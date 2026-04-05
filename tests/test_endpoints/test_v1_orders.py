"""GET /v1/spaces/{space}/orders."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from db.models import Order, Wallet, WalletUser
from repos.order import ORDER_CATEGORY_EPHEMERAL, ORDER_CATEGORY_WITHDRAWAL
from services.order import ORDER_KIND_MULTISIG_PIPELINE, WITHDRAWAL_KIND
from web.endpoints.dependencies import (
    get_redis,
    get_required_wallet_address_for_space,
    get_settings,
    ResolvedSettings,
)
from web.main import create_app

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"


@pytest_asyncio.fixture
async def main_app_orders(test_db, test_redis, test_settings):
    owner = WalletUser(
        nickname="orders_api_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:orders_api_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w = Wallet(
        name="ramp_ms",
        encrypted_mnemonic="enc",
        role="multisig",
        owner_did=owner.did,
        multisig_setup_status="awaiting_funding",
        multisig_setup_meta={"actors": [], "threshold_n": None, "threshold_m": None},
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    test_db.add(
        Order(
            category=ORDER_CATEGORY_EPHEMERAL,
            dedupe_key=f"ephemeral:multisig_pipeline:{w.id}",
            space_wallet_id=w.id,
            payload={"kind": ORDER_KIND_MULTISIG_PIPELINE, "wallet_id": w.id},
        )
    )
    test_db.add(
        Order(
            category=ORDER_CATEGORY_WITHDRAWAL,
            dedupe_key="withdrawal:apitest_tok_confirmed",
            space_wallet_id=w.id,
            payload={
                "kind": WITHDRAWAL_KIND,
                "status": "confirmed",
                "tron_address": "TTest1111111111111111111111111111",
            },
        )
    )
    test_db.add(
        Order(
            category=ORDER_CATEGORY_WITHDRAWAL,
            dedupe_key="withdrawal:apitest_tok_failed",
            space_wallet_id=w.id,
            payload={
                "kind": WITHDRAWAL_KIND,
                "status": "failed",
                "tron_address": "TTest2222222222222222222222222222222",
            },
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

    async def override_wallet_address_for_space():
        return _OWNER_TRON

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_required_wallet_address_for_space] = (
        override_wallet_address_for_space
    )

    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_space_orders_200(main_app_orders):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_orders),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/spaces/orders_api_space/orders")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert len(body["items"]) >= 1
    assert body["items"][0]["payload"]["kind"] == ORDER_KIND_MULTISIG_PIPELINE
    assert body.get("total") == 3


@pytest.mark.asyncio
async def test_list_space_orders_pagination(main_app_orders):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_orders),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/v1/spaces/orders_api_space/orders",
            params={"page": 1, "page_size": 1},
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_list_space_orders_filter_status_withdrawal(main_app_orders):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_orders),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/v1/spaces/orders_api_space/orders",
            params={"status": "confirmed"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["payload"]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_list_space_orders_filter_status_excludes_ephemeral(main_app_orders):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_orders),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/v1/spaces/orders_api_space/orders",
            params={"status": "failed"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    for it in body["items"]:
        assert it["category"] == ORDER_CATEGORY_WITHDRAWAL


@pytest.mark.asyncio
async def test_list_space_orders_invalid_status_400(main_app_orders):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_orders),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/v1/spaces/orders_api_space/orders",
            params={"status": "not_a_real_status"},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_space_orders_filter_status_comma_separated(main_app_orders):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_orders),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/v1/spaces/orders_api_space/orders",
            params={"status": "confirmed,failed"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    statuses = {it["payload"]["status"] for it in body["items"]}
    assert statuses == {"confirmed", "failed"}


@pytest.mark.asyncio
async def test_list_space_orders_query_q(main_app_orders):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_orders),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/v1/spaces/orders_api_space/orders",
            params={"q": "apitest_tok_failed"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert "failed" in body["items"][0]["dedupe_key"]
