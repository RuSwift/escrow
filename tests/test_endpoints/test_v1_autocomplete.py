"""GET /v1/autocomplete/cities и /v1/autocomplete/directions."""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db.models import BestchangeYamlSnapshot
from db import get_db
from web.endpoints.dependencies import get_redis, get_settings, ResolvedSettings
from web.main import create_app


@pytest_asyncio.fixture
async def main_app_autocomplete(test_db, test_redis, test_settings):
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

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings

    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_autocomplete_cities_and_directions(main_app_autocomplete, test_db):
    snap = BestchangeYamlSnapshot(
        file_hash="f" * 64,
        exported_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {
                    "payment_code": "PM1",
                    "cur": "USD",
                    "payment_name": "Один",
                    "payment_name_en": "One",
                },
            ],
            "cities": [{"id": 10, "name": "Город", "name_en": "City"}],
        },
    )
    test_db.add(snap)
    await test_db.commit()

    transport = ASGITransport(app=main_app_autocomplete)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_c = await client.get("/v1/autocomplete/cities", params={"locale": "en", "q": "Cit"})
        assert r_c.status_code == 200
        data_c = r_c.json()
        assert data_c["items"] == [{"id": 10, "name": "City"}]

        r_d = await client.get("/v1/autocomplete/directions", params={"locale": "en", "q": "One"})
        assert r_d.status_code == 200
        data_d = r_d.json()
        assert data_d["items"] == [{"payment_code": "PM1", "cur": "USD", "name": "One"}]


@pytest.mark.asyncio
async def test_autocomplete_q_min_length_400(main_app_autocomplete):
    detail = (
        "Параметр q обязателен: минимум 1 значащий символ после удаления пробелов по краям."
    )
    transport = ASGITransport(app=main_app_autocomplete)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/v1/autocomplete/cities", params={"locale": "en"})
        assert r1.status_code == 400
        assert r1.json()["detail"] == detail

        r2 = await client.get("/v1/autocomplete/cities", params={"locale": "en", "q": ""})
        assert r2.status_code == 400
        assert r2.json()["detail"] == detail

        r3 = await client.get("/v1/autocomplete/cities", params={"locale": "en", "q": "   "})
        assert r3.status_code == 400
        assert r3.json()["detail"] == detail

        r4 = await client.get("/v1/autocomplete/directions", params={})
        assert r4.status_code == 400
        assert r4.json()["detail"] == detail
