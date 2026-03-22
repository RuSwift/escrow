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
