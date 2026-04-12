"""
Тесты движков котировок: ForexEngine, CbrEngine, BestChangeRatios, RapiraEngine.

Интеграционные тесты с реальными HTTP (без моков): cdn.jsdelivr.net, cbr.ru,
URL из BestChangeSettings (по умолчанию api.bestchange.ru), Rapira API.

Rapira: ``RATIOS_RAPIRA_PRIVATE_KEY``, ``RATIOS_RAPIRA_UID`` (и при необходимости
``RATIOS_RAPIRA_HOST``, ``RATIOS_RAPIRA_TTL``) — в окружении или в ``.env`` /
``.env.local``; интеграционный тест падает, если они не заданы.

Маркер ``network`` стоит на тестах с запросами в сеть; без интернета:
``pytest tests/test_services/test_ratios.py -m "not network"`` — только
is_enabled и проверка аргументов load_orders.
"""
from types import SimpleNamespace

import pytest
import pytest_asyncio
from pydantic import SecretStr

from services.ratios import RatioCacheAdapter
from services.ratios.bestchange import BestChangeRatios
from services.ratios.cbr import CbrEngine
from services.ratios.forex import ForexEngine
from services.ratios.rapira import RapiraEngine
from settings import (
    BestChangeSettings,
    CbrEngineSettings,
    ForexEngineSettings,
    RapiraEngineSettings,
)


@pytest.fixture
def forex_engine(test_redis):
    cache = RatioCacheAdapter(test_redis, "TestForexEngineNet")
    return ForexEngine(cache, ForexEngineSettings(), refresh_cache=True)


@pytest.fixture
def cbr_engine(test_redis):
    cache = RatioCacheAdapter(test_redis, "TestCbrEngineNet")
    return CbrEngine(cache, CbrEngineSettings(), refresh_cache=True)


@pytest_asyncio.fixture
async def bestchange_engine_network(test_redis, tmp_path):
    """Реальная загрузка ZIP в tmp_path (без forced_zip_file)."""
    zip_path = tmp_path / "bestchange_info.zip"
    settings = BestChangeSettings(zip_path=str(zip_path))
    cache = RatioCacheAdapter(test_redis, "TestBestChangeNet")
    return BestChangeRatios(cache, settings, refresh_cache=True)


# --- ForexEngine (cdn.jsdelivr.net) ---


@pytest.mark.asyncio
async def test_forex_engine_is_enabled(forex_engine):
    assert forex_engine.is_enabled is True


@pytest.mark.asyncio
async def test_forex_market_ratio_matches_exchange_pair_semantics(test_redis, monkeypatch):
    """usd.json даёт «сколько quote за 1 USD» — в ExchangePair это ratio для 1 USD = ratio quote."""

    async def fake_load(cls):
        return {"date": "2026-01-01", "usd": {"rub": 80.0, "eur": 0.9}}

    monkeypatch.setattr(ForexEngine, "load_from_internet", classmethod(fake_load))
    cache = RatioCacheAdapter(test_redis, "TestForexPairSemantics")
    engine = ForexEngine(cache, ForexEngineSettings(), refresh_cache=True)
    pairs = await engine.market()
    by_q = {p.quote: p for p in pairs}
    assert by_q["RUB"].ratio == 80.0
    assert abs(by_q["EUR"].ratio - 0.9) < 1e-9
    assert by_q["RUB"].base == "USD"


@pytest.mark.network
@pytest.mark.asyncio
async def test_forex_load_from_internet_real():
    data = await ForexEngine.load_from_internet()
    assert data is not None
    assert "date" in data
    assert "usd" in data
    assert isinstance(data["usd"], dict)
    assert len(data["usd"]) > 10


@pytest.mark.network
@pytest.mark.asyncio
async def test_forex_market_real(forex_engine):
    pairs = await forex_engine.market()
    assert len(pairs) > 50
    quotes = {p.quote for p in pairs}
    assert "EUR" in quotes or "RUB" in quotes
    assert all(p.base == "USD" for p in pairs)


# --- CbrEngine (cbr.ru) ---


@pytest.mark.asyncio
async def test_cbr_engine_is_enabled(cbr_engine):
    assert cbr_engine.is_enabled is True


@pytest.mark.network
@pytest.mark.asyncio
async def test_cbr_load_from_internet_real():
    data = await CbrEngine.load_from_internet()
    assert data is not None
    assert "date" in data
    assert "rates" in data
    assert len(data["rates"]) >= 1
    codes = {r["code"] for r in data["rates"]}
    assert "USD" in codes


@pytest.mark.network
@pytest.mark.asyncio
async def test_cbr_market_real(cbr_engine):
    pairs = await cbr_engine.market()
    assert len(pairs) >= 1
    assert all(p.base == "RUB" for p in pairs)
    quotes = {p.quote for p in pairs}
    assert "USD" in quotes


@pytest.mark.network
@pytest.mark.asyncio
async def test_cbr_ratio_usdt_rub_real(cbr_engine):
    """USDT мапится на USD; курс строится по реальному рынку ЦБ."""
    p = await cbr_engine.ratio("USDT", "RUB")
    assert p is not None
    assert p.base == "USD"
    assert p.quote == "RUB"
    assert p.ratio > 0


# --- RapiraEngine (api.rapira.net, секреты из env / .env / .env.local) ---


def _rapira_settings_for_integration() -> RapiraEngineSettings:
    """Настройки из env и из .env / .env.local (абсолютные пути в RapiraEngineSettings)."""
    return RapiraEngineSettings()


def _rapira_has_credentials(settings: RapiraEngineSettings) -> bool:
    pk = settings.private_key
    secret = pk.get_secret_value() if pk else None
    return bool(secret and secret.strip() and settings.uid and settings.uid.strip())


@pytest.mark.asyncio
async def test_rapira_engine_is_enabled_false_without_secrets(test_redis):
    cache = RatioCacheAdapter(test_redis, "TestRapiraDisabled")
    settings = SimpleNamespace(
        private_key=None,
        uid=None,
        host="api.rapira.net",
        ttl=60,
    )
    engine = RapiraEngine(cache, settings)
    assert engine.is_enabled is False


@pytest.mark.asyncio
async def test_rapira_engine_is_enabled_true_with_secret_and_uid(test_redis):
    cache = RatioCacheAdapter(test_redis, "TestRapiraEnabledFlag")
    settings = SimpleNamespace(
        private_key=SecretStr("dGVzdA=="),
        uid="test-uid",
        host="api.rapira.net",
        ttl=60,
    )
    engine = RapiraEngine(cache, settings)
    assert engine.is_enabled is True


@pytest.mark.network
@pytest.mark.asyncio
async def test_rapira_load_markets_and_market_real(test_redis):
    """
    Реальные запросы к Rapira (JWT + /open/market/rates).
    Требуются RATIOS_RAPIRA_PRIVATE_KEY и RATIOS_RAPIRA_UID (env / .env / .env.local);
    без них тест падает. Ошибки API — через RuntimeError в RapiraAuth (тест падает).
    """
    settings = _rapira_settings_for_integration()
    if not _rapira_has_credentials(settings):
        pytest.fail(
            "Задайте RATIOS_RAPIRA_PRIVATE_KEY и RATIOS_RAPIRA_UID "
            "(окружение или .env / .env.local)"
        )
    cache = RatioCacheAdapter(test_redis, "TestRapiraNet")
    engine = RapiraEngine(cache, settings, refresh_cache=True)
    assert engine.is_enabled is True

    markets = await engine.load_markets()

    assert markets is not None
    assert len(markets) >= 1
    m0 = markets[0]
    assert m0.baseCurrency
    assert m0.quoteCurrency

    pairs = await engine.market()
    assert len(pairs) >= 1
    assert all(p.base and p.quote for p in pairs)
    assert pairs[0].ratio > 0


# --- BestChangeRatios (api.bestchange.ru / настройка url) ---


@pytest.mark.asyncio
async def test_bestchange_is_enabled_default():
    class _DummyCache:
        pass

    engine = BestChangeRatios(_DummyCache(), BestChangeSettings())
    assert engine.is_enabled is True


@pytest.mark.asyncio
async def test_bestchange_is_enabled_false_without_url(test_redis):
    settings = BestChangeSettings(url="", zip_path="/tmp/x.zip")
    cache = RatioCacheAdapter(test_redis, "TestBCNet2")
    engine = BestChangeRatios(cache, settings)
    assert engine.is_enabled is False


@pytest.mark.network
@pytest.mark.asyncio
async def test_bestchange_load_from_server_and_orders_real(bestchange_engine_network):
    """Один проход сети: ZIP с api.bestchange.ru, затем load_orders(USD/BTC)."""
    rates, currencies, exchangers, cities = await bestchange_engine_network.load_from_server()
    assert len(rates.get()) > 0
    assert len(currencies.data) > 0
    assert len(exchangers.data) > 0
    assert len(cities.data) > 0

    orders = await bestchange_engine_network.load_orders(fiat="USD", token="BTC")
    assert orders is not None
    assert isinstance(orders.asks, list)
    assert isinstance(orders.bids, list)
    assert len(orders.asks) + len(orders.bids) > 0


@pytest.mark.asyncio
async def test_bestchange_load_orders_invalid_args_raises():
    class _DummyCache:
        pass

    engine = BestChangeRatios(_DummyCache(), BestChangeSettings())
    with pytest.raises(RuntimeError, match="Unexpected"):
        await engine.load_orders(fiat="USD", give="X")
