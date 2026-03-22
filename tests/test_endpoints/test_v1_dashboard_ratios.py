"""GET /v1/dashboard/ratios."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from db.models import DashboardState
from web.endpoints.dependencies import (
    get_current_wallet_user,
    get_redis,
    get_settings,
    ResolvedSettings,
    UserInfo,
)
from web.main import create_app


@pytest_asyncio.fixture
async def main_app_dashboard_ratios(test_db, test_redis, test_settings):
    row = await test_db.get(DashboardState, 1)
    payload = {"Forex": [{"base": "USD", "quote": "RUB", "pair": None}]}
    if row is None:
        test_db.add(DashboardState(id=1, ratios=payload))
    else:
        row.ratios = payload
    await test_db.commit()

    app = create_app()

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

    async def override_wallet_user() -> UserInfo:
        return UserInfo(
            standard="tron",
            wallet_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            did="did:test:tron",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_wallet_user] = override_wallet_user

    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_dashboard_ratios(main_app_dashboard_ratios):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_dashboard_ratios),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/dashboard/ratios")
    assert r.status_code == 200
    body = r.json()
    assert "Forex" in body
    assert body["Forex"][0]["base"] == "USD"
    assert body["Forex"][0]["pair"] is None


@pytest_asyncio.fixture
async def main_app_dashboard_ratios_empty(test_db, test_redis, test_settings):
    app = create_app()

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

    async def override_wallet_user() -> UserInfo:
        return UserInfo(
            standard="tron",
            wallet_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            did="did:test:tron",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_wallet_user] = override_wallet_user

    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_dashboard_ratios_empty_when_no_row(
    main_app_dashboard_ratios_empty,
):
    async with AsyncClient(
        transport=ASGITransport(app=main_app_dashboard_ratios_empty),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/dashboard/ratios")
    assert r.status_code == 200
    assert r.json() == {}
