"""Сервис сделок (Deal): Simple-заявки fiat↔stable."""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Literal, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Deal, Wallet
from repos.deal import DealRepository
from repos.node import NodeRepository
from services.exchange_wallets import ExchangeWalletService
from services.space import SpaceService
from services.wallet_user import WalletUserService
from settings import Settings

logger = logging.getLogger(__name__)

SimpleDirection = Literal["fiat_to_stable", "stable_to_fiat"]


class DealService:
    """Бизнес-логика по Deal; Simple-заявки без space в URL (space из auth)."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._deals = DealRepository(session=session, redis=redis, settings=settings)
        self._space = SpaceService(session=session, redis=redis, settings=settings)
        self._wallet_users = WalletUserService(session=session, redis=redis, settings=settings)
        self._exchange = ExchangeWalletService(session=session, redis=redis, settings=settings)

    def _blockchain_for_standard(self, standard: str) -> str:
        s = (standard or "").strip().lower()
        if s == "tron":
            return "tron"
        if s == "web3":
            return "ethereum"
        return "tron"

    async def _resolve_arbiter_did(self) -> str:
        stmt = select(Wallet.owner_did).where(Wallet.role == "arbiter").limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row and str(row).strip():
            return str(row).strip()
        node_repo = NodeRepository(
            session=self._session, redis=self._redis, settings=self._settings
        )
        node = await node_repo.get()
        if node and (node.did or "").strip():
            return node.did.strip()
        raise ValueError("Arbiter not configured")

    async def _resolve_space(
        self, *, wallet_address: str, standard: str
    ) -> str:
        bc = self._blockchain_for_standard(standard)
        nick = await self._wallet_users.resolve_primary_space_nickname(
            wallet_address, bc
        )
        if not nick:
            raise ValueError("No space for this wallet")
        return nick

    async def list_simple_applications(
        self,
        *,
        wallet_address: str,
        actor_did: str,
        standard: str,
        page: int,
        page_size: int,
        q: Optional[str],
    ) -> Tuple[List[Deal], int]:
        space = await self._resolve_space(wallet_address=wallet_address, standard=standard)
        await self._space.ensure_owner_or_operator(space, wallet_address)
        return await self._deals.list_simple_applications_for_sender(
            actor_did, page=page, page_size=page_size, q=q
        )

    async def create_simple_application(
        self,
        *,
        wallet_address: str,
        sender_did: str,
        standard: str,
        direction: SimpleDirection,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
    ) -> Deal:
        space = await self._resolve_space(wallet_address=wallet_address, standard=standard)
        await self._space.ensure_owner_or_operator(space, wallet_address)

        self._validate_simple_legs(direction, primary_leg, counter_leg)

        receiver_did = (self._settings.deal_simple_placeholder_receiver_did or "").strip()
        if not receiver_did:
            raise ValueError("deal_simple_placeholder_receiver_did is empty")

        arbiter_did = await self._resolve_arbiter_did()

        ramp_wallet_id = await self._exchange.primary_ramp_wallet_id_for_space(
            space, wallet_address
        )

        requisites: Dict[str, Any] = {
            "simple_application": True,
            "space": space,
            "direction": direction,
            "primary_leg": primary_leg,
            "counter_leg": counter_leg,
        }
        if ramp_wallet_id is not None:
            requisites["primary_ramp_wallet_id"] = ramp_wallet_id

        label = self._build_label(direction, primary_leg, counter_leg)
        description = self._build_description(direction, primary_leg, counter_leg)
        amount = self._primary_amount_decimal(primary_leg)

        uid = uuid.uuid4().hex
        row = await self._deals.insert_simple_application(
            uid=uid,
            sender_did=sender_did,
            receiver_did=receiver_did,
            arbiter_did=arbiter_did,
            label=label,
            description=description,
            amount=amount,
            requisites=requisites,
        )
        await self._session.commit()
        await self._session.refresh(row)
        logger.info("Simple Deal created uid=%s space=%s sender=%s", uid, space, sender_did)
        return row

    @staticmethod
    def _leg_code(leg: Dict[str, Any]) -> str:
        return str((leg or {}).get("code") or "").strip().upper()

    @staticmethod
    def _leg_amount_str(leg: Dict[str, Any]) -> Optional[str]:
        raw = (leg or {}).get("amount")
        if raw is None:
            return None
        s = str(raw).strip()
        return s if s else None

    def _build_label(
        self,
        direction: SimpleDirection,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
    ) -> str:
        a = self._leg_code(primary_leg)
        b = self._leg_code(counter_leg)
        if direction == "fiat_to_stable":
            return f"Simple {a} → {b}"
        return f"Simple {a} → {b}"

    def _build_description(
        self,
        direction: SimpleDirection,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
    ) -> str:
        parts = [f"direction={direction}"]
        pa = self._leg_amount_str(primary_leg)
        ca = self._leg_amount_str(counter_leg)
        if pa:
            parts.append(f"primary_amount={pa}")
        if ca:
            parts.append(f"counter_amount={ca}")
        elif (counter_leg or {}).get("amount_discussed"):
            parts.append("counter_amount=discussed")
        return "; ".join(parts)

    def _primary_amount_decimal(self, primary_leg: Dict[str, Any]) -> Optional[Decimal]:
        s = self._leg_amount_str(primary_leg)
        if not s:
            return None
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    def _validate_simple_legs(
        self,
        direction: SimpleDirection,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
    ) -> None:
        if direction not in ("fiat_to_stable", "stable_to_fiat"):
            raise ValueError("Invalid direction")
        for name, leg in (("primary_leg", primary_leg), ("counter_leg", counter_leg)):
            if not isinstance(leg, dict):
                raise ValueError(f"{name} must be an object")
            at = str(leg.get("asset_type") or "").strip().lower()
            if at not in ("fiat", "stable"):
                raise ValueError(f"{name}.asset_type invalid")
            code = str(leg.get("code") or "").strip()
            if not code or len(code) > 32:
                raise ValueError(f"{name}.code invalid")
            side = str(leg.get("side") or "").strip().lower()
            if side not in ("give", "receive"):
                raise ValueError(f"{name}.side invalid")
            amt = self._leg_amount_str(leg)
            if name == "primary_leg" and not amt:
                raise ValueError("primary_leg.amount is required")
            if name == "counter_leg" and not amt and not leg.get("amount_discussed"):
                raise ValueError(
                    "counter_leg.amount or counter_leg.amount_discussed required"
                )
