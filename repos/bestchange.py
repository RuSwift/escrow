"""
Репозиторий по снимку BestChange (bestchange_yaml_snapshots): только строка с max(id).
Данные из payload разворачиваются в «таблицы» платёжных методов и городов с учётом языка (i18n).
Кеш в Redis с инвалидацией при смене max(id).
Опционально: список кодов forex-валют в payload.forex_currencies (или meta.forex_currencies) для autocomplete is_fiat.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models import BestchangeYamlSnapshot
from i18n.translations import normalize_locale, supported_locales
from core.bc import PaymentForm, PaymentFormsYaml
from repos.base import BaseRepository
from settings import Settings

logger = logging.getLogger(__name__)

Kind = Literal["payment_methods", "cities", "currencies"]

_REDIS_SID = "bestchange_yaml:sid"
_REDIS_DATA = "bestchange_yaml:data"
_REDIS_FOREX_SID = "bestchange_yaml:forex_sid"
_REDIS_FOREX_CODES = "bestchange_yaml:forex_codes"
# Кеш ``forms.yaml`` (содержимое по SHA-256)
_REDIS_PAYMENT_FORMS_SID = "payment_forms:sid"
_REDIS_PAYMENT_FORMS_DATA = "payment_forms:data"
# Подстраховка, если БД очищена без сброса Redis
_CACHE_TTL_SEC = 86400 * 7


def _casefold_ci(s: str) -> str:
    """Безрегистровое сравнение подстрок (Unicode, предпочтительнее чем lower())."""
    return (s or "").casefold()


def _forex_currency_codes_from_payload(payload: dict[str, Any]) -> set[str]:
    """
    Коды из необязательного списка forex_currencies в корне payload или в meta.
    Пустой набор, если ключа нет или список пуст — тогда autocomplete is_fiat использует Forex ratios.
    """
    raw = payload.get("forex_currencies")
    if raw is None:
        meta = payload.get("meta")
        if isinstance(meta, dict):
            raw = meta.get("forex_currencies")
    if raw is None:
        return set()
    if not isinstance(raw, list):
        return set()
    out: set[str] = set()
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.add(item.strip().upper())
    return out


def _locale_provided(locale: str | None) -> bool:
    """False — язык не задан: list() ищет по всем локалям (имена en/ru и т.д.)."""
    return locale is not None and bool(str(locale).strip())


def _canonical_pm_map(tables: dict[str, Any]) -> dict[str, PaymentMethodRow]:
    """Одна строка на payment_code: предпочтительно локаль en для поля name."""
    pm = tables["payment_methods"]
    codes: set[str] = set()
    for loc in pm:
        for r in pm[loc]:
            codes.add(r.payment_code)
    out: dict[str, PaymentMethodRow] = {}
    for code in codes:
        chosen: PaymentMethodRow | None = None
        for r in pm.get("en", []):
            if r.payment_code == code:
                chosen = r
                break
        if chosen is None:
            for loc in sorted(pm.keys()):
                for r in pm[loc]:
                    if r.payment_code == code:
                        chosen = r
                        break
                if chosen is not None:
                    break
        if chosen is not None:
            out[code] = chosen
    return out


def _canonical_city_map(tables: dict[str, Any]) -> dict[int, CityRow]:
    """Одна строка на id города: предпочтительно en."""
    ct = tables["cities"]
    ids: set[int] = set()
    for loc in ct:
        for r in ct[loc]:
            ids.add(r.id)
    out: dict[int, CityRow] = {}
    for cid in ids:
        chosen: CityRow | None = None
        for r in ct.get("en", []):
            if r.id == cid:
                chosen = r
                break
        if chosen is None:
            for loc in sorted(ct.keys()):
                for r in ct[loc]:
                    if r.id == cid:
                        chosen = r
                        break
                if chosen is not None:
                    break
        if chosen is not None:
            out[cid] = chosen
    return out


def _pm_code_matches_any_locale(
    tables: dict[str, Any],
    code: str,
    needle: str,
) -> bool:
    pm = tables["payment_methods"]
    for loc in pm:
        for r in pm[loc]:
            if r.payment_code != code:
                continue
            if (
                needle in _casefold_ci(r.payment_code)
                or needle in _casefold_ci(r.cur)
                or needle in _casefold_ci(r.name)
            ):
                return True
    return False


def _city_id_matches_any_locale(tables: dict[str, Any], city_id: int, needle: str) -> bool:
    ct = tables["cities"]
    for loc in ct:
        for r in ct[loc]:
            if r.id != city_id:
                continue
            if needle in _casefold_ci(str(r.id)) or needle in _casefold_ci(r.name):
                return True
    return False


def _filter_pm_all_locales(
    tables: dict[str, Any],
    q: str | None,
    limit: int,
    cur: str | None = None,
) -> list[PaymentMethodRow]:
    canonical = _canonical_pm_map(tables)
    if cur and str(cur).strip():
        want = _casefold_ci(str(cur).strip())
        canonical = {k: v for k, v in canonical.items() if _casefold_ci(v.cur) == want}
    if not canonical:
        return []
    if not q or not str(q).strip():
        codes = sorted(
            canonical.keys(),
            key=lambda c: (_casefold_ci(canonical[c].name), c),
        )
        return [canonical[c] for c in codes[:limit]]
    needle = _casefold_ci(str(q).strip())
    out: list[PaymentMethodRow] = []
    for code in sorted(canonical.keys(), key=lambda c: (_casefold_ci(canonical[c].name), c)):
        if _pm_code_matches_any_locale(tables, code, needle):
            out.append(canonical[code])
            if len(out) >= limit:
                break
    return out


def _filter_pm_by_cur(rows: list[PaymentMethodRow], cur: str | None) -> list[PaymentMethodRow]:
    if not cur or not str(cur).strip():
        return rows
    want = _casefold_ci(str(cur).strip())
    return [r for r in rows if _casefold_ci(r.cur) == want]


def _filter_currencies(tables: dict[str, Any], q: str | None, limit: int) -> list[CurrencyRow]:
    canonical = _canonical_pm_map(tables)
    codes_set: set[str] = set()
    for r in canonical.values():
        c = (r.cur or "").strip()
        if c:
            codes_set.add(c)
    codes_sorted = sorted(codes_set, key=lambda x: _casefold_ci(x))
    if not q or not str(q).strip():
        return [CurrencyRow(code=c) for c in codes_sorted[:limit]]
    needle = _casefold_ci(str(q).strip())
    out: list[CurrencyRow] = []
    for c in codes_sorted:
        if needle in _casefold_ci(c):
            out.append(CurrencyRow(code=c))
            if len(out) >= limit:
                break
    return out


def _filter_cities_all_locales(tables: dict[str, Any], q: str | None, limit: int) -> list[CityRow]:
    canonical = _canonical_city_map(tables)
    if not canonical:
        return []
    if not q or not str(q).strip():
        cids = sorted(
            canonical.keys(),
            key=lambda i: (_casefold_ci(canonical[i].name), i),
        )
        return [canonical[c] for c in cids[:limit]]
    needle = _casefold_ci(str(q).strip())
    out: list[CityRow] = []
    for cid in sorted(canonical.keys(), key=lambda i: (_casefold_ci(canonical[i].name), i)):
        if _city_id_matches_any_locale(tables, cid, needle):
            out.append(canonical[cid])
            if len(out) >= limit:
                break
    return out


def _pm_count_for_currency(tables: dict[str, Any], locale: str | None, cur: str) -> int:
    """Сколько платёжных методов с данной валютой в снимке (без учёта q и limit)."""
    if not cur or not str(cur).strip():
        return 0
    cur_s = str(cur).strip()
    if not _locale_provided(locale):
        canonical = _canonical_pm_map(tables)
        want = _casefold_ci(cur_s)
        return sum(1 for v in canonical.values() if _casefold_ci(v.cur) == want)
    loc = normalize_locale(locale)
    rows_pm = tables["payment_methods"][loc]
    return len(_filter_pm_by_cur(rows_pm, cur_s))


class PaymentMethodRow(BaseModel):
    payment_code: str
    cur: str
    name: str = Field(description="Отображаемое имя для выбранной локали")


class CityRow(BaseModel):
    id: int
    name: str = Field(description="Отображаемое имя для выбранной локали")


class CurrencyRow(BaseModel):
    """Уникальный код валюты (поле cur) из платёжных методов снимка."""

    code: str


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
        cur: str | None = None,
    ) -> list[PaymentMethodRow] | list[CityRow] | list[CurrencyRow]:
        """
        Список для autocomplete. Если locale не задан — поиск по всем локалям (имена en, ru, …);
        в ответе name как у локали en, иначе первая доступная. Если locale задан — только эта локаль.
        Для kind=currencies locale не влияет на набор кодов (уникальные cur из платёжных методов).
        Для payment_methods при непустом cur — только методы с этой валютой (безрегистровое сравнение);
        limit и q применяются уже внутри этой выборки (при пустом q — первые limit методов по валюте).
        """
        tables = await self._tables()
        if kind == "currencies":
            return _filter_currencies(tables, q, limit)
        if not _locale_provided(locale):
            if kind == "payment_methods":
                return _filter_pm_all_locales(tables, q, limit, cur)
            return _filter_cities_all_locales(tables, q, limit)
        loc = normalize_locale(locale)
        if kind == "payment_methods":
            rows_pm: list[PaymentMethodRow] = tables["payment_methods"][loc]
            rows_scoped = _filter_pm_by_cur(rows_pm, cur)
            return self._filter_pm(rows_scoped, q, limit)
        rows_c: list[CityRow] = tables["cities"][loc]
        return self._filter_cities(rows_c, q, limit)

    async def count_payment_methods_for_currency(
        self,
        *,
        locale: str | None = None,
        cur: str | None = None,
    ) -> int | None:
        """Число методов для ``cur`` в снимке; ``None`` если ``cur`` не задан."""
        if cur is None or not str(cur).strip():
            return None
        tables = await self._tables()
        return _pm_count_for_currency(tables, locale, str(cur).strip())

    async def get(
        self,
        kind: Kind,
        *,
        ref: str | int,
        locale: str | None = None,
    ) -> PaymentMethodRow | CityRow | None:
        """Один платёжный метод по payment_code или город по id."""
        if kind == "currencies":
            return None
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

    async def snapshot_forex_currency_codes(self) -> set[str]:
        """
        Коды forex из последнего снимка: ``forex_currencies`` в корне payload или в ``meta``.
        Если ключа нет или список пуст — ``set()`` (для autocomplete is_fiat тогда используют Forex ratios).
        Кеш Redis по ``max(id)`` снимка.
        """
        max_id = await self._scalar_max_id()
        if max_id is None:
            await self._redis.delete(_REDIS_FOREX_SID, _REDIS_FOREX_CODES)
            return set()

        sid_raw = await self._redis.get(_REDIS_FOREX_SID)
        data_raw = await self._redis.get(_REDIS_FOREX_CODES)
        if sid_raw == str(max_id) and data_raw is not None:
            try:
                arr = json.loads(data_raw)
                if isinstance(arr, list):
                    return {str(x).strip().upper() for x in arr if str(x).strip()}
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("bestchange_yaml: повреждённый кеш forex_codes, пересборка: %s", e)

        stmt = select(BestchangeYamlSnapshot).where(BestchangeYamlSnapshot.id == max_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None or row.payload is None:
            await self._redis.delete(_REDIS_FOREX_SID, _REDIS_FOREX_CODES)
            return set()

        pl = row.payload if isinstance(row.payload, dict) else {}
        codes = _forex_currency_codes_from_payload(pl)
        payload_list = sorted(codes)
        pipe = self._redis.pipeline()
        pipe.set(_REDIS_FOREX_SID, str(max_id), ex=_CACHE_TTL_SEC)
        pipe.set(_REDIS_FOREX_CODES, json.dumps(payload_list, ensure_ascii=False), ex=_CACHE_TTL_SEC)
        await pipe.execute()
        return codes

    async def patch(self) -> None:
        """Сбросить кеш Redis; данные пересоберутся из БД при следующем list/get."""
        await self._redis.delete(_REDIS_SID, _REDIS_DATA, _REDIS_FOREX_SID, _REDIS_FOREX_CODES)

    @staticmethod
    def _filter_pm(rows: list[PaymentMethodRow], q: str | None, limit: int) -> list[PaymentMethodRow]:
        if not q or not str(q).strip():
            return rows[:limit]
        needle = _casefold_ci(str(q).strip())
        out: list[PaymentMethodRow] = []
        for r in rows:
            if (
                needle in _casefold_ci(r.payment_code)
                or needle in _casefold_ci(r.cur)
                or needle in _casefold_ci(r.name)
            ):
                out.append(r)
                if len(out) >= limit:
                    break
        return out

    @staticmethod
    def _filter_cities(rows: list[CityRow], q: str | None, limit: int) -> list[CityRow]:
        if not q or not str(q).strip():
            return rows[:limit]
        needle = _casefold_ci(str(q).strip())
        out: list[CityRow] = []
        for r in rows:
            if needle in _casefold_ci(str(r.id)) or needle in _casefold_ci(r.name):
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
            await self._redis.delete(_REDIS_SID, _REDIS_DATA, _REDIS_FOREX_SID, _REDIS_FOREX_CODES)
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
            await self._redis.delete(_REDIS_SID, _REDIS_DATA, _REDIS_FOREX_SID, _REDIS_FOREX_CODES)
            return _empty_tables()

        built = _build_tables_from_payload(row.payload)
        blob = _serialize_tables(built)
        pipe = self._redis.pipeline()
        pipe.set(_REDIS_SID, str(max_id), ex=_CACHE_TTL_SEC)
        pipe.set(_REDIS_DATA, json.dumps(blob, ensure_ascii=False), ex=_CACHE_TTL_SEC)
        await pipe.execute()
        return built


class PaymentFormsYamlRepository(BaseRepository):
    """
    Чтение ``forms.yaml`` с диска (путь из Settings), кеш в Redis по SHA-256 файла.
    """

    async def get_form(self, payment_code: str) -> PaymentForm | None:
        """Форма реквизитов по ``payment_code`` (ключ как в bc.yaml); нормализация — только strip."""
        code = (payment_code or "").strip()
        if not code:
            return None
        data = await self._load_all_cached()
        if data is None:
            return None
        return data.forms.get(code)

    async def get_all(self) -> PaymentFormsYaml | None:
        """Весь документ ``forms.yaml`` или ``None``, если файл отсутствует / битый."""
        return await self._load_all_cached()

    async def patch(self) -> None:
        """Сбросить кеш Redis; при следующем запросе файл перечитается с диска."""
        await self._redis.delete(_REDIS_PAYMENT_FORMS_SID, _REDIS_PAYMENT_FORMS_DATA)

    async def _load_all_cached(self) -> PaymentFormsYaml | None:
        path = self._settings.payment_forms_yaml_path
        if not path.is_file():
            logger.warning("payment_forms: файл не найден: %s", path)
            await self._redis.delete(_REDIS_PAYMENT_FORMS_SID, _REDIS_PAYMENT_FORMS_DATA)
            return None
        try:
            raw = path.read_bytes()
        except OSError as exc:
            logger.warning("payment_forms: не удалось прочитать %s: %s", path, exc)
            return None

        digest = hashlib.sha256(raw).hexdigest()
        sid_raw = await self._redis.get(_REDIS_PAYMENT_FORMS_SID)
        data_raw = await self._redis.get(_REDIS_PAYMENT_FORMS_DATA)
        if sid_raw == digest and data_raw is not None:
            try:
                return PaymentFormsYaml.model_validate(json.loads(data_raw))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning("payment_forms: повреждённый кеш Redis, перечитка: %s", exc)

        try:
            parsed = PaymentFormsYaml.model_validate_yaml(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("payment_forms: невалидный YAML %s: %s", path, exc)
            return None

        payload = json.dumps(parsed.model_dump(mode="json"), ensure_ascii=False)
        pipe = self._redis.pipeline()
        pipe.set(_REDIS_PAYMENT_FORMS_SID, digest, ex=_CACHE_TTL_SEC)
        pipe.set(_REDIS_PAYMENT_FORMS_DATA, payload, ex=_CACHE_TTL_SEC)
        await pipe.execute()
        return parsed


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
