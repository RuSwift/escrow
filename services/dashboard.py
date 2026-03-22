"""
Дашборд: спотовые котировки (движки BaseRatioEngine). BestChangeRatios не участвует.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Type

from redis.asyncio import Redis

from services.ratios import get_ratios_engines
from services.ratios.base import BaseRatioEngine
from settings import Settings


def _normalize_system_currencies(codes: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for c in codes:
        u = (c or "").strip().upper()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _stablecoin_symbols(settings: Settings) -> List[str]:
    """Символы токенов из каталога залоговых стейблкоинов (USDT, A5A7, …)."""
    raw = [(t.symbol or "").strip().upper() for t in settings.collateral_stablecoin.tokens]
    return _normalize_system_currencies(raw)


def _fiat_involving_pairs(
    fiats: List[str],
    stable_symbols: List[str],
) -> List[tuple[str, str]]:
    """
    Все упорядоченные пары (base, quote), base != quote, где оба кода из объединения
    фиатов и стейблов, и хотя бы один код — из ``fiats`` (фиаты сервиса).
    Так попадают кроссы вроде USDT/RUB с Rapira, но не пара только между стейблами.
    """
    fiat_set = set(fiats)
    universe: List[str] = list(fiats)
    for s in stable_symbols:
        if s not in fiat_set:
            universe.append(s)
    out: List[tuple[str, str]] = []
    for base in universe:
        for quote in universe:
            if base == quote:
                continue
            if base not in fiat_set and quote not in fiat_set:
                continue
            out.append((base, quote))
    return out


def _dedupe_mutual_pair_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Для двух направлений одной пары валют (A/B и B/A) оставляет одну строку —
    с бо́льшим ``pair.ratio``. Если только одна сторона с котировкой — её; если обе
    без ``pair`` — первая по порядку исходного списка.
    Порядок в ответе: как первое вхождение каждой неупорядоченной пары в ``rows``.
    """
    order: List[tuple[str, str]] = []
    by_key: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        key = tuple(sorted([row["base"], row["quote"]]))
        if key not in by_key:
            order.append(key)
            by_key[key] = []
        by_key[key].append(row)

    out: List[Dict[str, Any]] = []
    for key in order:
        group = by_key[key]
        if len(group) == 1:
            out.append(group[0])
            continue
        with_ratio = [r for r in group if r.get("pair") is not None]
        if len(with_ratio) >= 2:
            out.append(max(with_ratio, key=lambda r: float(r["pair"]["ratio"])))
        elif len(with_ratio) == 1:
            out.append(with_ratio[0])
        else:
            out.append(group[0])
    return out


class DashboardService:
    """Работа с котировками для дашборда (только BaseRatioEngine)."""

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    def _spot_engines(self, *, refresh_cache: bool) -> List[BaseRatioEngine]:
        engines = get_ratios_engines(
            self._redis,
            self._settings.ratios,
            refresh_cache=refresh_cache,
        )
        return [
            e
            for e in engines
            if isinstance(e, BaseRatioEngine) and e.is_enabled
        ]

    async def list_ratios(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Кросс-курсы для пар, где участвует хотя бы один фиат из
        ``Settings.system_currencies``, а второй код — фиат или символ стейблкоина
        из ``collateral_stablecoin.tokens`` (USDT/RUB, RUB/USDT и т.д.).
        Значение ``pair`` — JSON ``ExchangePair`` или ``null``, если курс недоступен.
        Для взаимных направлений (A/B и B/A) в ответе одна строка — с большим
        ``pair.ratio``.

        Публичный HTTP-эндпоинт котировок читает снимок из БД (``dashboard_state``);
        этот метод используется фоном (cron) для построения снимка после прогрева Redis.
        """
        fiats = _normalize_system_currencies(self._settings.system_currencies)
        stables = _stablecoin_symbols(self._settings)
        pairs = _fiat_involving_pairs(fiats, stables)
        result: Dict[str, List[Dict[str, Any]]] = {}
        for engine in self._spot_engines(refresh_cache=False):
            label = type(engine).get_label()
            rows: List[Dict[str, Any]] = []
            for base, quote in pairs:
                ex = await engine.ratio(base, quote)
                rows.append(
                    {
                        "base": base,
                        "quote": quote,
                        "pair": ex.model_dump(mode="json") if ex is not None else None,
                    }
                )
            result[label] = _dedupe_mutual_pair_rows(rows)
        return result

    async def list_ratios_for_engine_types(
        self,
        only_engine_types: Tuple[Type[BaseRatioEngine], ...],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Котировки только для указанных классов движков (те же пары и дедуп, что в
        ``list_ratios``). Используется cron-ом для частичного сохранения в БД.
        """
        fiats = _normalize_system_currencies(self._settings.system_currencies)
        stables = _stablecoin_symbols(self._settings)
        pairs = _fiat_involving_pairs(fiats, stables)
        result: Dict[str, List[Dict[str, Any]]] = {}
        for engine in self._spot_engines(refresh_cache=False):
            if not isinstance(engine, only_engine_types):
                continue
            label = type(engine).get_label()
            rows: List[Dict[str, Any]] = []
            for base, quote in pairs:
                ex = await engine.ratio(base, quote)
                rows.append(
                    {
                        "base": base,
                        "quote": quote,
                        "pair": ex.model_dump(mode="json") if ex is not None else None,
                    }
                )
            result[label] = _dedupe_mutual_pair_rows(rows)
        return result

    async def update_ratios(
        self,
        *,
        only_engine_types: Optional[
            Tuple[Type[BaseRatioEngine], ...]
        ] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Принудительное обновление кэша ``market`` у спотовых движков
        (``refresh_cache=True`` при сборке).

        Если задан ``only_engine_types``, обновляются только движки этого типа
        (``isinstance`` по кортежу классов, напр. ``(ForexEngine, RapiraEngine)``).
        """
        out: Dict[str, Dict[str, Any]] = {}
        for engine in self._spot_engines(refresh_cache=True):
            if only_engine_types is not None and not isinstance(
                engine, only_engine_types
            ):
                continue
            label = type(engine).get_label()
            try:
                await engine.market()
                out[label] = {"ok": True}
            except Exception as exc:  # noqa: BLE001 — отдаём текст в дашборд
                out[label] = {"ok": False, "error": str(exc)}
        return out
