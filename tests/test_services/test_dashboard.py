"""Тесты DashboardService: list_ratios / update_ratios (только BaseRatioEngine)."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.ratio_entities import ExchangePair
from core.utils import utc_now_float
from repos.dashboard import DashboardStateRepository
from services.dashboard import (
    DashboardService,
    _dedupe_mutual_pair_rows,
    _fiat_involving_pairs,
    _normalize_system_currencies,
)
from services.ratios.base import BaseRatioEngine
from services.ratios.cache import RatioCacheAdapter
from settings import Settings


class FakeSpotEngine(BaseRatioEngine):
    """Спотовый движок с минимальным market для ratio()."""

    async def market(self) -> list[ExchangePair]:
        return [
            ExchangePair(
                base="USD",
                quote="RUB",
                ratio=100.0,
                utc=utc_now_float(),
            ),
        ]


class CountingSpotEngine(BaseRatioEngine):
    """market() считает вызовы."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.market_calls = 0

    async def market(self) -> list[ExchangePair]:
        self.market_calls += 1
        return []


@pytest.mark.asyncio
async def test_list_ratios_for_engine_types_filters(test_redis):
    """list_ratios_for_engine_types оставляет только указанные классы движков."""

    class OtherSpot(BaseRatioEngine):
        async def market(self):
            return []

    spot = FakeSpotEngine(
        RatioCacheAdapter(test_redis, "FakeSpotEngine"),
        SimpleNamespace(),
        refresh_cache=False,
    )
    other = OtherSpot(
        RatioCacheAdapter(test_redis, "OtherSpot"),
        SimpleNamespace(),
        refresh_cache=False,
    )
    settings = Settings(system_currencies=["USD", "RUB"])
    with patch(
        "services.dashboard.get_ratios_engines",
        return_value=[other, spot],
    ):
        svc = DashboardService(test_redis, settings)
        data = await svc.list_ratios_for_engine_types((FakeSpotEngine,))

    assert set(data.keys()) == {"FakeSpot"}


@pytest.mark.asyncio
async def test_dashboard_state_merge_preserves_other_engines(test_db):
    """merge_ratios_engines не удаляет ключи других движков."""
    from db.models import DashboardState

    row = await test_db.get(DashboardState, 1)
    if row is None:
        test_db.add(
            DashboardState(
                id=1,
                ratios={"Forex": [{"base": "X", "quote": "Y", "pair": None}]},
            )
        )
    else:
        row.ratios = {"Forex": [{"base": "X", "quote": "Y", "pair": None}]}
    await test_db.commit()

    repo = DashboardStateRepository(test_db)
    await repo.merge_ratios_engines(
        {"Cbr": [{"base": "RUB", "quote": "USD", "pair": None}]}
    )
    await test_db.commit()

    from sqlalchemy import select

    res = await test_db.execute(select(DashboardState).where(DashboardState.id == 1))
    row = res.scalar_one()
    assert set(row.ratios.keys()) == {"Forex", "Cbr"}
    assert len(row.ratios["Cbr"]) == 1


@pytest.mark.asyncio
async def test_list_ratios_skips_non_spot_engine(test_redis):
    """Объект без BaseRatioEngine не попадает в результат и не дергается."""
    spot = FakeSpotEngine(
        RatioCacheAdapter(test_redis, "FakeSpotEngine"),
        SimpleNamespace(),
        refresh_cache=False,
    )
    p2p_dummy = type("NotSpot", (), {"is_enabled": True})()

    settings = Settings(system_currencies=["USD", "RUB"])
    with patch(
        "services.dashboard.get_ratios_engines",
        return_value=[p2p_dummy, spot],
    ):
        svc = DashboardService(test_redis, settings)
        data = await svc.list_ratios()

    assert set(data.keys()) == {"FakeSpot"}
    rows = data["FakeSpot"]
    # 10 направлений → после схлопывания взаимных пар остаётся 5 неупорядоченных пар
    assert len(rows) == 5
    pairs = {(r["base"], r["quote"]) for r in rows}
    assert (("USDT", "RUB") in pairs) ^ (("RUB", "USDT") in pairs)
    assert ("USDT", "A7A5") not in pairs
    for r in rows:
        assert "pair" in r
        assert r["pair"] is None or isinstance(r["pair"], dict)


@pytest.mark.asyncio
async def test_update_ratios_only_engine_types(test_redis):
    """update_ratios(only_engine_types=…) обновляет только указанные классы движков."""

    class EngineAlpha(BaseRatioEngine):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.calls = 0

        async def market(self):
            self.calls += 1
            return []

    class EngineBeta(BaseRatioEngine):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.calls = 0

        async def market(self):
            self.calls += 1
            return []

    alpha = EngineAlpha(
        RatioCacheAdapter(test_redis, "Alpha"),
        SimpleNamespace(),
        refresh_cache=True,
    )
    beta = EngineBeta(
        RatioCacheAdapter(test_redis, "Beta"),
        SimpleNamespace(),
        refresh_cache=True,
    )
    settings = Settings()
    with patch(
        "services.dashboard.get_ratios_engines",
        return_value=[alpha, beta],
    ):
        svc = DashboardService(test_redis, settings)
        await svc.update_ratios(only_engine_types=(EngineAlpha,))

    assert alpha.calls == 1
    assert beta.calls == 0


@pytest.mark.asyncio
async def test_update_ratios_calls_market_only_on_spot(test_redis):
    counting = CountingSpotEngine(
        RatioCacheAdapter(test_redis, "CountingSpotEngine"),
        SimpleNamespace(),
        refresh_cache=True,
    )
    p2p_dummy = type("NotSpot", (), {"is_enabled": True})()

    settings = Settings()
    with patch(
        "services.dashboard.get_ratios_engines",
        return_value=[p2p_dummy, counting],
    ):
        svc = DashboardService(test_redis, settings)
        result = await svc.update_ratios()

    assert counting.market_calls == 1
    assert result.get("CountingSpot") == {"ok": True}
    assert len(result) == 1


@pytest.mark.asyncio
async def test_update_ratios_records_error(test_redis):
    class FailingSpot(BaseRatioEngine):
        async def market(self) -> list[ExchangePair]:
            raise RuntimeError("boom")

    bad = FailingSpot(
        RatioCacheAdapter(test_redis, "FailingSpot"),
        SimpleNamespace(),
        refresh_cache=True,
    )
    settings = Settings()
    with patch("services.dashboard.get_ratios_engines", return_value=[bad]):
        svc = DashboardService(test_redis, settings)
        result = await svc.update_ratios()

    assert result["FailingSpot"]["ok"] is False
    assert "boom" in result["FailingSpot"]["error"]


def test_normalize_and_fiat_involving_pairs():
    assert _normalize_system_currencies(["usd", "USD", "rub"]) == ["USD", "RUB"]
    assert _fiat_involving_pairs(["USD", "RUB"], ["USDT"]) == [
        ("USD", "RUB"),
        ("USD", "USDT"),
        ("RUB", "USD"),
        ("RUB", "USDT"),
        ("USDT", "USD"),
        ("USDT", "RUB"),
    ]
    assert _fiat_involving_pairs(["USD"], ["USDT", "A7A5"]) == [
        ("USD", "USDT"),
        ("USD", "A7A5"),
        ("USDT", "USD"),
        ("A7A5", "USD"),
    ]


def test_dedupe_mutual_pair_rows_keeps_higher_ratio():
    rows = [
        {"base": "RUB", "quote": "USD", "pair": {"base": "RUB", "quote": "USD", "ratio": 80.0, "utc": 1.0}},
        {"base": "USD", "quote": "RUB", "pair": {"base": "USD", "quote": "RUB", "ratio": 0.0125, "utc": 1.0}},
    ]
    out = _dedupe_mutual_pair_rows(rows)
    assert len(out) == 1
    assert out[0]["base"] == "RUB"
    assert out[0]["pair"]["ratio"] == 80.0


def test_dedupe_mutual_pair_rows_prefers_non_null():
    rows = [
        {"base": "EUR", "quote": "USD", "pair": None},
        {"base": "USD", "quote": "EUR", "pair": {"base": "USD", "quote": "EUR", "ratio": 1.1, "utc": 1.0}},
    ]
    out = _dedupe_mutual_pair_rows(rows)
    assert len(out) == 1
    assert out[0]["pair"] is not None
