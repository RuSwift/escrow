"""
Репозиторий для биллинга (Billing). Список с пагинацией и опциональными фильтрами.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import Billing
from repos.base import BaseRepository
from settings import Settings


class BillingResource(BaseResource):
    """Resource-схемы для операций с биллингом (Billing)."""

    class Get(BaseResource.Get):
        id: int
        wallet_user_id: int
        usdt_amount: Decimal
        created_at: datetime


def _model_to_get(model: Billing) -> BillingResource.Get:
    """Преобразует модель Billing в BillingResource.Get."""
    return BillingResource.Get(
        id=model.id,
        wallet_user_id=model.wallet_user_id,
        usdt_amount=model.usdt_amount,
        created_at=model.created_at,
    )


class BillingRepository(BaseRepository):
    """
    Репозиторий для биллинга. Список с обязательными offset/limit и опциональными фильтрами.
    """

    async def list(
        self,
        offset: int,
        limit: int,
        *,
        wallet_user_id: Optional[int] = None,
    ) -> tuple[list[BillingResource.Get], int]:
        """
        Список записей с пагинацией. Обязательны offset и limit.
        Остальные параметры — опциональные фильтры: при указании строятся условия WHERE.
        Возвращает (список записей, общее количество с учётом фильтров).
        """
        stmt = select(Billing)
        count_stmt = select(func.count(Billing.id))

        if wallet_user_id is not None:
            stmt = stmt.where(Billing.wallet_user_id == wallet_user_id)
            count_stmt = count_stmt.where(Billing.wallet_user_id == wallet_user_id)

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(Billing.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        items = [_model_to_get(r) for r in rows]
        return items, total
