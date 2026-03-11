"""
API-тесты эндпоинтов пользователей (admin): GET/POST /v1/users, GET/PATCH/DELETE /v1/users/{id},
POST balance, GET billing, GET did-document.
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

WALLET_TRON = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
WALLET_ETH = "0x1234567890123456789012345678901234567890"


def _tron_key_and_address():
    if PrivateKey is None:
        pytest.skip("tronpy not installed")
    priv = PrivateKey.from_passphrase(b"test-users-api")
    addr = priv.public_key.to_base58check_address()
    return priv, addr


def _tron_sign_message(priv_key, message: str) -> str:
    return priv_key.sign_msg(message.encode("utf-8")).hex()


@pytest_asyncio.fixture
async def users_app(test_db, test_redis, test_settings):
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


async def _get_admin_token(users_app):
    """Получить JWT админа через TRON nonce + verify."""
    priv, tron_address = _tron_key_and_address()
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
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
async def test_users_list_requires_admin(users_app):
    """GET /v1/users без авторизации возвращает 401."""
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/users")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_users_list_empty_with_admin(users_app):
    """GET /v1/users с админ-токеном возвращает пустой список."""
    token = await _get_admin_token(users_app)
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        r = await client.get(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data.get("users") == []
    assert data.get("total") == 0


@pytest.mark.asyncio
async def test_users_create_and_list(users_app):
    """POST /v1/users создаёт пользователя, GET /v1/users возвращает его."""
    token = await _get_admin_token(users_app)
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        create_r = await client.post(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "wallet_address": WALLET_TRON,
                "blockchain": "tron",
                "nickname": "alice",
                "is_verified": False,
                "access_to_admin_panel": False,
            },
        )
    assert create_r.status_code == 201
    created = create_r.json()
    assert created["nickname"] == "alice"
    assert created["wallet_address"] == WALLET_TRON
    assert "id" in created

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        list_r = await client.get(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert list_r.status_code == 200
    data = list_r.json()
    assert data["total"] == 1
    assert len(data["users"]) == 1
    assert data["users"][0]["id"] == created["id"]


@pytest.mark.asyncio
async def test_users_get_by_id(users_app):
    """GET /v1/users/{id} возвращает пользователя."""
    token = await _get_admin_token(users_app)
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        create_r = await client.post(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "wallet_address": WALLET_TRON,
                "blockchain": "tron",
                "nickname": "bob",
            },
        )
    assert create_r.status_code == 201
    uid = create_r.json()["id"]

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        get_r = await client.get(
            f"/v1/users/{uid}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert get_r.status_code == 200
    assert get_r.json()["nickname"] == "bob"


@pytest.mark.asyncio
async def test_users_patch(users_app):
    """PATCH /v1/users/{id} обновляет nickname, is_verified, access_to_admin_panel."""
    token = await _get_admin_token(users_app)
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        create_r = await client.post(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "wallet_address": WALLET_TRON,
                "blockchain": "tron",
                "nickname": "bob",
            },
        )
    assert create_r.status_code == 201
    uid = create_r.json()["id"]

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        patch_r = await client.patch(
            f"/v1/users/{uid}",
            headers={"Authorization": f"Bearer {token}"},
            json={"nickname": "bob_updated", "is_verified": True},
        )
    assert patch_r.status_code == 200
    data = patch_r.json()
    assert data["nickname"] == "bob_updated"
    assert data["is_verified"] is True


@pytest.mark.asyncio
async def test_users_delete(users_app):
    """DELETE /v1/users/{id} удаляет пользователя."""
    token = await _get_admin_token(users_app)
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        create_r = await client.post(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "wallet_address": WALLET_TRON,
                "blockchain": "tron",
                "nickname": "to_delete",
            },
        )
    assert create_r.status_code == 201
    uid = create_r.json()["id"]

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        del_r = await client.delete(
            f"/v1/users/{uid}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert del_r.status_code in (200, 204)

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        get_r = await client.get(
            f"/v1/users/{uid}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert get_r.status_code == 404


@pytest.mark.asyncio
async def test_users_balance_replenish(users_app):
    """POST /v1/users/{id}/balance с operation_type=replenish увеличивает баланс."""
    token = await _get_admin_token(users_app)
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        create_r = await client.post(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "wallet_address": WALLET_TRON,
                "blockchain": "tron",
                "nickname": "balance_user",
            },
        )
    assert create_r.status_code == 201
    uid = create_r.json()["id"]

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        balance_r = await client.post(
            f"/v1/users/{uid}/balance",
            headers={"Authorization": f"Bearer {token}"},
            json={"operation_type": "replenish", "amount": 50.5},
        )
    assert balance_r.status_code == 200
    data = balance_r.json()
    assert data["balance_usdt"] == 50.5


@pytest.mark.asyncio
async def test_users_billing_history(users_app):
    """GET /v1/users/{id}/billing возвращает историю операций."""
    token = await _get_admin_token(users_app)
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        create_r = await client.post(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "wallet_address": WALLET_TRON,
                "blockchain": "tron",
                "nickname": "billing_user",
            },
        )
    assert create_r.status_code == 201
    uid = create_r.json()["id"]

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        balance_r = await client.post(
            f"/v1/users/{uid}/balance",
            headers={"Authorization": f"Bearer {token}"},
            json={"operation_type": "replenish", "amount": 10},
        )
    assert balance_r.status_code == 200

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        billing_r = await client.get(
            f"/v1/users/{uid}/billing",
            headers={"Authorization": f"Bearer {token}"},
            params={"page": 1, "page_size": 20},
        )
    assert billing_r.status_code == 200
    data = billing_r.json()
    assert "transactions" in data
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["usdt_amount"] == 10.0


@pytest.mark.asyncio
async def test_users_did_document(users_app):
    """GET /v1/users/{id}/did-document возвращает did и did_document."""
    token = await _get_admin_token(users_app)
    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        create_r = await client.post(
            "/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "wallet_address": WALLET_TRON,
                "blockchain": "tron",
                "nickname": "diddoc_user",
            },
        )
    assert create_r.status_code == 201
    uid = create_r.json()["id"]

    async with AsyncClient(
        transport=ASGITransport(app=users_app),
        base_url="http://test",
    ) as client:
        did_r = await client.get(
            f"/v1/users/{uid}/did-document",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert did_r.status_code == 200
    data = did_r.json()
    assert "did" in data
    assert data["did"].startswith("did:")
    assert "did_document" in data
    assert data["did_document"].get("@context") is not None
