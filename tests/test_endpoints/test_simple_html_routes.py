"""HTML-маршруты /arbiter/{arbiter_space_did}, deal, legacy."""
from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from web.main import create_app
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings

_ARB = "did:test:arbiter_simple_html"


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
    path = f"/arbiter/{quote(_ARB, safe='')}"
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        r = await client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    body = r.text
    assert "data-simple-arbiter-space-did=" in body
    assert _ARB in body


@pytest.mark.asyncio
async def test_simple_legacy_returns_html_with_order_id(main_app):
    path = f"/arbiter/{quote(_ARB, safe='')}/TF-2840"
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        r = await client.get(path)
    assert r.status_code == 200
    assert "data-simple-order-id=" in r.text
    assert "TF-2840" in r.text


@pytest.mark.asyncio
async def test_simple_deal_returns_html(main_app):
    path = f"/arbiter/{quote(_ARB, safe='')}/deal/abc123deal"
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        r = await client.get(path)
    assert r.status_code == 200
    assert "data-simple-deal-uid=" in r.text
    assert "abc123deal" in r.text
