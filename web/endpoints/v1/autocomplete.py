"""
Autocomplete по данным BestchangeYamlRepository (последний снимок max(id)).
Города и направления оплаты (платёжные методы) — отдельные эндпоинты.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from web.endpoints.dependencies import BestchangeRepoDep
from web.endpoints.v1.schemas.autocomplete import (
    AutocompleteCitiesResponse,
    AutocompleteCityItem,
    AutocompleteDirectionItem,
    AutocompleteDirectionsResponse,
)

_AUTOCOMPLETE_Q_DETAIL = (
    "Параметр q обязателен: минимум 1 значащий символ после удаления пробелов по краям."
)


def _require_autocomplete_q(
    q: str | None = Query(None, description="Подстрока поиска (обязательно, минимум 1 значащий символ)."),
) -> str:
    if q is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_AUTOCOMPLETE_Q_DETAIL)
    s = q.strip()
    if len(s) < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_AUTOCOMPLETE_Q_DETAIL)
    return s


AutocompleteQ = Annotated[str, Depends(_require_autocomplete_q)]

router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])


@router.get("/cities", response_model=AutocompleteCitiesResponse)
async def autocomplete_cities(
    repo: BestchangeRepoDep,
    q: AutocompleteQ,
    locale: str | None = Query(
        None,
        description="Код языка как в i18n (en, ru). Если не указан — поиск по всем локалям; в ответе имена в основном как en.",
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """Подсказки городов из bc.yaml (кеш Redis + последний снимок БД)."""
    rows = await repo.list("cities", locale=locale, q=q, limit=limit)
    return AutocompleteCitiesResponse(
        items=[AutocompleteCityItem(id=r.id, name=r.name) for r in rows],
    )


@router.get("/directions", response_model=AutocompleteDirectionsResponse)
async def autocomplete_directions(
    repo: BestchangeRepoDep,
    q: AutocompleteQ,
    locale: str | None = Query(
        None,
        description="Код языка как в i18n (en, ru). Если не указан — поиск по всем локалям; в ответе имена в основном как en.",
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """Подсказки направлений оплаты (платёжные методы) из bc.yaml."""
    rows = await repo.list("payment_methods", locale=locale, q=q, limit=limit)
    return AutocompleteDirectionsResponse(
        items=[
            AutocompleteDirectionItem(payment_code=r.payment_code, cur=r.cur, name=r.name)
            for r in rows
        ],
    )
