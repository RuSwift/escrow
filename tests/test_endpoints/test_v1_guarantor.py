"""
Интеграционные тесты /v1/spaces/{space}/guarantor: только owner, профиль, направления.
"""
import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from db import get_db
from db.models import WalletUser
from web.main import create_app
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings

try:
    from tronpy.keys import PrivateKey
except ImportError:
    PrivateKey = None


def _tron_key_and_address(passphrase: bytes):
    if PrivateKey is None:
        pytest.skip("tronpy not installed")
    priv = PrivateKey.from_passphrase(passphrase)
    addr = priv.public_key.to_base58check_address()
    return priv, addr


def _tron_sign_message(priv_key, message: str) -> str:
    return priv_key.sign_msg(message.encode("utf-8")).hex()


@pytest_asyncio.fixture
async def main_app(test_db, test_redis, test_settings):
    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        return ResolvedSettings(
            settings=test_settings,
            has_key=False,
            is_admin_configured=False,
            is_node_initialized=False,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    yield app
    app.dependency_overrides.clear()


async def _verify_tron(client, priv, tron_address: str) -> str:
    nonce_r = await client.post(
        "/v1/auth/tron/nonce",
        json={"wallet_address": tron_address},
    )
    assert nonce_r.status_code == 200
    message = nonce_r.json()["message"]
    sig = _tron_sign_message(priv, message)
    verify_r = await client.post(
        "/v1/auth/tron/verify",
        json={
            "wallet_address": tron_address,
            "signature": sig,
            "message": message,
        },
    )
    assert verify_r.status_code == 200
    return verify_r.json()["token"]


@pytest.mark.asyncio
async def test_guarantor_get_requires_auth(main_app):
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/spaces/any/guarantor")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_guarantor_owner_get_ensures_profile_default_commission(main_app, test_db):
    priv, tron_address = _tron_key_and_address(b"guarantor-test-owner-a")
    space = "g_space_one"
    test_db.add(
        WalletUser(
            wallet_address=tron_address,
            blockchain="tron",
            did="did:tron:" + tron_address,
            nickname=space,
            is_verified=True,
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv, tron_address)
        r = await client.get(
            f"/v1/spaces/{space}/guarantor",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["is_verified"] is True
    assert Decimal(str(data["profile"]["commission_percent"])) == Decimal("0.1")
    assert data["directions"] == []


@pytest.mark.asyncio
async def test_guarantor_patch_commission_below_min_400(main_app, test_db):
    priv, tron_address = _tron_key_and_address(b"guarantor-test-owner-b")
    space = "g_space_two"
    test_db.add(
        WalletUser(
            wallet_address=tron_address,
            blockchain="tron",
            did="did:tron:" + tron_address,
            nickname=space,
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv, tron_address)
        r = await client.patch(
            f"/v1/spaces/{space}/guarantor/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={"commission_percent": 0.05},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_guarantor_patch_commission_ok(main_app, test_db):
    priv, tron_address = _tron_key_and_address(b"guarantor-test-owner-c")
    space = "g_space_three"
    test_db.add(
        WalletUser(
            wallet_address=tron_address,
            blockchain="tron",
            did="did:tron:" + tron_address,
            nickname=space,
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv, tron_address)
        r = await client.patch(
            f"/v1/spaces/{space}/guarantor/profile",
            headers={"Authorization": f"Bearer {token}"},
            json={"commission_percent": 2.5},
        )
    assert r.status_code == 200
    assert Decimal(str(r.json()["commission_percent"])) == Decimal("2.5")


@pytest.mark.asyncio
async def test_guarantor_non_owner_403(main_app, test_db):
    priv_owner, addr_owner = _tron_key_and_address(b"guarantor-owner-d")
    priv_other, addr_other = _tron_key_and_address(b"guarantor-other-d")
    space = "g_space_owner_only"
    test_db.add(
        WalletUser(
            wallet_address=addr_owner,
            blockchain="tron",
            did="did:tron:" + addr_owner,
            nickname=space,
        )
    )
    test_db.add(
        WalletUser(
            wallet_address=addr_other,
            blockchain="tron",
            did="did:tron:" + addr_other,
            nickname="other_nick",
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token_other = await _verify_tron(client, priv_other, addr_other)
        r = await client.get(
            f"/v1/spaces/{space}/guarantor",
            headers={"Authorization": f"Bearer {token_other}"},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_guarantor_directions_create_and_delete(main_app, test_db):
    priv, tron_address = _tron_key_and_address(b"guarantor-test-owner-e")
    space = "g_space_crud"
    test_db.add(
        WalletUser(
            wallet_address=tron_address,
            blockchain="tron",
            did="did:tron:" + tron_address,
            nickname=space,
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv, tron_address)
        headers = {"Authorization": f"Bearer {token}"}
        post_r = await client.post(
            f"/v1/spaces/{space}/guarantor/directions",
            headers=headers,
            json={
                "currency_code": "CNY",
                "payment_code": "ALIPAY",
                "payment_name": "Alipay",
                "conditions_text": "Test",
                "sort_order": 0,
            },
        )
        assert post_r.status_code == 200
        direction_id = post_r.json()["id"]

        get_r = await client.get(
            f"/v1/spaces/{space}/guarantor",
            headers=headers,
        )
        assert get_r.status_code == 200
        dirs = get_r.json()["directions"]
        assert len(dirs) == 1
        assert dirs[0]["currency_code"] == "CNY"
        assert dirs[0]["payment_code"] == "ALIPAY"

        del_r = await client.delete(
            f"/v1/spaces/{space}/guarantor/directions/{direction_id}",
            headers=headers,
        )
        assert del_r.status_code == 204

        get2 = await client.get(
            f"/v1/spaces/{space}/guarantor",
            headers=headers,
        )
        assert get2.json()["directions"] == []


@pytest.mark.asyncio
async def test_guarantor_patch_direction_conditions(main_app, test_db):
    priv, tron_address = _tron_key_and_address(b"guarantor-test-owner-patch-dir")
    space = "g_space_patch_dir"
    test_db.add(
        WalletUser(
            wallet_address=tron_address,
            blockchain="tron",
            did="did:tron:" + tron_address,
            nickname=space,
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv, tron_address)
        headers = {"Authorization": f"Bearer {token}"}
        post_r = await client.post(
            f"/v1/spaces/{space}/guarantor/directions",
            headers=headers,
            json={
                "currency_code": "USD",
                "payment_code": "CARD",
                "payment_name": "Card",
                "conditions_text": "Original",
                "sort_order": 0,
            },
        )
        assert post_r.status_code == 200
        direction_id = post_r.json()["id"]

        patch_r = await client.patch(
            f"/v1/spaces/{space}/guarantor/directions/{direction_id}",
            headers=headers,
            json={"conditions_text": "Updated terms"},
        )
        assert patch_r.status_code == 200
        assert patch_r.json()["conditions_text"] == "Updated terms"
        assert patch_r.json()["currency_code"] == "USD"

        get_r = await client.get(f"/v1/spaces/{space}/guarantor", headers=headers)
        assert get_r.status_code == 200
        assert get_r.json()["directions"][0]["conditions_text"] == "Updated terms"

        not_found = await client.patch(
            f"/v1/spaces/{space}/guarantor/directions/999999",
            headers=headers,
            json={"conditions_text": "x"},
        )
        assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_guarantor_direction_wildcard_all_methods_conflict(main_app, test_db):
    """payment_code '*' взаимоисключает с конкретными методами по той же валюте."""
    priv, tron_address = _tron_key_and_address(b"guarantor-test-owner-wild")
    space = "g_space_wildcard"
    test_db.add(
        WalletUser(
            wallet_address=tron_address,
            blockchain="tron",
            did="did:tron:" + tron_address,
            nickname=space,
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv, tron_address)
        headers = {"Authorization": f"Bearer {token}"}
        post_body = {
            "conditions_text": "Terms",
            "sort_order": 0,
        }

        r1 = await client.post(
            f"/v1/spaces/{space}/guarantor/directions",
            headers=headers,
            json={
                **post_body,
                "currency_code": "EUR",
                "payment_code": "ALIPAY",
                "payment_name": "Alipay",
            },
        )
        assert r1.status_code == 200

        r2 = await client.post(
            f"/v1/spaces/{space}/guarantor/directions",
            headers=headers,
            json={
                **post_body,
                "currency_code": "EUR",
                "payment_code": "*",
                "payment_name": None,
            },
        )
        assert r2.status_code == 400
        assert r2.json().get("detail", {}).get("code") == "all_methods_blocked_by_specific"

    priv2, tron2 = _tron_key_and_address(b"guarantor-test-owner-wild-b")
    space2 = "g_space_wildcard_b"
    test_db.add(
        WalletUser(
            wallet_address=tron2,
            blockchain="tron",
            did="did:tron:" + tron2,
            nickname=space2,
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv2, tron2)
        headers = {"Authorization": f"Bearer {token}"}
        post_body = {"conditions_text": "T", "sort_order": 0}

        ra = await client.post(
            f"/v1/spaces/{space2}/guarantor/directions",
            headers=headers,
            json={**post_body, "currency_code": "EUR", "payment_code": "*", "payment_name": "All"},
        )
        assert ra.status_code == 200

        rb = await client.post(
            f"/v1/spaces/{space2}/guarantor/directions",
            headers=headers,
            json={**post_body, "currency_code": "EUR", "payment_code": "SEPA", "payment_name": "SEPA"},
        )
        assert rb.status_code == 400
        assert rb.json().get("detail", {}).get("code") == "specific_blocked_by_all_methods"

    priv3, tron3 = _tron_key_and_address(b"guarantor-test-owner-wild-c")
    space3 = "g_space_wildcard_c"
    test_db.add(
        WalletUser(
            wallet_address=tron3,
            blockchain="tron",
            did="did:tron:" + tron3,
            nickname=space3,
        )
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv3, tron3)
        headers = {"Authorization": f"Bearer {token}"}
        post_body = {"conditions_text": "T", "sort_order": 0}

        rc = await client.post(
            f"/v1/spaces/{space3}/guarantor/directions",
            headers=headers,
            json={**post_body, "currency_code": "EUR", "payment_code": "*", "payment_name": None},
        )
        assert rc.status_code == 200
        rd = await client.post(
            f"/v1/spaces/{space3}/guarantor/directions",
            headers=headers,
            json={**post_body, "currency_code": "USD", "payment_code": "CARD", "payment_name": "Card"},
        )
        assert rd.status_code == 200

        r_dup = await client.post(
            f"/v1/spaces/{space3}/guarantor/directions",
            headers=headers,
            json={**post_body, "currency_code": "EUR", "payment_code": "*", "payment_name": None},
        )
        assert r_dup.status_code == 400
        assert r_dup.json().get("detail", {}).get("code") == "direction_already_exists"


@pytest.mark.asyncio
async def test_guarantor_patch_arbiter_public_slug_ok(main_app, test_db):
    priv, tron_address = _tron_key_and_address(b"guar-slug-ok-01")
    space = "g_space_slug_ok"
    test_db.add(
        WalletUser(
            wallet_address=tron_address,
            blockchain="tron",
            did="did:tron:guarslugok",
            nickname=space,
            is_verified=True,
        )
    )
    await test_db.commit()
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv, tron_address)
        headers = {"Authorization": f"Bearer {token}"}
        p = await client.patch(
            f"/v1/spaces/{space}/guarantor/profile",
            headers=headers,
            json={"arbiter_public_slug": "cool-arbiter-z9"},
        )
        assert p.status_code == 200, p.text
        assert p.json()["arbiter_public_slug"] == "cool-arbiter-z9"
        g = await client.get(f"/v1/spaces/{space}/guarantor", headers=headers)
        assert g.json()["profile"]["arbiter_public_slug"] == "cool-arbiter-z9"


@pytest.mark.asyncio
async def test_guarantor_patch_arbiter_public_slug_conflict(main_app, test_db):
    priv_a, addr_a = _tron_key_and_address(b"guar-slug-a-01")
    priv_b, addr_b = _tron_key_and_address(b"guar-slug-b-01")
    space_a = "g_space_slug_conf_a"
    space_b = "g_space_slug_conf_b"
    test_db.add(
        WalletUser(
            wallet_address=addr_a,
            blockchain="tron",
            did="did:tron:ga",
            nickname=space_a,
            is_verified=True,
        )
    )
    test_db.add(
        WalletUser(
            wallet_address=addr_b,
            blockchain="tron",
            did="did:tron:gb",
            nickname=space_b,
            is_verified=True,
        )
    )
    await test_db.commit()
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token_a = await _verify_tron(client, priv_a, addr_a)
        token_b = await _verify_tron(client, priv_b, addr_b)
        h_a = {"Authorization": f"Bearer {token_a}"}
        h_b = {"Authorization": f"Bearer {token_b}"}
        pa = await client.patch(
            f"/v1/spaces/{space_a}/guarantor/profile",
            headers=h_a,
            json={"arbiter_public_slug": "dup-slug-shared"},
        )
        assert pa.status_code == 200
        pb = await client.patch(
            f"/v1/spaces/{space_b}/guarantor/profile",
            headers=h_b,
            json={"arbiter_public_slug": "dup-slug-shared"},
        )
        assert pb.status_code == 400
        assert "taken" in str(pb.json().get("detail", "")).lower()


@pytest.mark.asyncio
async def test_guarantor_patch_arbiter_public_slug_invalid(main_app, test_db):
    priv, tron_address = _tron_key_and_address(b"guar-slug-inv-01")
    space = "g_space_slug_inv"
    test_db.add(
        WalletUser(
            wallet_address=tron_address,
            blockchain="tron",
            did="did:tron:guarsluginv",
            nickname=space,
            is_verified=True,
        )
    )
    await test_db.commit()
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        token = await _verify_tron(client, priv, tron_address)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.patch(
            f"/v1/spaces/{space}/guarantor/profile",
            headers=headers,
            json={"arbiter_public_slug": "!!"},
        )
        assert r.status_code == 400
