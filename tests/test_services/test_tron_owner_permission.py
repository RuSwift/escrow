"""Tron: owner permission для спейса и build_permission_body."""

import pytest

from db.models import WalletUser, WalletUserSub
from repos.wallet_user import WalletUserRepository
from services.tron.grid_client import OWNER_PERMISSION_THRESHOLD, TronGridClient
from services.tron.utils import owner_permission_allows_signer


def test_owner_permission_allows_signer_no_block_returns_true():
    assert owner_permission_allows_signer({}, "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH") is True


def test_owner_permission_allows_signer_empty_keys_returns_true():
    assert (
        owner_permission_allows_signer(
            {"owner_permission": {"keys": []}}, "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
        )
        is True
    )


def test_owner_permission_allows_signer_match():
    tron = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
    acc = {
        "owner_permission": {
            "threshold": 1,
            "keys": [{"address": tron, "weight": 1}],
        }
    }
    assert owner_permission_allows_signer(acc, tron) is True


def test_owner_permission_allows_signer_no_match():
    acc = {
        "owner_permission": {
            "keys": [{"address": "TOther123456789012345678901234567890AB", "weight": 1}],
        }
    }
    assert (
        owner_permission_allows_signer(acc, "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH")
        is False
    )


def test_build_permission_body_owner_keys_and_threshold():
    body = TronGridClient.build_permission_body(
        owner_address="TMsig1111111111111111111111111111111111",
        owner_tron_addresses=[
            "TOwner1111111111111111111111111111111111",
            "TOwner222222222222222222222222222222222222",
        ],
        actor_addresses=["TRXActor1111111111111111111111111111111111"],
        threshold=1,
        permission_name="ms_test",
    )
    assert body["owner"]["threshold"] == OWNER_PERMISSION_THRESHOLD == 1
    assert len(body["owner"]["keys"]) == 2
    assert body["owner"]["keys"][0]["address"] == "TOwner1111111111111111111111111111111111"
    assert body["actives"][0]["threshold"] == 1


def test_build_permission_body_empty_owner_raises():
    with pytest.raises(ValueError, match="owner_tron_addresses"):
        TronGridClient.build_permission_body(
            owner_address="TMsig1111111111111111111111111111111111",
            owner_tron_addresses=[],
            actor_addresses=["TAct111111111111111111111111111111111111"],
            threshold=1,
            permission_name="x",
        )


@pytest.mark.asyncio
async def test_list_tron_owner_addresses_parent_and_sub(test_db, test_redis, test_settings):
    repo = WalletUserRepository(
        session=test_db, redis=test_redis, settings=test_settings
    )
    parent = WalletUser(
        wallet_address="TParent1111111111111111111111111111111111",
        blockchain="tron",
        did="did:tron:parent_owner_perm",
        nickname="space_owner_perm_u1",
    )
    test_db.add(parent)
    await test_db.flush()
    sub_owner = WalletUserSub(
        wallet_user_id=parent.id,
        wallet_address="TSubOwner111111111111111111111111111111111111",
        blockchain="tron",
        nickname="so",
        roles=["owner"],
        is_verified=False,
        is_blocked=False,
    )
    sub_op = WalletUserSub(
        wallet_user_id=parent.id,
        wallet_address="TSubOp1111111111111111111111111111111111111111",
        blockchain="tron",
        nickname="op",
        roles=["operator"],
        is_verified=False,
        is_blocked=False,
    )
    test_db.add(sub_owner)
    test_db.add(sub_op)
    await test_db.commit()

    addrs = await repo.list_tron_owner_addresses_for_wallet_user(parent.id)
    assert addrs == [
        "TParent1111111111111111111111111111111111",
        "TSubOwner111111111111111111111111111111111111",
    ]
