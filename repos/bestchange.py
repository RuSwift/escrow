"""
Репозиторий по снимку BestChange (bestchange_yaml_snapshots): только строка с max(id).
Данные из payload разворачиваются в «таблицы» платёжных методов и городов с учётом языка (i18n).
Кеш в Redis с инвалидацией при смене max(id).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models import BestchangeYamlSnapshot
from i18n.translations import normalize_locale, supported_locales
from repos.base import BaseRepository
from settings import Settings

logger = logging.getLogger(__name__)

Kind = Literal["payment_methods", "cities"]

_REDIS_SID = "bestchange_yaml:sid"
_REDIS_DATA = "bestchange_yaml:data"
# Подстраховка, если БД очищена без сброса Redis
_CACHE_TTL_SEC = 86400 * 7


class PaymentMethodRow(BaseModel):
    payment_code: str
    cur: str
    name: str = Field(description="Отображаемое имя для выбранной локали")


class CityRow(BaseModel):
    id: int
    name: str = Field(description="Отображаемое имя для выбранной локали")


class BestchangeYamlRepository(BaseRepository):
    """
    Чтение последнего снимка bc.yaml (max(id)), списки для autocomplete с Redis-кешем.
    """

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session, redis, settings)

    async def list(
        self,
        kind: Kind,
        *,
        locale: str | None = None,
        q: str | None = None,
        limit: int = 50,
    ) -> list[PaymentMethodRow] | list[CityRow]:
        """Список платёжных методов или городов с опциональным префиксом/подстрокой для autocomplete."""
        loc = normalize_locale(locale)
        tables = await self._tables()
        if kind == "payment_methods":
            rows: list[PaymentMethodRow] = tables["payment_methods"][loc]
            return self._filter_pm(rows, q, limit)
        rows_c: list[CityRow] = tables["cities"][loc]
        return self._filter_cities(rows_c, q, limit)

    async def get(
        self,
        kind: Kind,
        *,
        ref: str | int,
        locale: str | None = None,
    ) -> PaymentMethodRow | CityRow | None:
        """Один платёжный метод по payment_code или город по id."""
        loc = normalize_locale(locale)
        tables = await self._tables()
        if kind == "payment_methods":
            code = str(ref).strip()
            for row in tables["payment_methods"][loc]:
                if row.payment_code == code:
                    return row
            return None
        city_id = int(ref)
        for row in tables["cities"][loc]:
            if row.id == city_id:
                return row
        return None

    async def patch(self) -> None:
        """Сбросить кеш Redis; данные пересоберутся из БД при следующем list/get."""
        await self._redis.delete(_REDIS_SID, _REDIS_DATA)

    @staticmethod
    def _filter_pm(rows: list[PaymentMethodRow], q: str | None, limit: int) -> list[PaymentMethodRow]:
        if not q or not str(q).strip():
            return rows[:limit]
        needle = str(q).strip().lower()
        out: list[PaymentMethodRow] = []
        for r in rows:
            if needle in r.payment_code.lower() or needle in r.cur.lower() or needle in r.name.lower():
                out.append(r)
                if len(out) >= limit:
                    break
        return out

    @staticmethod
    def _filter_cities(rows: list[CityRow], q: str | None, limit: int) -> list[CityRow]:
        if not q or not str(q).strip():
            return rows[:limit]
        needle = str(q).strip().lower()
        out: list[CityRow] = []
        for r in rows:
            if needle in str(r.id) or needle in r.name.lower():
                out.append(r)
                if len(out) >= limit:
                    break
        return out

    async def _scalar_max_id(self) -> int | None:
        stmt = select(func.max(BestchangeYamlSnapshot.id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _tables(self) -> dict[str, Any]:
        """
        Возвращает словарь с ключами payment_methods, cities -> {locale: rows}.
        Кешируется в Redis целиком для snapshot_id = max(id).
        """
        max_id = await self._scalar_max_id()
        if max_id is None:
            await self._redis.delete(_REDIS_SID, _REDIS_DATA)
            return _empty_tables()

        sid_raw = await self._redis.get(_REDIS_SID)
        data_raw = await self._redis.get(_REDIS_DATA)
        if sid_raw == str(max_id) and data_raw:
            try:
                blob = json.loads(data_raw)
                return _deserialize_tables(blob)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning("bestchange_yaml: повреждённый кеш Redis, пересборка: %s", e)

        stmt = select(BestchangeYamlSnapshot).where(BestchangeYamlSnapshot.id == max_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None or row.payload is None:
            await self._redis.delete(_REDIS_SID, _REDIS_DATA)
            return _empty_tables()

        built = _build_tables_from_payload(row.payload)
        blob = _serialize_tables(built)
        pipe = self._redis.pipeline()
        pipe.set(_REDIS_SID, str(max_id), ex=_CACHE_TTL_SEC)
        pipe.set(_REDIS_DATA, json.dumps(blob, ensure_ascii=False), ex=_CACHE_TTL_SEC)
        await pipe.execute()
        return built


def _locale_codes() -> tuple[str, ...]:
    """Языки из i18n плюс en (дефолт normalize_locale), чтобы ключи кеша совпадали с list/get."""
    codes = set(supported_locales())
    codes.add("en")
    return tuple(sorted(codes))


def _empty_tables() -> dict[str, Any]:
    codes = _locale_codes()
    empty_pm = {loc: [] for loc in codes}
    empty_c = {loc: [] for loc in codes}
    return {"payment_methods": empty_pm, "cities": empty_c}


def _localize_payment_name(raw: dict[str, Any], locale: str) -> str:
    en = str(raw.get("payment_name_en") or "").strip()
    ru = str(raw.get("payment_name") or "").strip()
    if locale == "ru":
        return ru or en
    # en и прочие коды из i18n: колонка *_en в YAML, затем русская
    return en or ru


def _localize_city_name(raw: dict[str, Any], locale: str) -> str:
    en = str(raw.get("name_en") or "").strip()
    ru = str(raw.get("name") or "").strip()
    if locale == "ru":
        return ru or en
    return en or ru


def _build_tables_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = _empty_tables()
    pms = payload.get("payment_methods")
    if not isinstance(pms, list):
        pms = []
    for item in pms:
        if not isinstance(item, dict):
            continue
        code = str(item.get("payment_code") or "").strip()
        cur = str(item.get("cur") or "").strip()
        if not code:
            continue
        for loc in _locale_codes():
            out["payment_methods"][loc].append(
                PaymentMethodRow(
                    payment_code=code,
                    cur=cur,
                    name=_localize_payment_name(item, loc),
                )
            )
    # стабильный порядок для autocomplete
    for loc in _locale_codes():
        out["payment_methods"][loc].sort(key=lambda r: (r.name.lower(), r.payment_code))

    cities = payload.get("cities")
    if not isinstance(cities, list):
        cities = []
    for item in cities:
        if not isinstance(item, dict):
            continue
        if "id" not in item:
            continue
        try:
            cid = int(item["id"])
        except (TypeError, ValueError):
            continue
        for loc in _locale_codes():
            out["cities"][loc].append(
                CityRow(
                    id=cid,
                    name=_localize_city_name(item, loc),
                )
            )
    for loc in _locale_codes():
        out["cities"][loc].sort(key=lambda r: (r.name.lower() if r.name else "", r.id))

    return out


def _serialize_tables(tables: dict[str, Any]) -> dict[str, Any]:
    return {
        "payment_methods": {
            loc: [r.model_dump() for r in rows] for loc, rows in tables["payment_methods"].items()
        },
        "cities": {loc: [r.model_dump() for r in rows] for loc, rows in tables["cities"].items()},
    }


def _deserialize_tables(blob: dict[str, Any]) -> dict[str, Any]:
    pm: dict[str, list[PaymentMethodRow]] = {}
    ct: dict[str, list[CityRow]] = {}
    for loc in _locale_codes():
        pm[loc] = [PaymentMethodRow(**d) for d in blob.get("payment_methods", {}).get(loc, [])]
        ct[loc] = [CityRow(**d) for d in blob.get("cities", {}).get(loc, [])]
    return {"payment_methods": pm, "cities": ct}
