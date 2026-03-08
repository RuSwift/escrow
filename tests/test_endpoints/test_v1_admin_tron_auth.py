"""
Тесты авторизации админа через TRON: POST /v1/admin/tron/nonce, POST /v1/admin/tron/verify.
Успешный сценарий: whitelist-адрес получает nonce, подписывает (tronpy), verify возвращает token.
Неуспешные: не из whitelist — 403, неверная подпись / нет nonce в сообщении / повторное использование nonce — 401.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from web.node import create_app
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings
from services.admin import AdminService

try:
    from tronpy.keys import PrivateKey
except ImportError:
    PrivateKey = None


def _tron_key_and_address():
    """Детерминированный TRON ключ и адрес для тестов (tronpy)."""
    if PrivateKey is None:
        pytest.skip("tronpy not installed")
    priv = PrivateKey.from_passphrase(b"test-admin-tron-auth")
    addr = priv.public_key.to_base58check_address()
    return priv, addr


def _tron_sign_message(priv_key, message: str) -> str:
    """Подписать сообщение в формате TIP-191 (как tronpy.sign_msg). Возвращает hex подписи."""
    sig = priv_key.sign_msg(message.encode("utf-8"))
    return sig.hex()


@pytest_asyncio.fixture
async def admin_tron_app(test_db, test_redis, test_settings):
    """Приложение с подменёнными deps и одним TRON-адресом в whitelist админки."""
    app = create_app()
    _, tron_address = _tron_key_and_address()

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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings

    admin_svc = AdminService(session=test_db, redis=test_redis, settings=test_settings)
    await admin_svc.ensure_admin_exists()
    await admin_svc.add_tron_address(tron_address, label="Test admin")
    await test_db.commit()

    yield app
    app.dependency_overrides.clear()


# --- Успешная авторизация ---


@pytest.mark.asyncio
async def test_admin_tron_nonce_then_verify_success(admin_tron_app):
    """Whitelist-адрес: nonce -> подпись (tronpy) -> verify -> 200 и token."""
    priv, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=admin_tron_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/admin/tron/nonce",
            json={"tron_address": tron_address},
        )
        assert nonce_r.status_code == 200
        data = nonce_r.json()
        message = data["message"]
        nonce = data["nonce"]
        assert nonce in message

        signature = _tron_sign_message(priv, message)
        verify_r = await client.post(
            "/v1/admin/tron/verify",
            json={
                "tron_address": tron_address,
                "signature": signature,
                "message": message,
            },
        )
    assert verify_r.status_code == 200
    verify_data = verify_r.json()
    assert verify_data.get("success") is True
    assert "token" in verify_data


@pytest.mark.asyncio
async def test_admin_tron_verify_token_usable(admin_tron_app):
    """После успешного verify токен даёт доступ к GET /v1/admin/info."""
    priv, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=admin_tron_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/admin/tron/nonce",
            json={"tron_address": tron_address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]
        signature = _tron_sign_message(priv, message)
        verify_r = await client.post(
            "/v1/admin/tron/verify",
            json={
                "tron_address": tron_address,
                "signature": signature,
                "message": message,
            },
        )
        assert verify_r.status_code == 200
        token = verify_r.json()["token"]

        info_r = await client.get(
            "/v1/admin/info",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert info_r.status_code == 200
    info = info_r.json()
    assert info.get("id") is not None
    assert info.get("tron_addresses_count", 0) >= 1


# --- Неуспешная: не из whitelist ---


@pytest.mark.asyncio
async def test_admin_tron_nonce_not_whitelisted_403(admin_tron_app):
    """POST /v1/admin/tron/nonce для адреса не из whitelist — 403."""
    other_address = "T" + "2" * 33
    async with AsyncClient(
        transport=ASGITransport(app=admin_tron_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/admin/tron/nonce",
            json={"tron_address": other_address},
        )
    assert r.status_code == 403
    assert "not authorized" in (r.json().get("detail") or "").lower()


@pytest.mark.asyncio
async def test_admin_tron_verify_not_whitelisted_403(admin_tron_app):
    """POST /v1/admin/tron/verify с адресом не из whitelist — 403 (даже с валидной подписью другого адреса)."""
    priv, _ = _tron_key_and_address()
    other_address = "T" + "2" * 33
    message = "Please sign this message to authenticate:\n\nNonce: abc123"
    signature = _tron_sign_message(priv, message)
    async with AsyncClient(
        transport=ASGITransport(app=admin_tron_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/admin/tron/verify",
            json={
                "tron_address": other_address,
                "signature": signature,
                "message": message,
            },
        )
    assert r.status_code == 403


# --- Неуспешная: подпись / nonce ---


@pytest.mark.asyncio
async def test_admin_tron_verify_invalid_signature_401(admin_tron_app):
    """verify с неверной подписью — 401."""
    _, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=admin_tron_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/admin/tron/nonce",
            json={"tron_address": tron_address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]

        r = await client.post(
            "/v1/admin/tron/verify",
            json={
                "tron_address": tron_address,
                "signature": "0x" + "00" * 65,
                "message": message,
            },
        )
    assert r.status_code == 401
    assert "signature" in (r.json().get("detail") or "").lower() or "invalid" in (r.json().get("detail") or "").lower()


@pytest.mark.asyncio
async def test_admin_tron_verify_message_without_nonce_401(admin_tron_app):
    """verify с сообщением без выданного nonce — 401."""
    priv, tron_address = _tron_key_and_address()
    message = "Please sign this message to authenticate:\n\nNonce: wrongnonce123"
    signature = _tron_sign_message(priv, message)
    async with AsyncClient(
        transport=ASGITransport(app=admin_tron_app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/admin/tron/verify",
            json={
                "tron_address": tron_address,
                "signature": signature,
                "message": message,
            },
        )
    assert r.status_code == 401
    assert "nonce" in (r.json().get("detail") or "").lower()


@pytest.mark.asyncio
async def test_admin_tron_verify_nonce_reuse_401(admin_tron_app):
    """Повторное использование одного nonce — второй verify возвращает 401."""
    priv, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=admin_tron_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/admin/tron/nonce",
            json={"tron_address": tron_address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]
        signature = _tron_sign_message(priv, message)

        verify1 = await client.post(
            "/v1/admin/tron/verify",
            json={
                "tron_address": tron_address,
                "signature": signature,
                "message": message,
            },
        )
        assert verify1.status_code == 200

        verify2 = await client.post(
            "/v1/admin/tron/verify",
            json={
                "tron_address": tron_address,
                "signature": signature,
                "message": message,
            },
        )
    assert verify2.status_code == 401
    assert "nonce" in (verify2.json().get("detail") or "").lower() or "already used" in (verify2.json().get("detail") or "").lower()
