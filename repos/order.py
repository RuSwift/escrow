"""Репозиторий Order (эфемерные ордера дашборда)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import Order as OrderModel
from db.models import Wallet
from repos.base import BaseRepository
from settings import Settings

ORDER_CATEGORY_EPHEMERAL = "ephemeral"


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
