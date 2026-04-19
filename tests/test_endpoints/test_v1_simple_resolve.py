"""GET /v1/simple/resolve/{uid} — контекст страницы Simple."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from db.models import Deal, Wallet, WalletUser
from web.endpoints.dependencies import (
    UserInfo,
    get_current_wallet_user,
    get_redis,
    get_settings,
    ResolvedSettings,
)
from web.main import create_app

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"
_OTHER_TRON = "TQOtherSimpleResolveWallet999999999"


@pytest_asyncio.fixture
async def main_app_simple_resolve(test_db, test_redis, test_settings):
    owner = WalletUser(
        nickname="simple_resolve_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:tron:simple_resolve_owner",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    other = WalletUser(
        nickname="simple_resolve_other",
        wallet_address=_OTHER_TRON,
        blockchain="tron",
        did="did:tron:simple_resolve_other",
    )
    test_db.add(other)

    test_db.add(
        Wallet(
            name="arb_resolve_test",
            encrypted_mnemonic="enc",
            role="arbiter",
            tron_address="TArbiterResolveTest11111111111",
            ethereum_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            owner_did="did:peer:resolve_arbiter",
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

    yield app, owner, other
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resolve_payment_request_only(main_app_simple_resolve):
    app, owner, _other = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "CNY",
            "amount": "862500",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "125000",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post("/v1/simple/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        uid = c.json()["payment_request"]["uid"]

        r = await client.get(f"/v1/simple/resolve/{uid}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["kind"] == "payment_request_only"
        assert body["payment_request"]["uid"] == uid
        assert body["payment_request"]["space_id"] == owner.id
        assert body["deal"] is None


@pytest.mark.asyncio
async def test_resolve_payment_request_other_user_200(main_app_simple_resolve):
    app, owner, other = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "EUR",
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
        uid = c.json()["payment_request"]["uid"]

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        try:
            r = await client.get(f"/v1/simple/resolve/{uid}")
            assert r.status_code == 200
            assert r.json()["kind"] == "payment_request_only"
            assert r.json()["payment_request"]["uid"] == uid
        finally:
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=owner.did,
            )


@pytest.mark.asyncio
async def test_resolve_not_found_404(main_app_simple_resolve):
    app, _owner, _other = main_app_simple_resolve
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/simple/resolve/nonexistent_uid_xxxxxxxx")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_resolve_deal_only(test_db, test_redis, test_settings):
    """Сделка по uid — вторая ветка resolver (без проверки участников)."""
    owner = WalletUser(
        nickname="simple_resolve_deal_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:tron:deal_resolve_owner",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    test_db.add(
        Wallet(
            name="arb_deal_resolve",
            encrypted_mnemonic="enc",
            role="arbiter",
            tron_address="TArbDealResolve2222222222222222",
            ethereum_address="0xcccccccccccccccccccccccccccccccccccccccc",
            owner_did="did:peer:deal_resolve_arb",
        )
    )

    deal_uid = "SimpleResolveDealUidXYZ01"
    test_db.add(
        Deal(
            uid=deal_uid,
            sender_did="did:s:1",
            receiver_did="did:r:1",
            arbiter_did="did:peer:deal_resolve_arb",
            label="Resolve test deal",
            status="wait_deposit",
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

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            r = await client.get(f"/v1/simple/resolve/{deal_uid}")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["kind"] == "deal_only"
            assert body["deal"]["uid"] == deal_uid
            assert body["deal"]["label"] == "Resolve test deal"
            assert body["payment_request"] is None
    finally:
        app.dependency_overrides.clear()
