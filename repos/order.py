"""Репозиторий Order (эфемерные ордера дашборда)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Text, and_, cast, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import Order as OrderModel
from db.models import OrderWithdrawalSignature as OrderWithdrawalSignatureModel
from db.models import Wallet
from repos.base import BaseRepository
from settings import Settings

ORDER_CATEGORY_EPHEMERAL = "ephemeral"
ORDER_CATEGORY_WITHDRAWAL = "withdrawal"


class OrderResource(BaseResource):
    """Контракт ордера в слое репозитория (без экспозиции ORM наружу)."""

    class Get(BaseResource.Get):
        id: int
        category: str
        dedupe_key: str
        space_wallet_id: int | None = None
        payload: Dict[str, Any] | None = None
        created_at: datetime
        updated_at: datetime

    class EphemeralSync(BaseModel):
        """Строка полной синхронизации эфемерных ордеров (upsert по dedupe_key)."""

        model_config = ConfigDict(extra="forbid")

        dedupe_key: str = Field(..., max_length=255)
        space_wallet_id: int = Field(..., description="wallets.id ramp-кошелька спейса")
        payload: Dict[str, Any]


def _order_model_to_get(model: OrderModel) -> OrderResource.Get:
    return OrderResource.Get(
        id=int(model.id),
        category=model.category,
        dedupe_key=model.dedupe_key,
        space_wallet_id=model.space_wallet_id,
        payload=dict(model.payload) if model.payload is not None else None,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class OrderRepository(BaseRepository):
    """CRUD и синхронизация эфемерных ордеров."""

    async def list_ephemeral_by_owner_did(self, owner_did: str) -> List[OrderResource.Get]:
        od = (owner_did or "").strip()
        if not od:
            return []
        stmt = (
            select(OrderModel)
            .join(Wallet, OrderModel.space_wallet_id == Wallet.id)
            .where(
                OrderModel.category == ORDER_CATEGORY_EPHEMERAL,
                Wallet.owner_did == od,
            )
            .order_by(OrderModel.updated_at.desc())
        )
        res = await self._session.execute(stmt)
        return [_order_model_to_get(m) for m in res.scalars().all()]

    async def replace_ephemeral_orders(
        self, rows: Sequence[OrderResource.EphemeralSync]
    ) -> Tuple[int, int]:
        """
        Полная синхронизация category=ephemeral: удалить лишние, upsert переданные.

        Связь со спейсом — колонка ``space_wallet_id`` (FK на ``wallets``).
        Возвращает (upserted_count, deleted_count).
        """
        keys = {r.dedupe_key for r in rows}
        del_stmt = delete(OrderModel).where(OrderModel.category == ORDER_CATEGORY_EPHEMERAL)
        if keys:
            del_stmt = del_stmt.where(OrderModel.dedupe_key.notin_(keys))
        del_res = await self._session.execute(del_stmt)
        deleted = del_res.rowcount or 0

        now = datetime.now(timezone.utc)
        upserted = 0
        for row in rows:
            ins = pg_insert(OrderModel).values(
                category=ORDER_CATEGORY_EPHEMERAL,
                dedupe_key=row.dedupe_key,
                space_wallet_id=row.space_wallet_id,
                payload=row.payload,
                created_at=now,
                updated_at=now,
            )
            stmt = ins.on_conflict_do_update(
                index_elements=[OrderModel.dedupe_key],
                set_={
                    "space_wallet_id": ins.excluded.space_wallet_id,
                    "payload": ins.excluded.payload,
                    "updated_at": ins.excluded.updated_at,
                },
            )
            await self._session.execute(stmt)
            upserted += 1
        return upserted, deleted

    async def insert_withdrawal_order(
        self,
        *,
        dedupe_key: str,
        space_wallet_id: int,
        payload: Dict[str, Any],
    ) -> OrderResource.Get:
        now = datetime.now(timezone.utc)
        model = OrderModel(
            category=ORDER_CATEGORY_WITHDRAWAL,
            dedupe_key=dedupe_key,
            space_wallet_id=space_wallet_id,
            payload=payload,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _order_model_to_get(model)

    async def get_by_id(self, order_id: int) -> Optional[OrderResource.Get]:
        stmt = select(OrderModel).where(OrderModel.id == order_id)
        res = await self._session.execute(stmt)
        m = res.scalar_one_or_none()
        return _order_model_to_get(m) if m else None

    async def get_by_dedupe_key(self, dedupe_key: str) -> Optional[OrderResource.Get]:
        dk = (dedupe_key or "").strip()
        if not dk:
            return None
        stmt = select(OrderModel).where(OrderModel.dedupe_key == dk)
        res = await self._session.execute(stmt)
        m = res.scalar_one_or_none()
        return _order_model_to_get(m) if m else None

    async def delete_withdrawal_by_id(self, order_id: int) -> bool:
        stmt = delete(OrderModel).where(
            OrderModel.id == order_id,
            OrderModel.category == ORDER_CATEGORY_WITHDRAWAL,
        )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0

    async def list_withdrawal_by_owner_did(self, owner_did: str) -> List[OrderResource.Get]:
        od = (owner_did or "").strip()
        if not od:
            return []
        stmt = (
            select(OrderModel)
            .join(Wallet, OrderModel.space_wallet_id == Wallet.id)
            .where(
                OrderModel.category == ORDER_CATEGORY_WITHDRAWAL,
                Wallet.owner_did == od,
            )
            .order_by(OrderModel.updated_at.desc())
        )
        res = await self._session.execute(stmt)
        return [_order_model_to_get(m) for m in res.scalars().all()]

    async def update_withdrawal_payload(
        self,
        order_id: int,
        payload: Dict[str, Any],
    ) -> None:
        stmt = (
            update(OrderModel)
            .where(
                OrderModel.id == order_id,
                OrderModel.category == ORDER_CATEGORY_WITHDRAWAL,
            )
            .values(payload=payload, updated_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)

    async def upsert_withdrawal_signature(
        self,
        order_id: int,
        signer_address: str,
        signature_data: Optional[Dict[str, Any]],
    ) -> None:
        addr = (signer_address or "").strip()
        if not addr:
            return
        ins = pg_insert(OrderWithdrawalSignatureModel).values(
            order_id=order_id,
            signer_address=addr,
            signature_data=signature_data,
            created_at=datetime.now(timezone.utc),
        )
        stmt = ins.on_conflict_do_update(
            constraint="uq_order_withdrawal_sig_order_signer",
            set_={
                "signature_data": ins.excluded.signature_data,
            },
        )
        await self._session.execute(stmt)

    async def list_withdrawal_signatures(
        self, order_id: int
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(OrderWithdrawalSignatureModel)
            .where(OrderWithdrawalSignatureModel.order_id == order_id)
            .order_by(OrderWithdrawalSignatureModel.created_at.asc())
        )
        res = await self._session.execute(stmt)
        out: List[Dict[str, Any]] = []
        for row in res.scalars().all():
            out.append(
                {
                    "signer_address": row.signer_address,
                    "signature_data": dict(row.signature_data)
                    if row.signature_data is not None
                    else None,
                    "created_at": row.created_at,
                }
            )
        return out

    async def list_merged_for_space_paginated(
        self,
        owner_did: str,
        *,
        page: int = 1,
        page_size: int = 10,
        status_filters: Optional[List[str]] = None,
        q: Optional[str] = None,
    ) -> Tuple[List[OrderResource.Get], int]:
        """
        Эфемерные + withdrawal ордера спейса (по owner_did ramp-кошельков), сортировка по updated_at desc.

        При непустом status_filters — только withdrawal с payload.status IN (…).
        None / пустой список — эфемерные и все выводы.
        q — поиск по dedupe_key и текстовому представлению payload (ILIKE).
        """
        od = (owner_did or "").strip()
        if not od:
            return [], 0
        page = max(1, int(page))
        page_size = min(max(1, int(page_size)), 100)
        offset = (page - 1) * page_size

        join_cond = OrderModel.space_wallet_id == Wallet.id
        clauses: List[Any] = [Wallet.owner_did == od]

        sf_list = [x.strip().lower() for x in (status_filters or []) if (x or "").strip()]
        if sf_list:
            sf_list = list(dict.fromkeys(sf_list))

        if sf_list:
            clauses.append(OrderModel.category == ORDER_CATEGORY_WITHDRAWAL)
            clauses.append(OrderModel.payload["status"].astext.in_(sf_list))
        else:
            clauses.append(
                or_(
                    OrderModel.category == ORDER_CATEGORY_EPHEMERAL,
                    OrderModel.category == ORDER_CATEGORY_WITHDRAWAL,
                )
            )

        qq = (q or "").strip()
        if qq:
            pattern = f"%{qq}%"
            clauses.append(
                or_(
                    OrderModel.dedupe_key.ilike(pattern),
                    cast(OrderModel.payload, Text).ilike(pattern),
                )
            )

        where_clause = and_(*clauses)

        count_stmt = (
            select(func.count(OrderModel.id))
            .select_from(OrderModel)
            .join(Wallet, join_cond)
            .where(where_clause)
        )
        total = int((await self._session.execute(count_stmt)).scalar_one() or 0)

        list_stmt = (
            select(OrderModel)
            .join(Wallet, join_cond)
            .where(where_clause)
            .order_by(OrderModel.updated_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        res = await self._session.execute(list_stmt)
        items = [_order_model_to_get(m) for m in res.scalars().all()]
        return items, total

    async def delete_withdrawal_signatures(self, order_id: int) -> int:
        stmt = delete(OrderWithdrawalSignatureModel).where(
            OrderWithdrawalSignatureModel.order_id == order_id
        )
        res = await self._session.execute(stmt)
        return int(res.rowcount or 0)


WITHDRAWAL_DEDUPE_PREFIX = "withdrawal:"


def withdrawal_dedupe_key(sign_token: str) -> str:
    """dedupe_key для заявки на вывод; sign_token — сегмент URL /o/{sign_token}."""
    t = (sign_token or "").strip()
    if not t:
        raise ValueError("withdrawal sign token required")
    return f"{WITHDRAWAL_DEDUPE_PREFIX}{t}"
