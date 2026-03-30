"""POST withdrawal, GET order-sign по dedupe_key в БД, DELETE заявки."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from sqlalchemy import select

from db import get_db
from db.models import Order, Wallet, WalletUser
from repos.order import ORDER_CATEGORY_WITHDRAWAL, withdrawal_dedupe_key
from web.endpoints.dependencies import (
    get_redis,
    get_required_wallet_address_for_space,
    get_settings,
    ResolvedSettings,
)
from web.main import create_app

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"


@pytest_asyncio.fixture
async def main_app_withdrawal(test_db, test_redis, test_settings):
    owner = WalletUser(
        nickname="wd_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:wd_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w = Wallet(
        name="ramp_ext",
        encrypted_mnemonic=None,
        role="external",
        tron_address="TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi",
        owner_did=owner.did,
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

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

    yield app, w.id
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_withdrawal_201(main_app_withdrawal, test_redis):
    app, wallet_id = main_app_withdrawal
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/spaces/wd_space/orders/withdrawal",
            json={
                "wallet_id": wallet_id,
                "token_type": "native",
                "symbol": "TRX",
                "contract_address": None,
                "amount_raw": 1_000_000,
                "destination_address": "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi",
            },
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert "sign_url" in data
        assert "/o/" in data["sign_url"]
        assert data["order"]["payload"]["kind"] == "withdrawal_request"
        assert data["order"]["category"] == ORDER_CATEGORY_WITHDRAWAL
        dedupe = data["order"]["dedupe_key"]
        assert dedupe.startswith("withdrawal:")
        sign_token = dedupe.split("withdrawal:", 1)[1]
        assert sign_token in data["sign_url"]
        assert dedupe == withdrawal_dedupe_key(sign_token)
        r_sign = await client.get(f"/v1/order-sign/{sign_token}")
        assert r_sign.status_code == 200, r_sign.text
        assert r_sign.json()["order_id"] == data["order"]["id"]


@pytest.mark.asyncio
async def test_order_sign_get_404(main_app_withdrawal):
    app, _ = main_app_withdrawal
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/order-sign/invalidtoken00000000000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_withdrawal_204(main_app_withdrawal):
    app, wallet_id = main_app_withdrawal
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/spaces/wd_space/orders/withdrawal",
            json={
                "wallet_id": wallet_id,
                "token_type": "native",
                "symbol": "TRX",
                "contract_address": None,
                "amount_raw": 1_000_000,
                "destination_address": "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi",
            },
        )
        assert r.status_code == 201
        order_id = r.json()["order"]["id"]
        r_del = await client.delete(f"/v1/spaces/wd_space/orders/{order_id}")
    assert r_del.status_code == 204


@pytest.mark.asyncio
async def test_delete_withdrawal_400_when_confirmed(main_app_withdrawal, test_db):
    app, wallet_id = main_app_withdrawal
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/spaces/wd_space/orders/withdrawal",
            json={
                "wallet_id": wallet_id,
                "token_type": "native",
                "symbol": "TRX",
                "contract_address": None,
                "amount_raw": 1_000_000,
                "destination_address": "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi",
            },
        )
        assert r.status_code == 201
        order_id = r.json()["order"]["id"]
        row_res = await test_db.execute(select(Order).where(Order.id == order_id))
        row = row_res.scalar_one()
        payload = dict(row.payload or {})
        payload["status"] = "confirmed"
        row.payload = payload
        test_db.add(row)
        await test_db.commit()
        r_del = await client.delete(f"/v1/spaces/wd_space/orders/{order_id}")
    assert r_del.status_code == 400
    assert "Cannot delete withdrawal" in r_del.json()["detail"]
