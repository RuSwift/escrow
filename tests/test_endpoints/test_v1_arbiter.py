"""
API-тесты эндпоинтов арбитра: GET /v1/arbiter/addresses (нормализация нескольких активных).
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from db import get_db
from db.models import Wallet
from web.node import create_app
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings
from services.admin import AdminService

try:
    from tronpy.keys import PrivateKey
except ImportError:
    PrivateKey = None

VALID_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
OTHER_MNEMONIC = "legal winner thank year wave sausage worth useful legal winner thank yellow"


def _tron_key_and_address():
    if PrivateKey is None:
        pytest.skip("tronpy not installed")
    priv = PrivateKey.from_passphrase(b"test-arbiter-api")
    addr = priv.public_key.to_base58check_address()
    return priv, addr


def _tron_sign_message(priv_key, message: str) -> str:
    return priv_key.sign_msg(message.encode("utf-8")).hex()


@pytest_asyncio.fixture
async def arbiter_app(test_db, test_redis, test_settings):
    """Приложение с подменёнными deps и админом в whitelist."""
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


async def _get_admin_token(arbiter_app):
    """Получить JWT админа через TRON nonce + verify."""
    priv, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=arbiter_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post(
            "/v1/admin/tron/nonce",
            json={"tron_address": tron_address},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]
        sig = _tron_sign_message(priv, message)
        verify_r = await client.post(
            "/v1/admin/tron/verify",
            json={"tron_address": tron_address, "signature": sig, "message": message},
        )
        assert verify_r.status_code == 200
        return verify_r.json()["token"]


@pytest.mark.asyncio
async def test_arbiter_addresses_requires_admin(arbiter_app):
    """GET /v1/arbiter/addresses без авторизации возвращает 401."""
    async with AsyncClient(
        transport=ASGITransport(app=arbiter_app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/arbiter/addresses")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_arbiter_addresses_list_normalizes_multiple_active(arbiter_app, test_db):
    """
    Если в БД два арбитра с role='arbiter', GET /v1/arbiter/addresses нормализует:
    остаётся один активный (с минимальным id), в ответе ровно один is_active=true.
    """
    token = await _get_admin_token(arbiter_app)
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(
        transport=ASGITransport(app=arbiter_app),
        base_url="http://test",
    ) as client:
        create1 = await client.post(
            "/v1/arbiter/addresses",
            headers=headers,
            json={"name": "First", "mnemonic": VALID_MNEMONIC},
        )
        assert create1.status_code == 201
        id1 = create1.json()["id"]

        create2 = await client.post(
            "/v1/arbiter/addresses",
            headers=headers,
            json={"name": "Second", "mnemonic": OTHER_MNEMONIC},
        )
        assert create2.status_code == 201
        id2 = create2.json()["id"]

    # Искусственно делаем оба активными (как при сбое/гонке)
    await test_db.execute(
        update(Wallet).where(Wallet.id == id1).values(role="arbiter")
    )
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=arbiter_app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/arbiter/addresses", headers=headers)
    assert r.status_code == 200
    data = r.json()
    addresses = data.get("addresses", [])
    assert len(addresses) == 2
    active_count = sum(1 for a in addresses if a.get("is_active") is True)
    assert active_count == 1, "должен быть ровно один активный после нормализации"
    active = next(a for a in addresses if a["is_active"])
    assert active["id"] == id1, "активным оставляем запись с меньшим id"
