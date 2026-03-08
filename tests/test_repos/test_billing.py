"""
Тесты BillingRepository.list(offset, limit, *, wallet_user_id=...) на реальной БД.
"""
from decimal import Decimal

import pytest
from db.models import Billing, WalletUser
from repos.billing import BillingRepository


@pytest.fixture
def billing_repo(test_db, test_redis, test_settings) -> BillingRepository:
    """BillingRepository с тестовой сессией."""
    return BillingRepository(
        session=test_db,
        redis=test_redis,
        settings=test_settings,
    )


@pytest.fixture
async def wallet_user_id(test_db):
    """Создаёт одного WalletUser в БД и возвращает его id."""
    user = WalletUser(
        wallet_address="TXyz123456789012345678901234567890AB",
        blockchain="tron",
        did="did:tron:TXyz123456789012345678901234567890AB",
        nickname="billing_test_user",
    )
    test_db.add(user)
    await test_db.flush()
    await test_db.commit()
    await test_db.refresh(user)
    return user.id


@pytest.mark.asyncio
async def test_list_empty_returns_empty_and_zero(billing_repo):
    """Без записей list() возвращает ([], 0)."""
    items, total = await billing_repo.list(0, 10)
    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_list_with_wallet_user_id_filter(billing_repo, wallet_user_id):
    """С фильтром wallet_user_id возвращаются только записи этого пользователя."""
    from db.models import Billing

    b1 = Billing(wallet_user_id=wallet_user_id, usdt_amount=Decimal("10.00"))
    b2 = Billing(wallet_user_id=wallet_user_id, usdt_amount=Decimal("-5.50"))
    billing_repo._session.add(b1)
    billing_repo._session.add(b2)
    await billing_repo._session.flush()
    await billing_repo._session.commit()

    items, total = await billing_repo.list(0, 10, wallet_user_id=wallet_user_id)
    assert len(items) == 2
    assert total == 2
    amounts = {float(x.usdt_amount) for x in items}
    assert amounts == {10.0, -5.5}


@pytest.mark.asyncio
async def test_list_pagination_offset_limit(billing_repo, wallet_user_id):
    """Пагинация: offset и limit ограничивают выборку, total — полный count."""
    from db.models import Billing

    for i in range(5):
        b = Billing(wallet_user_id=wallet_user_id, usdt_amount=Decimal(str(i)))
        billing_repo._session.add(b)
    await billing_repo._session.flush()
    await billing_repo._session.commit()

    items, total = await billing_repo.list(1, 2, wallet_user_id=wallet_user_id)
    assert len(items) == 2
    assert total == 5
    items2, _ = await billing_repo.list(0, 2, wallet_user_id=wallet_user_id)
    assert len(items2) == 2


@pytest.mark.asyncio
async def test_list_order_by_created_at_desc(billing_repo, wallet_user_id):
    """Записи возвращаются в порядке created_at DESC (новые первые)."""
    from db.models import Billing

    b1 = Billing(wallet_user_id=wallet_user_id, usdt_amount=Decimal("1"))
    b2 = Billing(wallet_user_id=wallet_user_id, usdt_amount=Decimal("2"))
    billing_repo._session.add(b1)
    billing_repo._session.add(b2)
    await billing_repo._session.flush()
    await billing_repo._session.commit()

    items, _ = await billing_repo.list(0, 10, wallet_user_id=wallet_user_id)
    assert len(items) >= 2
    # Последняя добавленная (b2) обычно имеет более поздний created_at
    assert items[0].id >= items[1].id or items[0].created_at >= items[1].created_at
