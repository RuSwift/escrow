"""
Санный тест репозитория: субаккаунты (WalletUserSub) — add_sub, list_subs, get_sub, patch_sub, delete_sub.
"""
import pytest

from repos.wallet_user import (
    WalletUserRepository,
    WalletUserResource,
    WalletUserSubResource,
)


@pytest.fixture
def wallet_user_repo(test_db, test_redis, test_settings) -> WalletUserRepository:
    """WalletUserRepository с тестовой сессией."""
    return WalletUserRepository(
        session=test_db,
        redis=test_redis,
        settings=test_settings,
    )


@pytest.mark.asyncio
async def test_subs_crud_sane(wallet_user_repo):
    """Добавление субаккаунта, список, получение, обновление nickname, удаление."""
    parent = await wallet_user_repo.create(
        WalletUserResource.Create(
            wallet_address="TManager123456789012345678901234567890",
            blockchain="tron",
            nickname="manager_sane",
        )
    )
    assert parent.id

    subs_before = await wallet_user_repo.list_subs(parent.id)
    assert subs_before == []

    added = await wallet_user_repo.add_sub(
        parent.id,
        WalletUserSubResource.Create(
            wallet_address="TSub123456789012345678901234567890AB",
            blockchain="tron",
            nickname="sub_alice",
        ),
    )
    assert added.id
    assert added.wallet_user_id == parent.id
    assert added.wallet_address == "TSub123456789012345678901234567890AB"
    assert added.blockchain == "tron"
    assert added.nickname == "sub_alice"

    subs = await wallet_user_repo.list_subs(parent.id)
    assert len(subs) == 1
    assert subs[0].id == added.id
    assert subs[0].nickname == "sub_alice"

    got = await wallet_user_repo.get_sub(parent.id, added.id)
    assert got is not None
    assert got.nickname == "sub_alice"

    patched = await wallet_user_repo.patch_sub(
        parent.id, added.id, WalletUserSubResource.Patch(nickname="sub_alice_updated")
    )
    assert patched is not None
    assert patched.nickname == "sub_alice_updated"

    deleted = await wallet_user_repo.delete_sub(parent.id, added.id)
    assert deleted is True

    subs_after = await wallet_user_repo.list_subs(parent.id)
    assert subs_after == []
