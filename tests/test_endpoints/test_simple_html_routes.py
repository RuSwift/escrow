"""HTML-маршруты /simple и /simple/{order_id}."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from web.main import create_app
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings


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


@pytest.mark.asyncio
async def test_simple_list_returns_html(main_app):
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        r = await client.get("/simple")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    body = r.text
    assert 'data-simple-order-id=""' in body or "data-simple-order-id=''" in body


@pytest.mark.asyncio
async def test_simple_deal_returns_html_with_order_id(main_app):
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        r = await client.get("/simple/TF-2840")
    assert r.status_code == 200
    assert "data-simple-order-id=" in r.text
    assert "TF-2840" in r.text
