"""
Сервис для работы с историей биллинга (Billing).
"""
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from repos.billing import BillingRepository, BillingResource
from settings import Settings


class BillingService:
    """Сервис для получения истории биллинга по пользователю."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ):
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = BillingRepository(
            session=session, redis=redis, settings=settings
        )

    async def get_history(
        self,
        wallet_user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[BillingResource.Get], int]:
        """
        История биллинга по wallet_user_id с пагинацией.
        Возвращает (список записей, общее количество).
        """
        offset = (page - 1) * page_size
        return await self._repo.list(
            offset=offset,
            limit=page_size,
            wallet_user_id=wallet_user_id,
        )


__all__ = ["BillingService"]
