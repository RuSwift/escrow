"""GET/POST /v1/simple/payment-requests — Simple UI без {space} в path."""

from datetime import datetime, timedelta, timezone

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

    yield app, owner
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_payment_requests_empty_200(main_app_simple_deals):
    app, _owner = main_app_simple_deals
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/simple/payment-requests")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_create_and_list_payment_request(main_app_simple_deals):
    app, owner = main_app_simple_deals
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
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post("/v1/simple/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["payment_request"]
        assert created["uid"]
        assert created["pair_label"]
        assert "RUB" in created["pair_label"]
        assert created["heading"] is None
        assert created["expires_at"] is not None
        exp = datetime.fromisoformat(created["expires_at"].replace("Z", "+00:00"))
        assert exp > datetime.now(timezone.utc)
        assert created["space_id"] == owner.id
        assert created["space_nickname"] == "simple_api_space"

        r = await client.get("/v1/simple/payment-requests")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        uids = {it["uid"] for it in body["items"]}
        assert created["uid"] in uids

        r2 = await client.get("/v1/simple/payment-requests?q=RUB")
        assert r2.status_code == 200
        assert r2.json()["total"] >= 1


@pytest.mark.asyncio
async def test_create_payment_request_heading_forever(main_app_simple_deals):
    app, owner = main_app_simple_deals
    payload = {
        "direction": "fiat_to_stable",
        "heading": "Тестовый заголовок",
        "lifetime": "forever",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "EUR",
            "amount": "500",
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
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post("/v1/simple/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["payment_request"]
        assert created["heading"] == "Тестовый заголовок"
        assert created["expires_at"] is None
        assert created["space_id"] == owner.id

        r = await client.get("/v1/simple/payment-requests?q=Тестовый")
        assert r.status_code == 200
        assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_create_payment_request_lifetime_48h(main_app_simple_deals):
    app, _owner = main_app_simple_deals
    payload = {
        "direction": "fiat_to_stable",
        "lifetime": "48h",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "GBP",
            "amount": "100",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "12",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post("/v1/simple/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["payment_request"]
        assert created["expires_at"] is not None
        exp = datetime.fromisoformat(created["expires_at"].replace("Z", "+00:00"))
        delta = exp - datetime.now(timezone.utc)
        assert timedelta(hours=47) < delta < timedelta(hours=49)


@pytest.mark.asyncio
async def test_deactivate_payment_request_success(main_app_simple_deals):
    app, _owner = main_app_simple_deals
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "USD",
            "amount": "100",
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
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post("/v1/simple/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        pk = c.json()["payment_request"]["pk"]

        d = await client.post(
            f"/v1/simple/payment-requests/{pk}/deactivate",
            json={"confirm_pk": str(pk)},
        )
        assert d.status_code == 200, d.text
        body = d.json()["payment_request"]
        assert body["deactivated_at"] is not None

        lst = await client.get("/v1/simple/payment-requests")
        assert lst.status_code == 200
        uids = {it["uid"]: it for it in lst.json()["items"]}
        assert body["uid"] in uids
        assert uids[body["uid"]]["deactivated_at"] is not None


@pytest.mark.asyncio
async def test_deactivate_payment_request_confirm_mismatch_400(main_app_simple_deals):
    app, _owner = main_app_simple_deals
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "JPY",
            "amount": "1000",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "1",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post("/v1/simple/payment-requests", json=payload)
        pk = c.json()["payment_request"]["pk"]
        d = await client.post(
            f"/v1/simple/payment-requests/{pk}/deactivate",
            json={"confirm_pk": "999999"},
        )
        assert d.status_code == 400
        assert "не совпадает" in d.json()["detail"]


@pytest.mark.asyncio
async def test_deactivate_payment_request_already_400(main_app_simple_deals):
    app, _owner = main_app_simple_deals
    payload = {
        "direction": "stable_to_fiat",
        "primary_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "50",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "fiat",
            "code": "EUR",
            "amount": None,
            "side": "receive",
            "amount_discussed": True,
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post("/v1/simple/payment-requests", json=payload)
        pk = c.json()["payment_request"]["pk"]
        first = await client.post(
            f"/v1/simple/payment-requests/{pk}/deactivate",
            json={"confirm_pk": str(pk)},
        )
        assert first.status_code == 200
        second = await client.post(
            f"/v1/simple/payment-requests/{pk}/deactivate",
            json={"confirm_pk": str(pk)},
        )
        assert second.status_code == 400
        assert "деактивирована" in second.json()["detail"]


@pytest.mark.asyncio
async def test_deactivate_payment_request_not_found_404(main_app_simple_deals):
    app, _owner = main_app_simple_deals
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/simple/payment-requests/999999999/deactivate",
            json={"confirm_pk": "999999999"},
        )
        assert r.status_code == 404
