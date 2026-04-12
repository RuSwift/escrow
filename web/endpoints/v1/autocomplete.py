"""
Autocomplete по данным BestchangeYamlRepository (последний снимок max(id)).
Города и направления оплаты (платёжные методы) — отдельные эндпоинты.
"""
from fastapi import APIRouter, Query

from services.guarantor import list_autocomplete_fiat_currencies
from web.endpoints.dependencies import AppSettings, BestchangeRepoDep, RedisClient
from web.endpoints.v1.schemas.autocomplete import (
    AutocompleteCitiesResponse,
    AutocompleteCityItem,
    AutocompleteCurrenciesResponse,
    AutocompleteCurrencyItem,
    AutocompleteDirectionItem,
    AutocompleteDirectionsResponse,
)

def _autocomplete_q_normalized(q: str | None) -> str | None:
    """None или пустая строка после trim — без фильтра по подстроке (первые ``limit`` строк)."""
    if q is None:
        return None
    s = q.strip()
    return s if s else None


router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])


@router.get("/cities", response_model=AutocompleteCitiesResponse)
async def autocomplete_cities(
    repo: BestchangeRepoDep,
    q: str | None = Query(
        None,
        description="Подстрока поиска; если не задана или пустая — первые limit городов.",
    ),
    locale: str | None = Query(
        None,
        description=(
            "Код языка как в i18n (en, ru): имена в ответе на этом языке; "
            "подстрока q ищется по всем локалям. Если не указан — см. репозиторий (ru затем en)."
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """Подсказки городов из bc.yaml (кеш Redis + последний снимок БД)."""
    rows = await repo.list("cities", locale=locale, q=_autocomplete_q_normalized(q), limit=limit)
    return AutocompleteCitiesResponse(
        items=[AutocompleteCityItem(id=r.id, name=r.name) for r in rows],
    )


@router.get("/directions", response_model=AutocompleteDirectionsResponse)
async def autocomplete_directions(
    repo: BestchangeRepoDep,
    q: str | None = Query(
        None,
        description="Подстрока; если не задана или пустая — первые limit методов (с учётом cur).",
    ),
    locale: str | None = Query(
        None,
        description="Код языка как в i18n (en, ru). Если не указан — поиск по всем локалям; в ответе имена в основном как en.",
    ),
    limit: int = Query(50, ge=1, le=200),
    cur: str | None = Query(
        None,
        description="Если указан — только платёжные методы с этой валютой (поле cur).",
    ),
):
    """Подсказки направлений оплаты (платёжные методы) из bc.yaml."""
    rows = await repo.list(
        "payment_methods",
        locale=locale,
        q=_autocomplete_q_normalized(q),
        limit=limit,
        cur=cur,
    )
    total_for_cur = await repo.count_payment_methods_for_currency(locale=locale, cur=cur)
    return AutocompleteDirectionsResponse(
        items=[
            AutocompleteDirectionItem(payment_code=r.payment_code, cur=r.cur, name=r.name)
            for r in rows
        ],
        total_for_cur=total_for_cur,
    )


@router.get("/currencies", response_model=AutocompleteCurrenciesResponse)
async def autocomplete_currencies(
    repo: BestchangeRepoDep,
    redis: RedisClient,
    app_settings: AppSettings,
    q: str | None = Query(
        None,
        description="Подстрока; если не задана или пустая — первые limit кодов валют.",
    ),
    limit: int = Query(50, ge=1, le=200),
    is_fiat: bool = Query(
        False,
        description=(
            "Allowlist: сначала forex_currencies из снимка bc.yaml (если задан непустой список), "
            "иначе коды из ForexEngine; только активные ISO 4217 (без криптовалют из API). "
            "При пустом q — сначала коды из Settings.system_currencies (в порядке настроек), затем остальные; "
            "при непустом q — совпадения из BestChange, затем добор из allowlist."
        ),
    ),
):
    """Подсказки валют — уникальные коды cur из платёжных методов снимка bc.yaml (язык не влияет на коды)."""
    qn = _autocomplete_q_normalized(q)
    if is_fiat:
        rows = await list_autocomplete_fiat_currencies(
            repo,
            redis,
            app_settings.settings,
            qn,
            limit,
        )
        return AutocompleteCurrenciesResponse(
            items=[AutocompleteCurrencyItem(code=r.code) for r in rows],
        )
    rows = await repo.list("currencies", q=qn, limit=limit)
    return AutocompleteCurrenciesResponse(items=[AutocompleteCurrencyItem(code=r.code) for r in rows])
