"""GET /v1/autocomplete/cities, directions, currencies."""
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
async def test_autocomplete_cities_and_directions(main_app_autocomplete, test_db, monkeypatch):
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
                {
                    "payment_code": "PM2",
                    "cur": "EUR",
                    "payment_name": "Два",
                    "payment_name_en": "Two",
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
        assert data_d.get("total_for_cur") is None

        r_d_usd_total = await client.get(
            "/v1/autocomplete/directions",
            params={"locale": "en", "limit": 5, "cur": "USD"},
        )
        assert r_d_usd_total.status_code == 200
        assert r_d_usd_total.json()["total_for_cur"] == 1

        r_cur = await client.get("/v1/autocomplete/currencies", params={"q": "US"})
        assert r_cur.status_code == 200
        assert r_cur.json()["items"] == [{"code": "USD"}]

        r_d_eur = await client.get(
            "/v1/autocomplete/directions",
            params={"locale": "en", "q": "Two", "cur": "EUR"},
        )
        assert r_d_eur.status_code == 200
        assert r_d_eur.json()["items"] == [{"payment_code": "PM2", "cur": "EUR", "name": "Two"}]

        r_d_filtered_out = await client.get(
            "/v1/autocomplete/directions",
            params={"locale": "en", "q": "One", "cur": "EUR"},
        )
        assert r_d_filtered_out.status_code == 200
        assert r_d_filtered_out.json()["items"] == []

        r_no_q_cities = await client.get(
            "/v1/autocomplete/cities",
            params={"locale": "en", "limit": 5},
        )
        assert r_no_q_cities.status_code == 200
        assert r_no_q_cities.json()["items"] == [{"id": 10, "name": "City"}]

        r_no_q_cur = await client.get("/v1/autocomplete/currencies", params={"limit": 5})
        assert r_no_q_cur.status_code == 200
        assert [x["code"] for x in r_no_q_cur.json()["items"]] == ["EUR", "USD"]

        from services import guarantor as guarantor_svc

        async def fake_forex_codes(_repo, _redis, _settings):
            return {"USD", "EUR", "RUB", "CNY"}

        monkeypatch.setattr(guarantor_svc, "async_forex_supported_codes", fake_forex_codes)
        r_fiat = await client.get(
            "/v1/autocomplete/currencies",
            params={"is_fiat": "true", "limit": 10},
        )
        assert r_fiat.status_code == 200
        fiat_codes = [x["code"] for x in r_fiat.json()["items"]]
        # Пустой q: порядок Settings.system_currencies (дефолт RUB,CNY,USD,EUR), затем прочие по коду
        assert fiat_codes == ["RUB", "CNY", "USD", "EUR"]

        r_no_q_dir = await client.get(
            "/v1/autocomplete/directions",
            params={"locale": "en", "limit": 5},
        )
        assert r_no_q_dir.status_code == 200
        assert r_no_q_dir.json().get("total_for_cur") is None
        assert len(r_no_q_dir.json()["items"]) == 2
