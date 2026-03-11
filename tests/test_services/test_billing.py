"""
Тесты BillingService.get_history на реальной БД и Redis.
"""
import pytest

from services.billing import BillingService

# Валидные TRON-адреса (base58: T + 34 символа без 0/O/I/l)
TRON_BILLING_1 = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
TRON_BILLING_2 = "T" + "2" * 33


@pytest.fixture
def billing_service(test_db, test_redis, test_settings) -> BillingService:
    """BillingService с тестовой сессией."""
    return BillingService(
        session=test_db,
        redis=test_redis,
        settings=test_settings,
    )


@pytest.fixture
def wallet_user_service(test_db, test_redis, test_settings):
    """WalletUserService для создания пользователя и получения id."""
    from services.wallet_user import WalletUserService
    return WalletUserService(
        session=test_db,
        redis=test_redis,
        settings=test_settings,
    )


@pytest.mark.asyncio
async def test_get_history_empty_returns_empty_list_and_zero(
    billing_service, wallet_user_service
):
    """Для пользователя без записей биллинга get_history возвращает ([], 0)."""
    await wallet_user_service.create_user(
        TRON_BILLING_1, "tron", "billing_user"
    )
    user = await wallet_user_service.get_by_wallet_address(TRON_BILLING_1)
    assert user is not None
    items, total = await billing_service.get_history(user.id, page=1, page_size=20)
    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_get_history_returns_list_and_total(
    billing_service, wallet_user_service
):
    """get_history делегирует в repo и возвращает (list, total) с пагинацией."""
    await wallet_user_service.create_user(
        TRON_BILLING_2, "tron", "billing_user2"
    )
    user = await wallet_user_service.get_by_wallet_address(TRON_BILLING_2)
    assert user is not None
    from decimal import Decimal
    from db.models import Billing

    b = Billing(wallet_user_id=user.id, usdt_amount=Decimal("100.5"))
    billing_service._session.add(b)
    await billing_service._session.flush()
    await billing_service._session.commit()

    items, total = await billing_service.get_history(user.id, page=1, page_size=10)
    assert len(items) == 1
    assert total == 1
    assert float(items[0].usdt_amount) == 100.5
