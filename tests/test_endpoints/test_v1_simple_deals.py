"""GET/POST /v1/arbiter/{arbiter_space_did}/payment-requests — Simple UI."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from core.utils import get_user_did
from db import get_db
from db.models import GuarantorProfile, PrimaryWallet, Wallet, WalletUser
from web.endpoints.dependencies import (
    UserInfo,
    get_arbiter_path_resolve_service,
    get_current_wallet_user,
    get_redis,
    get_settings,
    ResolvedSettings,
)
from web.main import create_app
from services.arbiter_path import ArbiterPathResolveService

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"
_OTHER_TRON = "TP8PmmcgrTv1ASwJ7UPe8fDCmbUtTYLxnd"

# Совпадает с owner_did кошелька-арбитра в фикстуре (Wallet).
SIMPLE_ARBITER_DID = "did:peer:simple_deals_arbiter_owner"

SIMPLE_ARBITER_SLUG = "slugforsimple"
SIMPLE_ARBITER_DID_FROM_PRIMARY = get_user_did(_OWNER_TRON, "tron")


def _simple_v1_base() -> str:
    return f"/v1/arbiter/{quote(SIMPLE_ARBITER_DID, safe='')}"


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
        PrimaryWallet(
            wallet_user_id=owner.id,
            address=_OWNER_TRON,
            blockchain="tron",
        )
    )
    test_db.add(
        GuarantorProfile(
            wallet_user_id=owner.id,
            space=owner.nickname,
            commission_percent=Decimal("0.1"),
            arbiter_public_slug=SIMPLE_ARBITER_SLUG,
        )
    )
    await test_db.commit()

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

    async def override_get_arbiter_path_resolve_service():
        return ArbiterPathResolveService(test_db, test_redis, test_settings)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_wallet_user] = override_current_user
    app.dependency_overrides[get_arbiter_path_resolve_service] = override_get_arbiter_path_resolve_service

    yield app, owner
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_payment_requests_empty_200(main_app_simple_deals):
    app, _owner = main_app_simple_deals
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get(f"/v1/arbiter/{SIMPLE_ARBITER_SLUG}/payment-requests")
        assert r.status_code == 200
        assert r.json()["items"] == []

        r = await client.get(_simple_v1_base() + "/payment-requests")
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
        c = await client.post(_simple_v1_base() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["payment_request"]
        assert created["uid"]
        assert created["public_ref"]
        assert len(created["public_ref"]) == 9
        assert set(created["commissioners"].keys()) <= {"system"}
        assert created["pair_label"]
        assert "RUB" in created["pair_label"]
        assert created["heading"] is None
        assert created["expires_at"] is not None
        exp = datetime.fromisoformat(created["expires_at"].replace("Z", "+00:00"))
        assert exp > datetime.now(timezone.utc)
        assert created["space_id"] == owner.id
        assert created["space_nickname"] == "simple_api_space"
        assert created["arbiter_did"] == SIMPLE_ARBITER_DID
        assert created["owner_did"] == owner.did

        r = await client.get(_simple_v1_base() + "/payment-requests")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] >= 1
        uids = {it["uid"] for it in body["items"]}
        assert created["uid"] in uids
        assert all(it.get("arbiter_did") == SIMPLE_ARBITER_DID for it in body["items"])

        r2 = await client.get(_simple_v1_base() + "/payment-requests?q=RUB")
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
        c = await client.post(_simple_v1_base() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["payment_request"]
        assert created["heading"] == "Тестовый заголовок"
        assert created["expires_at"] is None
        assert created["space_id"] == owner.id

        r = await client.get(_simple_v1_base() + "/payment-requests?q=Тестовый")
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
        c = await client.post(_simple_v1_base() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["payment_request"]
        assert created["expires_at"] is not None
        exp = datetime.fromisoformat(created["expires_at"].replace("Z", "+00:00"))
        delta = exp - datetime.now(timezone.utc)
        assert timedelta(hours=47) < delta < timedelta(hours=49)


@pytest.mark.asyncio
async def test_list_payment_requests_commissioner_has_borrow_amounts(main_app_simple_deals):
    """
    UI variant-B needs escrow total in list view (base + fees).
    For that, list endpoint must include commissioners slots with borrow_amount for system+intermediary.
    """
    app, owner = main_app_simple_deals

    # Create another user (commissioner) in DB for completeness.
    async for s in app.dependency_overrides[get_db]():
        other = WalletUser(
            nickname="simple_api_other",
            wallet_address=_OTHER_TRON,
            blockchain="tron",
            did="did:tron:simple_api_other",
        )
        s.add(other)
        await s.commit()
        await s.refresh(other)
        s.add(
            PrimaryWallet(
                wallet_user_id=other.id,
                address=_OTHER_TRON,
                blockchain="tron",
            )
        )
        await s.commit()

    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "CNY",
            "amount": "10000",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "100",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # owner creates payment request
        c = await client.post(_simple_v1_base() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["payment_request"]
        uid = created["uid"]
        pk = created["pk"]

        # switch to other (commissioner) and create intermediary slot with 0.8%
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did="did:tron:simple_api_other",
        )
        try:
            rs = await client.post(
                _simple_v1_base() + f"/payment-requests/{uid}/resell",
                json={"intermediary_percent": "0.8"},
            )
            assert rs.status_code == 200, rs.text

            # list should include borrow_amount for system+intermediary
            r = await client.get(_simple_v1_base() + "/payment-requests")
            assert r.status_code == 200, r.text
            items = r.json()["items"]
            it = next(x for x in items if x["pk"] == pk)
            comm = it["commissioners"]
            assert "system" in comm
            assert comm["system"].get("borrow_amount")
            # find intermediary slot for other did
            i_slots = [
                s for s in comm.values() if isinstance(s, dict) and s.get("role") == "intermediary"
            ]
            assert any(s.get("did") == "did:tron:simple_api_other" for s in i_slots)
            mine = next(s for s in i_slots if s.get("did") == "did:tron:simple_api_other")
            assert mine.get("borrow_amount")
            assert mine.get("commission", {}).get("value") == "0.8"
        finally:
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=owner.did,
            )


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
        c = await client.post(_simple_v1_base() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        pk = c.json()["payment_request"]["pk"]

        d = await client.post(
            f"{_simple_v1_base()}/payment-requests/{pk}/deactivate",
            json={"confirm_pk": str(pk)},
        )
        assert d.status_code == 200, d.text
        body = d.json()["payment_request"]
        assert body["deactivated_at"] is not None

        lst = await client.get(_simple_v1_base() + "/payment-requests")
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
        c = await client.post(_simple_v1_base() + "/payment-requests", json=payload)
        pk = c.json()["payment_request"]["pk"]
        d = await client.post(
            f"{_simple_v1_base()}/payment-requests/{pk}/deactivate",
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
        c = await client.post(_simple_v1_base() + "/payment-requests", json=payload)
        pk = c.json()["payment_request"]["pk"]
        first = await client.post(
            f"{_simple_v1_base()}/payment-requests/{pk}/deactivate",
            json={"confirm_pk": str(pk)},
        )
        assert first.status_code == 200
        second = await client.post(
            f"{_simple_v1_base()}/payment-requests/{pk}/deactivate",
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
            f"{_simple_v1_base()}/payment-requests/999999999/deactivate",
            json={"confirm_pk": "999999999"},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_arbiter_unknown_slug_list_404(main_app_simple_deals):
    app, _owner = main_app_simple_deals
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/arbiter/no-such-slug-xyz99/payment-requests")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_payment_request_via_arbiter_public_slug(main_app_simple_deals):
    app, owner = main_app_simple_deals
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "CHF",
            "amount": "200",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "5",
            "side": "receive",
        },
    }
    base_slug = f"/v1/arbiter/{SIMPLE_ARBITER_SLUG}"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(base_slug + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        created = c.json()["payment_request"]
        # В v1_simple_deals.py:30 SIMPLE_ARBITER_DID_FROM_PRIMARY = get_user_did(_OWNER_TRON, "tron")
        # Но в main_app_simple_deals фикстуре DID владельца задан как "did:tron:simple_api_space_owner"
        # Сервис PaymentRequestService._get_arbiter_commission_info использует DID арбитра для поиска профиля.
        # В тесте мы передаем SIMPLE_ARBITER_SLUG, который привязан к owner.
        # В ответе arbiter_did должен соответствовать DID того, кто является арбитром для этого слага.
        assert created["arbiter_did"] == owner.did
        assert created["space_id"] == owner.id

        lst = await client.get(base_slug + "/payment-requests")
        assert lst.status_code == 200
        uids = {it["uid"] for it in lst.json()["items"]}
        assert created["uid"] in uids
