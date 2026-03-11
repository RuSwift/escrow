"""
Сервис для работы с историей биллинга (Billing).
"""
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from repos.billing import BillingRepository, BillingResource
from repos.wallet_user import WalletUserRepository, WalletUserResource
from settings import Settings


class BillingService:
    """Сервис для получения истории биллинга по пользователю и операций пополнения/списания."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
        *,
        wallet_user_repo: WalletUserRepository | None = None,
    ):
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = BillingRepository(
            session=session, redis=redis, settings=settings
        )
        self._wallet_user_repo = wallet_user_repo or WalletUserRepository(
            session=session, redis=redis, settings=settings
        )

    async def add_transaction(
        self, wallet_user_id: int, usdt_amount: Decimal
    ) -> None:
        """
        Создать запись биллинга и обновить баланс пользователя.
        usdt_amount: положительный — пополнение, отрицательный — списание.
        """
        user = await self._wallet_user_repo.get(wallet_user_id)
        if not user:
            raise ValueError("User not found")
        new_balance = user.balance_usdt + usdt_amount
        if new_balance < 0:
            raise ValueError("Insufficient balance for withdrawal")
        await self._repo.create(
            BillingResource.Create(
                wallet_user_id=wallet_user_id,
                usdt_amount=usdt_amount,
            )
        )
        await self._wallet_user_repo.patch(
            wallet_user_id,
            WalletUserResource.Patch(balance_usdt=new_balance),
        )
        await self._session.commit()

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
