"""Репозиторий Deal — чтение по uid для Simple resolve."""

from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Deal
from repos.base import BaseRepository
from settings import Settings


class DealRepository(BaseRepository):
    """Чтение сделок; Simple-заявки в PaymentRequestRepository."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session=session, redis=redis, settings=settings)

    async def get_by_uid(self, uid: str) -> Optional[Deal]:
        """Сделка по публичному uid (уникальная ссылка)."""
        u = (uid or "").strip()
        if not u:
            return None
        stmt = select(Deal).where(Deal.uid == u)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()
