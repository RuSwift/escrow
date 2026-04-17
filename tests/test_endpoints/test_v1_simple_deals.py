"""GET/POST /v1/simple/deals — Simple UI без {space} в path."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from db.models import Wallet, WalletUser
from web.endpoints.dependencies import (
    UserInfo,
    get_current_wallet_user,
    get_redis,
    get_settings,
    ResolvedSettings,
)
from web.main import create_app

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"


@pytest_asyncio.fixture
async def main_app_simple_deals(test_db, test_redis, test_settings):
    owner = WalletUser(
        nickname="simple_api_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:tron:simple_api_space_owner",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    test_db.add(
        Wallet(
            name="arb_test",
            encrypted_mnemonic="enc",
            role="arbiter",
            tron_address="TArbiterSimpleDealsTest1111111111",
            ethereum_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            owner_did="did:peer:simple_deals_arbiter_owner",
        )
    )
    await test_db.commit()

    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        return ResolvedSettings(
            settings=test_settings,
            has_key=True,
            is_admin_configured=True,
            is_node_initialized=True,
        )

    async def override_current_user():
        return UserInfo(
            standard="tron",
            wallet_address=_OWNER_TRON,
            did=owner.did,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_wallet_user] = override_current_user

    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_simple_deals_empty_200(main_app_simple_deals):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_simple_deals),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/simple/deals")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_create_and_list_simple_deal(main_app_simple_deals):
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "RUB",
            "amount": "10000",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": None,
            "side": "receive",
            "amount_discussed": True,
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=main_app_simple_deals),
        base_url="http://test",
    ) as client:
        c = await client.post("/v1/simple/deals/simple-application", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["deal"]
        assert created["uid"]
        assert "Simple" in created["label"]

        r = await client.get("/v1/simple/deals")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        uids = {it["uid"] for it in body["items"]}
        assert created["uid"] in uids

        r2 = await client.get("/v1/simple/deals?q=RUB")
        assert r2.status_code == 200
        assert r2.json()["total"] >= 1
