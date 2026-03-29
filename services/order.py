"""Сервис ордеров дашборда (эфемерные подсказки и задел под сделки)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Wallet
from repos.order import ORDER_CATEGORY_EPHEMERAL, OrderRepository, OrderResource
from repos.wallet_user import WalletUserRepository
from services.multisig_wallet.constants import (
    SPACE_DRIFT_ELIGIBLE_STATUSES,
    TERMINAL_STATUSES,
)
from services.space import SpaceService
from settings import Settings

logger = logging.getLogger(__name__)

ORDER_KIND_MULTISIG_PIPELINE = "multisig_pipeline"
ORDER_KIND_MULTISIG_SPACE_DRIFT = "multisig_space_drift"


def _dedupe_pipeline(wallet_id: int) -> str:
    return f"ephemeral:multisig_pipeline:{wallet_id}"


def _dedupe_drift(wallet_id: int) -> str:
    return f"ephemeral:multisig_space_drift:{wallet_id}"


class OrderService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._orders = OrderRepository(session=session, redis=redis, settings=settings)
        self._wallet_users = WalletUserRepository(
            session=session, redis=redis, settings=settings
        )
        self._space = SpaceService(session=session, redis=redis, settings=settings)

    async def _owner_did_for_space(self, space: str) -> str:
        owner = await self._wallet_users.get_by_nickname((space or "").strip())
        if not owner:
            raise ValueError("Space not found")
        return owner.did

    async def list_for_space(
        self,
        space: str,
        actor_wallet_address: str,
    ) -> List[OrderResource.Get]:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        return await self._orders.list_ephemeral_by_owner_did(owner_did)

    async def refresh_ephemeral(self) -> Dict[str, int]:
        """
        Два прохода: вычислить желаемое множество эфемерных ордеров, затем синхронизировать БД.
        multisig_space_drift — только при статусах active | failed (настройка завершена).
        """
        desired: List[OrderResource.EphemeralSync] = []

        stmt = select(Wallet).where(Wallet.role == "multisig")
        res = await self._session.execute(stmt)
        wallets: List[Wallet] = list(res.scalars().all())

        for w in wallets:
            st = w.multisig_setup_status
            if st is not None and st not in TERMINAL_STATUSES:
                desired.append(
                    OrderResource.EphemeralSync(
                        dedupe_key=_dedupe_pipeline(w.id),
                        space_wallet_id=w.id,
                        payload={
                            "kind": ORDER_KIND_MULTISIG_PIPELINE,
                            "wallet_id": w.id,
                            "wallet_name": w.name,
                            "multisig_setup_status": st,
                            "tron_address": (w.tron_address or "").strip() or None,
                        },
                    )
                )

            odid = (w.owner_did or "").strip()
            if not odid:
                continue
            wu = await self._wallet_users.get_by_did(odid)
            if not wu:
                continue
            if st not in SPACE_DRIFT_ELIGIBLE_STATUSES:
                continue
            admin_addrs = await self._wallet_users.list_tron_owner_addresses_for_wallet_user(
                wu.id
            )
            oo_addrs = await self._wallet_users.list_tron_owner_operator_addresses_for_wallet_user(
                wu.id
            )
            admins_set = {a.strip() for a in admin_addrs if (a or "").strip()}
            oo_set = {a.strip() for a in oo_addrs if (a or "").strip()}
            meta = w.multisig_setup_meta or {}
            actors_raw = meta.get("actors") or []
            actors_set: set[str] = set()
            for a in actors_raw:
                if isinstance(a, str) and (a or "").strip():
                    actors_set.add(a.strip())

            owners_drift = False
            owners_set: set[str] = set()
            if "owners" in meta:
                for o in meta.get("owners") or []:
                    if isinstance(o, str) and (o or "").strip():
                        owners_set.add(o.strip())
                owners_drift = owners_set != admins_set

            actors_drift = actors_set != oo_set

            if owners_drift or actors_drift:
                owners_only_in_meta: List[str] = []
                owners_only_in_space: List[str] = []
                if owners_drift:
                    owners_only_in_meta = sorted(owners_set - admins_set)
                    owners_only_in_space = sorted(admins_set - owners_set)
                actors_only_in_meta = sorted(actors_set - oo_set) if actors_drift else []
                actors_only_in_space = sorted(oo_set - actors_set) if actors_drift else []
                desired.append(
                    OrderResource.EphemeralSync(
                        dedupe_key=_dedupe_drift(w.id),
                        space_wallet_id=w.id,
                        payload={
                            "kind": ORDER_KIND_MULTISIG_SPACE_DRIFT,
                            "wallet_id": w.id,
                            "wallet_name": w.name,
                            "multisig_setup_status": st,
                            "tron_address": (w.tron_address or "").strip() or None,
                            "owners_drift": owners_drift,
                            "actors_drift": actors_drift,
                            "meta_owners": sorted(owners_set),
                            "actors": sorted(actors_set),
                            "space_tron_admins": sorted(admins_set),
                            "space_tron_owner_operator": sorted(oo_set),
                            "owners_only_in_meta": owners_only_in_meta,
                            "owners_only_in_space": owners_only_in_space,
                            "actors_only_in_meta": actors_only_in_meta,
                            "actors_only_in_space": actors_only_in_space,
                            "only_in_meta": actors_only_in_meta,
                            "only_in_space": actors_only_in_space,
                            "space_tron_owners": sorted(oo_set),
                        },
                    )
                )

        upserted, deleted = await self._orders.replace_ephemeral_orders(desired)
        return {"upserted": upserted, "deleted": deleted}
