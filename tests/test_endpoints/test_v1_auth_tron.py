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
    assert "spaces" in data
    assert isinstance(data["spaces"], list)
    assert data["spaces"] == []  # новый адрес — записей нет

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
    me_data = me_r.json()
    assert me_data["wallet_address"] == tron_address
    assert me_data.get("standard") == "tron"
    assert "did" in me_data
    assert "spaces" in me_data
    assert me_data["spaces"] == []


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


# --- POST /v1/auth/tron/init ---


@pytest.mark.asyncio
async def test_auth_tron_init_success(auth_app):
    """После verify (spaces пусты) POST /tron/init с nickname возвращает 200 и space; затем /me возвращает spaces с nickname."""
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
    token = verify_r.json()["token"]
    assert verify_r.json()["spaces"] == []

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        init_r = await client.post(
            "/v1/auth/tron/init",
            json={"nickname": "test_space_user"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert init_r.status_code == 200
    assert init_r.json().get("space") == "test_space_user"

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        me_r = await client.get(
            "/v1/auth/tron/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert me_r.status_code == 200
    assert "test_space_user" in me_r.json().get("spaces", [])


@pytest.mark.asyncio
async def test_auth_tron_init_when_spaces_exist_400(auth_app, test_db):
    """Если у кошелька уже есть spaces (WalletUser создан), init возвращает 400."""
    from db.models import WalletUser

    priv, tron_address = _tron_key_and_address()
    user = WalletUser(
        wallet_address=tron_address,
        blockchain="tron",
        did="did:tron:" + tron_address,
        nickname="existing_user",
    )
    test_db.add(user)
    await test_db.flush()
    await test_db.commit()

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
    assert "existing_user" in verify_r.json().get("spaces", [])
    token = verify_r.json()["token"]

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        init_r = await client.post(
            "/v1/auth/tron/init",
            json={"nickname": "another_nick"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert init_r.status_code == 400
    assert "already" in (init_r.json().get("detail") or "").lower() or "spaces" in (init_r.json().get("detail") or "").lower()


@pytest.mark.asyncio
async def test_auth_tron_init_nickname_taken_400(auth_app, test_db):
    """Init с nickname, который уже занят другим WalletUser, возвращает 400."""
    from db.models import WalletUser

    priv, tron_address = _tron_key_and_address()
    other = WalletUser(
        wallet_address="TAnotherAddr1234567890123456789012",
        blockchain="tron",
        did="did:tron:TAnotherAddr1234567890123456789012",
        nickname="taken_nick",
    )
    test_db.add(other)
    await test_db.flush()
    await test_db.commit()

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
    token = verify_r.json()["token"]

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        init_r = await client.post(
            "/v1/auth/tron/init",
            json={"nickname": "taken_nick"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert init_r.status_code == 400
    assert "taken" in (init_r.json().get("detail") or "").lower() or "nickname" in (init_r.json().get("detail") or "").lower()


@pytest.mark.asyncio
async def test_auth_tron_me_returns_standard_and_spaces(auth_app):
    """GET /tron/me возвращает standard, wallet_address, did, spaces (список)."""
    priv, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
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
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        me_r = await client.get(
            "/v1/auth/tron/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert me_r.status_code == 200
    data = me_r.json()
    assert data["standard"] == "tron"
    assert data["wallet_address"] == tron_address
    assert data["did"].startswith("did:")
    assert "spaces" in data
    assert isinstance(data["spaces"], list)


@pytest.mark.asyncio
async def test_auth_tron_me_x_space_header(auth_app):
    """GET /tron/me с заголовком X-Space возвращает space_nickname при валидном space."""
    priv, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
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
        init_r = await client.post(
            "/v1/auth/tron/init",
            json={"nickname": "my_space"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert init_r.status_code == 200
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as client:
        me_r = await client.get(
            "/v1/auth/tron/me",
            headers={"Authorization": f"Bearer {token}", "X-Space": "my_space"},
        )
    assert me_r.status_code == 200
    assert me_r.json().get("space_nickname") == "my_space"
    assert "my_space" in me_r.json().get("spaces", [])
