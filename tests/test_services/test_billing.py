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


# --- add_transaction ---


@pytest.mark.asyncio
async def test_add_transaction_replenish_updates_balance(
    billing_service, wallet_user_service
):
    """add_transaction с положительной суммой пополняет баланс и создаёт запись."""
    await wallet_user_service.create_user(
        TRON_BILLING_1, "tron", "billing_user"
    )
    user = await wallet_user_service.get_by_wallet_address(TRON_BILLING_1)
    assert user is not None
    from decimal import Decimal

    await billing_service.add_transaction(user.id, Decimal("50.25"))
    updated = await wallet_user_service.get_by_id(user.id)
    assert float(updated.balance_usdt) == 50.25
    items, total = await billing_service.get_history(user.id, page=1, page_size=10)
    assert total == 1
    assert float(items[0].usdt_amount) == 50.25


@pytest.mark.asyncio
async def test_add_transaction_withdraw_updates_balance(
    billing_service, wallet_user_service
):
    """add_transaction с отрицательной суммой списывает баланс (при достаточном балансе)."""
    await wallet_user_service.create_user(
        TRON_BILLING_2, "tron", "billing_user2"
    )
    user = await wallet_user_service.get_by_wallet_address(TRON_BILLING_2)
    from decimal import Decimal

    await billing_service.add_transaction(user.id, Decimal("100"))
    await billing_service.add_transaction(user.id, Decimal("-30"))
    updated = await wallet_user_service.get_by_id(user.id)
    assert float(updated.balance_usdt) == 70
    items, total = await billing_service.get_history(user.id, page=1, page_size=10)
    assert total == 2


@pytest.mark.asyncio
async def test_add_transaction_insufficient_balance_raises(
    billing_service, wallet_user_service
):
    """add_transaction с отрицательной суммой при нулевом балансе поднимает ValueError."""
    await wallet_user_service.create_user(
        TRON_BILLING_1, "tron", "billing_user"
    )
    user = await wallet_user_service.get_by_wallet_address(TRON_BILLING_1)
    from decimal import Decimal

    with pytest.raises(ValueError, match="Insufficient balance"):
        await billing_service.add_transaction(user.id, Decimal("-10"))


@pytest.mark.asyncio
async def test_add_transaction_user_not_found_raises(
    billing_service,
):
    """add_transaction для несуществующего wallet_user_id поднимает ValueError."""
    from decimal import Decimal

    with pytest.raises(ValueError, match="User not found"):
        await billing_service.add_transaction(999999, Decimal("10"))
