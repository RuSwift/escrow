"""
API-тесты авторизации через TRON: POST /v1/auth/tron/nonce, POST /v1/auth/tron/verify.
Успешный сценарий: nonce → подпись (tronpy) → verify → token; GET /v1/auth/tron/me.
Неуспешные: невалидный адрес — 400, неверная подпись / нет message — 401/400.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from web.node import create_app
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings

try:
    from tronpy.keys import PrivateKey
except ImportError:
    PrivateKey = None


def _tron_key_and_address():
    """Детерминированный TRON ключ и адрес для тестов (tronpy)."""
    if PrivateKey is None:
        pytest.skip("tronpy not installed")
    priv = PrivateKey.from_passphrase(b"test-auth-tron-wallet")
    addr = priv.public_key.to_base58check_address()
    return priv, addr


def _tron_sign_message(priv_key, message: str) -> str:
    """Подписать сообщение в формате TIP-191 (как tronpy.sign_msg). Возвращает hex подписи."""
    sig = priv_key.sign_msg(message.encode("utf-8"))
    return sig.hex()


@pytest_asyncio.fixture
async def auth_app(test_db, test_redis, test_settings):
    """Приложение с подменёнными БД, Redis и настройками (то же, что для Ethereum auth)."""
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


# --- POST /v1/auth/tron/nonce ---


@pytest.mark.asyncio
async def test_auth_tron_nonce_success(auth_app):
    """POST /v1/auth/tron/nonce с валидным TRON-адресом возвращает 200 и nonce, message."""
    _, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/auth/tron/nonce",
            json={"wallet_address": tron_address},
        )
    assert r.status_code == 200
    data = r.json()
    assert "nonce" in data
    assert "message" in data
    assert data["nonce"] in data["message"]


@pytest.mark.asyncio
async def test_auth_tron_nonce_invalid_address_400(auth_app):
    """POST /v1/auth/tron/nonce с невалидным адресом — 400."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/auth/tron/nonce",
            json={"wallet_address": "not-a-tron-address"},
        )
    assert r.status_code == 400


# --- POST /v1/auth/tron/verify + GET /v1/auth/tron/me ---


@pytest.mark.asyncio
async def test_auth_tron_verify_then_me_success(auth_app):
    """Полный сценарий: nonce → подпись (tronpy) → verify → 200 + token; GET /tron/me с Bearer → 200."""
    priv, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
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
    data = verify_r.json()
    assert "token" in data
    assert data["wallet_address"] == tron_address

    token = data["token"]
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        me_r = await client.get(
            "/v1/auth/tron/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert me_r.status_code == 200
    assert me_r.json()["wallet_address"] == tron_address


@pytest.mark.asyncio
async def test_auth_tron_verify_no_message_400(auth_app):
    """POST /v1/auth/tron/verify без message — 400."""
    _, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/auth/tron/verify",
            json={
                "wallet_address": tron_address,
                "signature": "0" * 130,
                "message": None,
            },
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_auth_tron_verify_invalid_signature_401(auth_app):
    """POST /v1/auth/tron/verify с неверной подписью — 401."""
    _, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/auth/tron/nonce",
            json={"wallet_address": tron_address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]

        r = await client.post(
            "/v1/auth/tron/verify",
            json={
                "wallet_address": tron_address,
                "signature": "0" * 130,
                "message": message,
            },
        )
    assert r.status_code == 401
    detail = (r.json().get("detail") or "").lower()
    assert "signature" in detail or "invalid" in detail
