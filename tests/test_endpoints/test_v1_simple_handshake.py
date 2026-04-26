"""POST accept / confirm / withdraw-acceptance для Simple PaymentRequest."""

from unittest.mock import AsyncMock, patch
from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

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
_THIRD_TRON = "TQThirdSimpleHandshakeWallet8888888888"

SIMPLE_HANDSHAKE_ARBITER = "did:peer:handshake_arbiter"


def _v1() -> str:
    return f"/v1/arbiter/{quote(SIMPLE_HANDSHAKE_ARBITER, safe='')}"


@pytest_asyncio.fixture
async def main_app_handshake(test_db, test_redis, test_settings):
    owner = WalletUser(
        nickname="simple_hs_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:tron:simple_hs_owner",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    other = WalletUser(
        nickname="simple_hs_other",
        wallet_address=_OTHER_TRON,
        blockchain="tron",
        did="did:tron:simple_hs_other",
    )
    third = WalletUser(
        nickname="simple_hs_third",
        wallet_address=_THIRD_TRON,
        blockchain="tron",
        did="did:tron:simple_hs_third",
    )
    test_db.add(other)
    test_db.add(third)

    test_db.add(
        Wallet(
            name="arb_hs_test",
            encrypted_mnemonic="enc",
            role="arbiter",
            tron_address="TArbiterHandshakeTest11111111111",
            ethereum_address="0xcccccccccccccccccccccccccccccccccccccccc",
            owner_did=SIMPLE_HANDSHAKE_ARBITER,
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

    yield app, owner, other, third
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_accept_fixed_then_confirm_deal(main_app_handshake, test_db):
    app, owner, other, _third = main_app_handshake
    # Simulate prod mismatch:
    # payment_request stores did:tron:<address>, but wallet_users.did in DB is did:web:...
    owner.did = "did:web:escrow.ruswift.ru:simple_hs_owner"
    other.did = "did:web:escrow.ruswift.ru:simple_hs_other"
    test_db.add(owner)
    test_db.add(other)
    await test_db.commit()
    await test_db.refresh(owner)
    await test_db.refresh(other)
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "CNY",
            "amount": "100",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "14",
            "side": "receive",
        },
    }
    with patch("services.payment_request.NotifyService") as NS:
        ns = NS.return_value
        ns._language_for_scope = AsyncMock(return_value="ru")
        ns.notify_roles = AsyncMock()
        ns.send_message = AsyncMock()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # Override auth DID to did:tron:<address> so PaymentRequest keeps did:tron in DB.
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=f"did:tron:{_OWNER_TRON}",
            )
            c = await client.post(_v1() + "/payment-requests", json=payload)
            assert c.status_code == 201, c.text
            pk = c.json()["payment_request"]["pk"]

            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OTHER_TRON,
                did=f"did:tron:{_OTHER_TRON}",
            )
            a = await client.post(
                _v1() + f"/payment-requests/{pk}/accept",
                json={},
            )
            assert a.status_code == 200, a.text
            pr = a.json()["payment_request"]
            assert pr["owner_confirm_pending"] is True
            assert pr["counterparty_accept_did"] == f"did:tron:{_OTHER_TRON}"
            assert pr.get("counter_leg_snapshot_json") is None

            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=f"did:tron:{_OWNER_TRON}",
            )
            cf = await client.post(_v1() + f"/payment-requests/{pk}/confirm", json={})
            assert cf.status_code == 200, cf.text
            body = cf.json()
            assert body.get("deal_uid")
            assert body["payment_request"]["deal_id"] is not None
            # resolve by PR pk/public_ref should now return deal_only once deal_id exists
            pref = body["payment_request"]["public_ref"]
            rr = await client.get(_v1() + f"/resolve/{pref}")
            assert rr.status_code == 200, rr.text
            rb = rr.json()
            assert rb["kind"] == "deal_only"
            assert rb.get("deal") and rb["deal"].get("uid")
            assert rb.get("payment_request_pk") == pk
            assert rb.get("payment_request_public_ref") == pref
            assert rb.get("payment_request") is not None
            assert rb["payment_request"]["pk"] == pk
            assert rb["deal"].get("signers") is not None
            deal_pk = int(body["payment_request"]["deal_id"])
            res_deal = await test_db.execute(select(Deal).where(Deal.pk == deal_pk))
            deal_row = res_deal.scalar_one()
            assert deal_row.signers is not None
            sig = deal_row.signers
            # direction == fiat_to_stable: acceptor (other) deposits stable, owner receives stable
            assert deal_row.sender_did == f"did:tron:{_OTHER_TRON}"
            assert deal_row.receiver_did == f"did:tron:{_OWNER_TRON}"
            assert sig["sender"]["address"] == _OTHER_TRON
            assert sig["receiver"]["address"] == _OWNER_TRON
            assert sig["arbiter"]["address"] == "TArbiterHandshakeTest11111111111"
            assert sig["sender"]["blockchain"] == "tron"
            assert sig["receiver"]["blockchain"] == "tron"
            assert sig["arbiter"]["blockchain"] == "tron"

        assert ns.notify_roles.await_count >= 2


@pytest.mark.asyncio
async def test_second_counterparty_409(main_app_handshake):
    app, owner, other, third = main_app_handshake
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "EUR",
            "amount": "50",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "55",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_v1() + "/payment-requests", json=payload)
        pk = c.json()["payment_request"]["pk"]

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        assert (
            await client.post(_v1() + f"/payment-requests/{pk}/accept", json={})
        ).status_code == 200

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_THIRD_TRON,
            did=third.did,
        )
        x = await client.post(_v1() + f"/payment-requests/{pk}/accept", json={})
        assert x.status_code == 409


@pytest.mark.asyncio
async def test_withdraw_discussed_restores_counter_leg(main_app_handshake):
    app, owner, other, _ = main_app_handshake
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "USD",
            "amount": "200",
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
    with patch("services.payment_request.NotifyService") as NS:
        ns = NS.return_value
        ns._language_for_scope = AsyncMock(return_value="ru")
        ns.notify_roles = AsyncMock()
        ns.send_message = AsyncMock()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            c = await client.post(_v1() + "/payment-requests", json=payload)
            pk = c.json()["payment_request"]["pk"]

            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OTHER_TRON,
                did=other.did,
            )
            a = await client.post(
                _v1() + f"/payment-requests/{pk}/accept",
                json={"counter_stable_amount": "25"},
            )
            assert a.status_code == 200, a.text
            assert a.json()["payment_request"]["counter_leg"]["amount"] == "25"
            assert a.json()["payment_request"]["counter_leg"]["amount_discussed"] is False

            w = await client.post(
                _v1() + f"/payment-requests/{pk}/withdraw-acceptance",
                json={},
            )
            assert w.status_code == 200, w.text
            cl = w.json()["payment_request"]["counter_leg"]
            assert cl.get("amount_discussed") is True

        assert ns.notify_roles.await_count >= 2


@pytest.mark.asyncio
async def test_withdraw_wrong_did_403(main_app_handshake):
    app, owner, other, third = main_app_handshake
    payload = {
        "direction": "stable_to_fiat",
        "primary_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "10",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "fiat",
            "code": "USD",
            "amount": "9",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_v1() + "/payment-requests", json=payload)
        pk = c.json()["payment_request"]["pk"]
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        await client.post(_v1() + f"/payment-requests/{pk}/accept", json={})

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_THIRD_TRON,
            did=third.did,
        )
        r = await client.post(
            _v1() + f"/payment-requests/{pk}/withdraw-acceptance",
            json={},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_withdraw_after_confirm_400(main_app_handshake):
    app, owner, other, _ = main_app_handshake
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "CNY",
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
        c = await client.post(_v1() + "/payment-requests", json=payload)
        pk = c.json()["payment_request"]["pk"]
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        await client.post(_v1() + f"/payment-requests/{pk}/accept", json={})
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OWNER_TRON,
            did=owner.did,
        )
        await client.post(_v1() + f"/payment-requests/{pk}/confirm", json={})

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        r = await client.post(
            _v1() + f"/payment-requests/{pk}/withdraw-acceptance",
            json={},
        )
        assert r.status_code == 400
