"""GuarantorDirectionRepository: направления и профиль гаранта."""

from decimal import Decimal

import pytest
import pytest_asyncio

from db.models import WalletUser
from repos.guarantor_direction import GuarantorDirectionRepository
from settings import Settings


@pytest_asyncio.fixture
async def guarantor_dir_repo(test_db, test_redis, test_settings: Settings):
    return GuarantorDirectionRepository(session=test_db, redis=test_redis, settings=test_settings)


@pytest.mark.asyncio
async def test_list_create_update_delete(guarantor_dir_repo: GuarantorDirectionRepository, test_db):
    space = "acme"

    assert await guarantor_dir_repo.list_for_space(space) == []

    a = await guarantor_dir_repo.create(
        space,
        currency_code="USD",
        payment_code="PM1",
        payment_name="Wire",
        conditions_text="  Terms  ",
        commission_percent=Decimal("1.5"),
        sort_order=1,
    )
    assert a.id is not None
    assert a.space == space
    assert a.currency_code == "USD"
    assert a.payment_code == "PM1"
    assert a.payment_name == "Wire"
    assert a.conditions_text == "Terms"
    assert a.commission_percent == Decimal("1.5")

    b = await guarantor_dir_repo.create(
        space,
        currency_code="EUR",
        payment_code="PM2",
        sort_order=0,
    )
    rows = await guarantor_dir_repo.list_for_space(space)
    assert len(rows) == 2
    assert [r.id for r in rows] == [b.id, a.id]

    upd = await guarantor_dir_repo.update(
        a.id,
        space,
        conditions_text="New",
        commission_percent=None,
    )
    assert upd is not None
    assert upd.conditions_text == "New"
    assert upd.commission_percent is None

    other = await guarantor_dir_repo.get_by_id(a.id, "other_space")
    assert other is None

    ok = await guarantor_dir_repo.delete(a.id, space)
    assert ok is True
    assert await guarantor_dir_repo.get_by_id(a.id, space) is None
    assert await guarantor_dir_repo.delete(a.id, space) is False


@pytest.mark.asyncio
async def test_profile_upsert_and_delete(guarantor_dir_repo: GuarantorDirectionRepository, test_db):
    wu = WalletUser(
        wallet_address="TTestGuarantorProf1234567890123456",
        blockchain="tron",
        did="did:tron:testguarantorprofile",
        nickname="test_guarantor_profile_u",
    )
    test_db.add(wu)
    await test_db.commit()
    await test_db.refresh(wu)

    space = "acme"
    assert await guarantor_dir_repo.get_profile(wu.id, space) is None

    p1 = await guarantor_dir_repo.upsert_profile(
        wu.id,
        space,
        commission_percent=Decimal("2.5"),
        conditions_text=" Общие условия ",
    )
    assert p1.id is not None
    assert p1.wallet_user_id == wu.id
    assert p1.space == space
    assert p1.commission_percent == Decimal("2.5")
    assert p1.conditions_text == "Общие условия"

    p2 = await guarantor_dir_repo.upsert_profile(wu.id, space, commission_percent=Decimal("3"))
    assert p2.id == p1.id
    assert p2.commission_percent == Decimal("3")
    assert p2.conditions_text == "Общие условия"

    p3 = await guarantor_dir_repo.upsert_profile(wu.id, space, conditions_text=None)
    assert p3.conditions_text is None
    assert p3.commission_percent == Decimal("3")

    assert await guarantor_dir_repo.delete_profile(wu.id, space) is True
    assert await guarantor_dir_repo.get_profile(wu.id, space) is None
    assert await guarantor_dir_repo.delete_profile(wu.id, space) is False
