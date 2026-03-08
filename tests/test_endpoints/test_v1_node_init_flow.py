"""
E2E тесты флоу инициализации ноды при первой настройке (без пароля админа и ключа):
init (mnemonic) или init-pem → set-password → login → set-service-endpoint.
"""
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from settings import Settings

from db import get_db
from repos.node import NodeRepository
from services.admin import AdminService
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings
from web.node import create_app

TEST_PEM_PATH = Path(__file__).resolve().parent.parent / "data" / "test.pem"


def _valid_mnemonic():
    """Валидная мнемоника для e2e (12 слов)."""
    from mnemonic import Mnemonic
    return Mnemonic("english").generate(strength=128)


def _make_override_get_settings(test_db, test_redis, settings):
    """Собирает override get_settings для переданных db, redis и settings."""
    async def override_get_settings():
        node_repo = NodeRepository(session=test_db, redis=test_redis, settings=settings)
        admin_svc = AdminService(session=test_db, redis=test_redis, settings=settings)
        node = await node_repo.get()
        has_key_env = bool(
            settings.mnemonic.phrase
            or settings.mnemonic.encrypted_phrase
            or settings.pem
        )
        has_keypair_from_db = (node is not None) and (
            await node_repo.get_active_keypair() is not None
        )
        has_key = has_key_env or has_keypair_from_db
        is_admin = settings.admin.is_configured or await admin_svc.is_admin_configured()
        service_endpoint = (node.service_endpoint or "").strip() if node else ""
        is_node_initialized = has_key and is_admin and bool(service_endpoint)
        return ResolvedSettings(
            settings=settings,
            has_key=has_key,
            is_admin_configured=is_admin,
            is_node_initialized=is_node_initialized,
        )
    return override_get_settings


@pytest.fixture
def node_init_app(test_db, test_redis, test_settings):
    """Приложение с подменёнными БД и Redis; get_settings строит состояние из test_db/test_redis."""
    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = _make_override_get_settings(test_db, test_redis, test_settings)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def node_init_app_mnemonic_env(test_db, test_redis, set_test_secret, monkeypatch):
    """Приложение с MNEMONIC_PHRASE, заданным через env (нода считается с ключом)."""
    mnemonic = _valid_mnemonic()
    monkeypatch.setenv("MNEMONIC_PHRASE", mnemonic)
    settings = Settings()
    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = _make_override_get_settings(test_db, test_redis, settings)
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def node_init_app_pem_env(test_db, test_redis, set_test_secret, monkeypatch):
    """Приложение с PEM, заданным через env (нода считается с ключом)."""
    if not TEST_PEM_PATH.exists():
        pytest.skip(f"Test PEM file not found: {TEST_PEM_PATH}")
    pem_content = TEST_PEM_PATH.read_text()
    monkeypatch.setenv("PEM", pem_content)
    settings = Settings()
    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = _make_override_get_settings(test_db, test_redis, settings)
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_node_init_flow_with_pem(node_init_app, set_test_secret):
    """
    Полный флоу при первой инициализации (нет ни пароля админа, ни ключа):
    init-pem (без авторизации) → set-password → login → set-service-endpoint.
    """
    if not TEST_PEM_PATH.exists():
        pytest.skip(f"Test PEM file not found: {TEST_PEM_PATH}")
    pem_content = TEST_PEM_PATH.read_text()

    async with AsyncClient(
        transport=ASGITransport(app=node_init_app),
        base_url="http://test",
    ) as client:
        # 1) Инициализация ноды из PEM без авторизации (первая инициализация)
        r = await client.post(
            "/v1/node/init-pem",
            json={"pem_data": pem_content, "password": None},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True
        assert data.get("did", "").startswith("did:peer:1:")
        assert data.get("key_type") == "pem"

        # 2) Установка пароля админа (без авторизации, нода уже с ключом, но админ ещё не настроен)
        r = await client.post(
            "/v1/admin/set-password",
            json={"username": "admin", "password": "adminpassword123"},
        )
        assert r.status_code == 200, r.text

        # 3) Логин → получаем Bearer токен
        r = await client.post(
            "/v1/admin/login",
            json={"username": "admin", "password": "adminpassword123"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True
        token = data.get("token")
        assert token

        headers = {"Authorization": f"Bearer {token}"}

        # 4) Установка service endpoint (с авторизацией)
        r = await client.post(
            "/v1/node/set-service-endpoint",
            json={"service_endpoint": "https://node.test.example/didcomm/endpoint"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True

        # 5) Проверка: key-info и service-endpoint
        r = await client.get("/v1/node/key-info", headers=headers)
        assert r.status_code == 200, r.text
        info = r.json()
        assert info.get("did", "").startswith("did:peer:1:")
        assert info.get("service_endpoint") == "https://node.test.example/didcomm/endpoint"

        r = await client.get("/v1/node/service-endpoint", headers=headers)
        assert r.status_code == 200, r.text
        ep = r.json()
        assert ep.get("service_endpoint") == "https://node.test.example/didcomm/endpoint"
        assert ep.get("configured") is True


@pytest.mark.asyncio
async def test_node_init_flow_with_mnemonic(node_init_app, set_test_secret):
    """
    Полный флоу при первой инициализации через мнемонику:
    init (mnemonic, без авторизации) → set-password → login → set-service-endpoint.
    """
    mnemonic = _valid_mnemonic()

    async with AsyncClient(
        transport=ASGITransport(app=node_init_app),
        base_url="http://test",
    ) as client:
        # 1) Инициализация ноды из мнемоники без авторизации (первая инициализация)
        r = await client.post(
            "/v1/node/init",
            json={"mnemonic": mnemonic},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True
        assert data.get("did", "").startswith("did:peer:1:")
        assert data.get("key_type") == "mnemonic"

        # 2) Установка пароля админа
        r = await client.post(
            "/v1/admin/set-password",
            json={"username": "admin", "password": "adminpassword123"},
        )
        assert r.status_code == 200, r.text

        # 3) Логин → Bearer токен
        r = await client.post(
            "/v1/admin/login",
            json={"username": "admin", "password": "adminpassword123"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True
        token = data.get("token")
        assert token

        headers = {"Authorization": f"Bearer {token}"}

        # 4) Установка service endpoint
        r = await client.post(
            "/v1/node/set-service-endpoint",
            json={"service_endpoint": "https://node.test.example/didcomm/endpoint"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("success") is True

        # 5) Проверка key-info и service-endpoint
        r = await client.get("/v1/node/key-info", headers=headers)
        assert r.status_code == 200, r.text
        info = r.json()
        assert info.get("did", "").startswith("did:peer:1:")
        assert info.get("service_endpoint") == "https://node.test.example/didcomm/endpoint"

        r = await client.get("/v1/node/service-endpoint", headers=headers)
        assert r.status_code == 200, r.text
        ep = r.json()
        assert ep.get("service_endpoint") == "https://node.test.example/didcomm/endpoint"
        assert ep.get("configured") is True


@pytest.mark.asyncio
async def test_node_init_rejected_when_mnemonic_set_via_env(node_init_app_mnemonic_env):
    """
    Если MNEMONIC_PHRASE задан через env, повторная инициализация через init отклоняется (400).
    """
    mnemonic = _valid_mnemonic()
    async with AsyncClient(
        transport=ASGITransport(app=node_init_app_mnemonic_env),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/node/init",
            json={"mnemonic": mnemonic},
        )
        assert r.status_code == 400, r.text
        data = r.json()
        assert "detail" in data
        detail_lower = data["detail"].lower()
        assert "only one" in detail_lower or "already" in detail_lower or "один раз" in data["detail"] or "инициализ" in data["detail"]


@pytest.mark.asyncio
async def test_node_init_pem_rejected_when_pem_set_via_env(node_init_app_pem_env):
    """
    Если PEM задан через env, повторная инициализация через init-pem отклоняется (400).
    """
    if not TEST_PEM_PATH.exists():
        pytest.skip(f"Test PEM file not found: {TEST_PEM_PATH}")
    pem_content = TEST_PEM_PATH.read_text()
    async with AsyncClient(
        transport=ASGITransport(app=node_init_app_pem_env),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/node/init-pem",
            json={"pem_data": pem_content, "password": None},
        )
        assert r.status_code == 400, r.text
        data = r.json()
        assert "detail" in data
        detail_lower = data["detail"].lower()
        assert "only one" in detail_lower or "already" in detail_lower or "один раз" in data["detail"] or "инициализ" in data["detail"]
