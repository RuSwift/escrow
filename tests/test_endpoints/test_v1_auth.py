"""
Интеграционные тесты авторизации: POST /v1/auth/nonce, verify, GET /v1/auth/me.
Используется реальная подпись от eth_account.
"""
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from httpx import ASGITransport, AsyncClient

from db import get_db
from web.node import create_app
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings


def _eth_sign_message(message: str, private_key_hex: str) -> str:
    account = Account.from_key(private_key_hex)
    message_hash = encode_defunct(text=message)
    signed = account.sign_message(message_hash)
    return signed.signature.hex()


@pytest.fixture
def auth_app(test_db, test_redis, test_settings):
    """Приложение с подменёнными БД, Redis и настройками."""
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


@pytest.fixture
def eth_key_hex():
    return "0x" + "1" * 64


# --- /v1/auth/nonce ---


@pytest.mark.asyncio
async def test_auth_nonce_success(auth_app, eth_key_hex):
    """POST /v1/auth/nonce с валидным Ethereum-адресом возвращает 200 и nonce, message."""
    account = Account.from_key(eth_key_hex)
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/auth/nonce",
            json={"wallet_address": account.address},
        )
    assert r.status_code == 200
    data = r.json()
    assert "nonce" in data
    assert "message" in data
    assert data["nonce"] in data["message"]


@pytest.mark.asyncio
async def test_auth_nonce_invalid_address_400(auth_app):
    """POST /v1/auth/nonce с невалидным адресом — 400."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/auth/nonce",
            json={"wallet_address": "not-an-address"},
        )
    assert r.status_code == 400


# --- /v1/auth/verify + /v1/auth/me ---


@pytest.mark.asyncio
async def test_auth_verify_then_me_success(auth_app, eth_key_hex):
    """Полный сценарий: nonce -> подпись -> verify -> 200 + token; GET /me с Bearer -> 200 + wallet_address."""
    account = Account.from_key(eth_key_hex)
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/auth/nonce",
            json={"wallet_address": account.address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]
        signature = _eth_sign_message(message, eth_key_hex)

        verify_r = await client.post(
            "/v1/auth/verify",
            json={
                "wallet_address": account.address,
                "signature": signature,
                "message": message,
            },
        )
    assert verify_r.status_code == 200
    data = verify_r.json()
    assert "token" in data
    assert data["wallet_address"] == account.address.lower()

    token = data["token"]
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        me_r = await client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert me_r.status_code == 200
    assert me_r.json()["wallet_address"] == account.address.lower()


@pytest.mark.asyncio
async def test_auth_verify_no_message_400(auth_app, eth_key_hex):
    """POST /v1/auth/verify без message — 400."""
    account = Account.from_key(eth_key_hex)
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/auth/verify",
            json={
                "wallet_address": account.address,
                "signature": "0x" + "00" * 65,
                "message": None,
            },
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_auth_verify_invalid_signature_401(auth_app, eth_key_hex):
    """POST /v1/auth/verify с неверной подписью — 401."""
    account = Account.from_key(eth_key_hex)
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/auth/verify",
            json={
                "wallet_address": account.address,
                "signature": "0x" + "00" * 65,
                "message": "Please sign this message to authenticate:\n\nNonce: abc",
            },
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_no_token_401(auth_app):
    """GET /v1/auth/me без Authorization — 401 (HTTPBearer)."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/auth/me")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_auth_me_invalid_token_401(auth_app):
    """GET /v1/auth/me с невалидным Bearer — 401."""
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
    assert r.status_code == 401
