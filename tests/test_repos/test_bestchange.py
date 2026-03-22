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


@pytest.mark.asyncio
async def test_list_currencies(bestchange_repo: BestchangeYamlRepository, test_db):
    snap = BestchangeYamlSnapshot(
        file_hash="g" * 64,
        exported_at=datetime(2025, 8, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {"payment_code": "A", "cur": "USD", "payment_name": "a", "payment_name_en": "a"},
                {"payment_code": "B", "cur": "EUR", "payment_name": "b", "payment_name_en": "b"},
                {"payment_code": "C", "cur": "USD", "payment_name": "c", "payment_name_en": "c"},
            ],
            "cities": [],
        },
    )
    test_db.add(snap)
    await test_db.commit()

    rows = await bestchange_repo.list("currencies", q="us", limit=10)
    assert [r.code for r in rows] == ["USD"]

    all_codes = await bestchange_repo.list("currencies", q=None, limit=10)
    assert sorted(r.code for r in all_codes) == ["EUR", "USD"]

    assert await bestchange_repo.get("currencies", ref="x") is None


@pytest.mark.asyncio
async def test_list_payment_methods_filter_by_cur(bestchange_repo: BestchangeYamlRepository, test_db):
    snap = BestchangeYamlSnapshot(
        file_hash="h" * 64,
        exported_at=datetime(2025, 9, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {
                    "payment_code": "PM_EUR",
                    "cur": "EUR",
                    "payment_name": "Альфа",
                    "payment_name_en": "Alpha pay",
                },
                {
                    "payment_code": "PM_USD",
                    "cur": "USD",
                    "payment_name": "Бета",
                    "payment_name_en": "Beta pay",
                },
            ],
            "cities": [],
        },
    )
    test_db.add(snap)
    await test_db.commit()

    eur = await bestchange_repo.list("payment_methods", locale="en", q="Alpha", cur="EUR", limit=10)
    assert len(eur) == 1 and eur[0].payment_code == "PM_EUR"

    usd_empty = await bestchange_repo.list("payment_methods", locale="en", q="Alpha", cur="USD", limit=10)
    assert len(usd_empty) == 0

    beta_usd = await bestchange_repo.list("payment_methods", locale="en", q="Beta", cur="usd", limit=10)
    assert len(beta_usd) == 1 and beta_usd[0].payment_code == "PM_USD"


@pytest.mark.asyncio
async def test_list_payment_methods_empty_q_cur_before_limit(bestchange_repo: BestchangeYamlRepository, test_db):
    """При пустом q limit применяется среди методов с выбранной валютой, не по всем методам сразу."""
    snap = BestchangeYamlSnapshot(
        file_hash="cur" + "0" * 61,
        exported_at=datetime(2025, 11, 15, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {"payment_code": "E1", "cur": "EUR", "payment_name": "E one", "payment_name_en": "E one"},
                {"payment_code": "E2", "cur": "EUR", "payment_name": "E two", "payment_name_en": "E two"},
                {"payment_code": "E3", "cur": "EUR", "payment_name": "E three", "payment_name_en": "E three"},
                {"payment_code": "E4", "cur": "EUR", "payment_name": "E four", "payment_name_en": "E four"},
                {"payment_code": "E5", "cur": "EUR", "payment_name": "E five", "payment_name_en": "E five"},
                {"payment_code": "U1", "cur": "USD", "payment_name": "U one", "payment_name_en": "U one"},
                {"payment_code": "U2", "cur": "USD", "payment_name": "U two", "payment_name_en": "U two"},
                {"payment_code": "U3", "cur": "USD", "payment_name": "U three", "payment_name_en": "U three"},
                {"payment_code": "U4", "cur": "USD", "payment_name": "U four", "payment_name_en": "U four"},
                {"payment_code": "U5", "cur": "USD", "payment_name": "U five", "payment_name_en": "U five"},
            ],
            "cities": [],
        },
    )
    test_db.add(snap)
    await test_db.commit()

    rows = await bestchange_repo.list("payment_methods", locale="en", q=None, cur="USD", limit=5)
    # Порядок как в снимке: сортировка по name.lower(), затем payment_code
    assert [r.payment_code for r in rows] == ["U5", "U4", "U1", "U3", "U2"]

    n = await bestchange_repo.count_payment_methods_for_currency(locale="en", cur="USD")
    assert n == 5


@pytest.mark.asyncio
async def test_snapshot_forex_currency_codes(bestchange_repo: BestchangeYamlRepository, test_db):
    snap = BestchangeYamlSnapshot(
        file_hash="fx" + "0" * 62,
        exported_at=datetime(2025, 10, 1, tzinfo=timezone.utc),
        payload={
            "payment_methods": [
                {"payment_code": "P", "cur": "USD", "payment_name": "a", "payment_name_en": "a"},
            ],
            "cities": [],
            "forex_currencies": ["usd", "GBP", "  "],
        },
    )
    test_db.add(snap)
    await test_db.commit()

    codes = await bestchange_repo.snapshot_forex_currency_codes()
    assert codes == {"USD", "GBP"}

    await bestchange_repo.patch()
    codes2 = await bestchange_repo.snapshot_forex_currency_codes()
    assert codes2 == {"USD", "GBP"}


@pytest.mark.asyncio
async def test_snapshot_forex_currency_codes_from_meta(bestchange_repo: BestchangeYamlRepository, test_db):
    snap = BestchangeYamlSnapshot(
        file_hash="fy" + "0" * 62,
        exported_at=datetime(2025, 11, 1, tzinfo=timezone.utc),
        payload={
            "meta": {"forex_currencies": ["CHF"]},
            "payment_methods": [],
            "cities": [],
        },
    )
    test_db.add(snap)
    await test_db.commit()
    assert await bestchange_repo.snapshot_forex_currency_codes() == {"CHF"}


@pytest.mark.asyncio
async def test_snapshot_forex_currency_codes_empty_without_key(bestchange_repo: BestchangeYamlRepository, test_db):
    snap = BestchangeYamlSnapshot(
        file_hash="fz" + "0" * 62,
        exported_at=datetime(2025, 12, 1, tzinfo=timezone.utc),
        payload={"payment_methods": [], "cities": []},
    )
    test_db.add(snap)
    await test_db.commit()
    assert await bestchange_repo.snapshot_forex_currency_codes() == set()
