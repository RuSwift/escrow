"""Репозиторий Deal — зарезервирован под будущий CRUD; Simple-заявки в repos/payment_request."""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from repos.base import BaseRepository
from settings import Settings


class DealRepository(BaseRepository):
    """Пока без методов — заявки Simple в PaymentRequestRepository."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session=session, redis=redis, settings=settings)
