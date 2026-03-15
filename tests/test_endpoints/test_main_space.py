"""
API-тесты маршрута GET /{space} main-приложения: доступ по JWT и проверка space в списке.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from db.models import WalletUser
from web.main import create_app
from web.endpoints.dependencies import (
    MAIN_AUTH_TOKEN_COOKIE,
    get_redis,
    get_settings,
    ResolvedSettings,
)

try:
    from tronpy.keys import PrivateKey
except ImportError:
    PrivateKey = None


def _tron_key_and_address():
    if PrivateKey is None:
        pytest.skip("tronpy not installed")
    priv = PrivateKey.from_passphrase(b"test-main-space-wallet")
    addr = priv.public_key.to_base58check_address()
    return priv, addr


def _tron_sign_message(priv_key, message: str) -> str:
    return priv_key.sign_msg(message.encode("utf-8")).hex()


@pytest_asyncio.fixture
async def main_app(test_db, test_redis, test_settings):
    """Main app с подменёнными БД, Redis и настройками."""
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


@pytest.mark.asyncio
async def test_get_space_without_auth_401_or_403(main_app):
    """GET /{space} без Authorization возвращает 401 или 403 (Forbidden)."""
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        r = await client.get("/any_space")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_verify_sets_cookie_with_jwt(main_app, test_db):
    """POST /v1/auth/tron/verify при успехе возвращает Set-Cookie с JWT (main_auth_token)."""
    priv, tron_address = _tron_key_and_address()
    user = WalletUser(
        wallet_address=tron_address,
        blockchain="tron",
        did="did:tron:" + tron_address,
        nickname="test_cookie",
    )
    test_db.add(user)
    await test_db.flush()
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/auth/tron/nonce",
            json={"wallet_address": tron_address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]
        signature = _tron_sign_message(priv, message)
        verify_r = await client.post(
            "/v1/auth/tron/verify",
            json={
                "wallet_address": tron_address,
                "signature": signature,
                "message": message,
            },
        )
    assert verify_r.status_code == 200
    token = verify_r.json()["token"]
    assert token

    set_cookie = verify_r.headers.get("set-cookie") or verify_r.headers.get("Set-Cookie") or ""
    assert f"{MAIN_AUTH_TOKEN_COOKIE}=" in set_cookie
    assert token in set_cookie


@pytest.mark.asyncio
async def test_get_space_with_cookie_auth_200(main_app, test_db):
    """GET /{space} с авторизацией только по cookie (без Bearer) возвращает 200 и HTML."""
    priv, tron_address = _tron_key_and_address()
    user = WalletUser(
        wallet_address=tron_address,
        blockchain="tron",
        did="did:tron:" + tron_address,
        nickname="cookie_space",
    )
    test_db.add(user)
    await test_db.flush()
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/auth/tron/nonce",
            json={"wallet_address": tron_address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]
        signature = _tron_sign_message(priv, message)
        verify_r = await client.post(
            "/v1/auth/tron/verify",
            json={
                "wallet_address": tron_address,
                "signature": signature,
                "message": message,
            },
        )
        assert verify_r.status_code == 200
        token = verify_r.json()["token"]
        assert "cookie_space" in verify_r.json().get("spaces", [])

        r = await client.get(
            "/cookie_space",
            headers={"Cookie": f"{MAIN_AUTH_TOKEN_COOKIE}={token}"},
        )
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert b"cookie_space" in r.content or b"app-main" in r.content


@pytest.mark.asyncio
async def test_get_space_with_valid_token_and_space_200(main_app, test_db):
    """GET /{space} с валидным JWT и space в списке пользователя возвращает 200 и HTML."""
    priv, tron_address = _tron_key_and_address()
    user = WalletUser(
        wallet_address=tron_address,
        blockchain="tron",
        did="did:tron:" + tron_address,
        nickname="test_space_page",
    )
    test_db.add(user)
    await test_db.flush()
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/auth/tron/nonce",
            json={"wallet_address": tron_address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]
        signature = _tron_sign_message(priv, message)
        verify_r = await client.post(
            "/v1/auth/tron/verify",
            json={
                "wallet_address": tron_address,
                "signature": signature,
                "message": message,
            },
        )
    assert verify_r.status_code == 200
    token = verify_r.json()["token"]
    assert "test_space_page" in verify_r.json().get("spaces", [])

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/test_space_page",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert b"test_space_page" in r.content or b"app-main" in r.content


@pytest.mark.asyncio
async def test_get_space_not_in_allowed_redirects_to_root(main_app, test_db):
    """GET /{space} с валидным JWT, но space не в списке пользователя — редирект на /."""
    priv, tron_address = _tron_key_and_address()
    user = WalletUser(
        wallet_address=tron_address,
        blockchain="tron",
        did="did:tron:" + tron_address,
        nickname="my_space",
    )
    test_db.add(user)
    await test_db.flush()
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        nonce_r = await client.post(
            "/v1/auth/tron/nonce",
            json={"wallet_address": tron_address},
        )
        message = nonce_r.json()["message"]
        signature = _tron_sign_message(priv, message)
        verify_r = await client.post(
            "/v1/auth/tron/verify",
            json={"wallet_address": tron_address, "signature": signature, "message": message},
        )
    token = verify_r.json()["token"]

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        r = await client.get(
            "/other_space_not_mine",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 302
    assert r.headers.get("location") == "/"
