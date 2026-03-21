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
