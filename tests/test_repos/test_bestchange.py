"""BestchangeYamlRepository: max(id), локали i18n, Redis-кеш."""
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from db.models import BestchangeYamlSnapshot
from repos.bestchange import BestchangeYamlRepository
from settings import Settings


@pytest_asyncio.fixture
async def bestchange_repo(test_db, test_redis, test_settings: Settings):
    return BestchangeYamlRepository(session=test_db, redis=test_redis, settings=test_settings)


@pytest.mark.asyncio
async def test_list_uses_max_id_and_locale(bestchange_repo: BestchangeYamlRepository, test_db):
    older = BestchangeYamlSnapshot(
        file_hash="a" * 64,
        exported_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {"payment_code": "OLD", "cur": "USD", "payment_name": "Старый", "payment_name_en": "Old"},
            ],
            "cities": [{"id": 1, "name": "Старый город", "name_en": "Old city"}],
        },
    )
    newer = BestchangeYamlSnapshot(
        file_hash="b" * 64,
        exported_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {
                    "payment_code": "NEW",
                    "cur": "EUR",
                    "payment_name": "Новый",
                    "payment_name_en": "New",
                },
            ],
            "cities": [{"id": 2, "name": "Новгород", "name_en": "Novgorod"}],
        },
    )
    test_db.add(older)
    test_db.add(newer)
    await test_db.commit()

    pm_en = await bestchange_repo.list("payment_methods", locale="en", limit=10)
    assert len(pm_en) == 1
    assert pm_en[0].payment_code == "NEW"
    assert pm_en[0].name == "New"

    pm_ru = await bestchange_repo.list("payment_methods", locale="ru", limit=10)
    assert pm_ru[0].name == "Новый"

    cities = await bestchange_repo.list("cities", locale="en", q="Nov", limit=10)
    assert len(cities) == 1
    assert cities[0].id == 2


@pytest.mark.asyncio
async def test_get_and_cache_invalidation(bestchange_repo: BestchangeYamlRepository, test_db, test_redis):
    snap = BestchangeYamlSnapshot(
        file_hash="c" * 64,
        exported_at=datetime(2022, 1, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {"payment_code": "X", "cur": "Y", "payment_name": "Икс", "payment_name_en": "X"},
            ],
            "cities": [{"id": 5, "name": "Пять", "name_en": "Five"}],
        },
    )
    test_db.add(snap)
    await test_db.commit()

    g1 = await bestchange_repo.get("payment_methods", ref="X", locale="en")
    assert g1 is not None
    assert g1.name == "X"

    assert await test_redis.get("bestchange_yaml:sid") is not None
    assert await test_redis.get("bestchange_yaml:data") is not None

    await bestchange_repo.patch()
    assert await test_redis.get("bestchange_yaml:sid") is None
    assert await test_redis.get("bestchange_yaml:data") is None

    g2 = await bestchange_repo.get("cities", ref=5, locale="en")
    assert g2 is not None
    assert g2.name == "Five"


@pytest.mark.asyncio
async def test_new_snapshot_id_rebuilds_cache(bestchange_repo: BestchangeYamlRepository, test_db):
    first = BestchangeYamlSnapshot(
        file_hash="d" * 64,
        exported_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {"payment_code": "A1", "cur": "Z", "payment_name": "А", "payment_name_en": "A"},
            ],
            "cities": [],
        },
    )
    test_db.add(first)
    await test_db.commit()

    rows1 = await bestchange_repo.list("payment_methods", locale="en", limit=5)
    assert rows1[0].payment_code == "A1"

    second = BestchangeYamlSnapshot(
        file_hash="e" * 64,
        exported_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {"payment_code": "B2", "cur": "Z", "payment_name": "Б", "payment_name_en": "B"},
            ],
            "cities": [],
        },
    )
    test_db.add(second)
    await test_db.commit()

    rows2 = await bestchange_repo.list("payment_methods", locale="en", limit=5)
    assert rows2[0].payment_code == "B2"


@pytest.mark.asyncio
async def test_list_q_case_insensitive(bestchange_repo: BestchangeYamlRepository, test_db):
    snap = BestchangeYamlSnapshot(
        file_hash="f" * 64,
        exported_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {
                    "payment_code": "AbCd",
                    "cur": "usd",
                    "payment_name": "Название",
                    "payment_name_en": "Mixed Case Title",
                },
            ],
            "cities": [{"id": 42, "name": "САНКТ-Петербург", "name_en": "Saint Petersburg"}],
        },
    )
    test_db.add(snap)
    await test_db.commit()

    pm = await bestchange_repo.list("payment_methods", locale="en", q="MIXED case", limit=10)
    assert len(pm) == 1 and pm[0].payment_code == "AbCd"

    pm2 = await bestchange_repo.list("payment_methods", locale="en", q="abcd", limit=10)
    assert len(pm2) == 1

    pm3 = await bestchange_repo.list("payment_methods", locale="en", q="USD", limit=10)
    assert len(pm3) == 1

    ct = await bestchange_repo.list("cities", locale="en", q="saint peter", limit=10)
    assert len(ct) == 1 and ct[0].id == 42

    ct_ru = await bestchange_repo.list("cities", locale="ru", q="санкт-пет", limit=10)
    assert len(ct_ru) == 1


@pytest.mark.asyncio
async def test_list_without_locale_searches_all_localized_names(bestchange_repo: BestchangeYamlRepository, test_db):
    snap = BestchangeYamlSnapshot(
        file_hash="9" * 64,
        exported_at=datetime(2025, 7, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {
                    "payment_code": "PMX",
                    "cur": "RUB",
                    "payment_name": "Только русское имя",
                    "payment_name_en": "Only English",
                },
            ],
            "cities": [{"id": 7, "name": "Тула", "name_en": "Tula"}],
        },
    )
    test_db.add(snap)
    await test_db.commit()

    pm_en_only = await bestchange_repo.list("payment_methods", locale="en", q="Только", limit=10)
    assert len(pm_en_only) == 0

    pm_all = await bestchange_repo.list("payment_methods", locale=None, q="Только", limit=10)
    assert len(pm_all) == 1 and pm_all[0].payment_code == "PMX"
    assert pm_all[0].name == "Only English"

    city_en = await bestchange_repo.list("cities", locale="en", q="Тул", limit=10)
    assert len(city_en) == 0

    city_all = await bestchange_repo.list("cities", locale=None, q="Тул", limit=10)
    assert len(city_all) == 1 and city_all[0].id == 7
    assert city_all[0].name == "Tula"
