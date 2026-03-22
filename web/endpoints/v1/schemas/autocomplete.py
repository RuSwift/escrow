"""Схемы ответов для GET /v1/autocomplete/cities, directions, currencies."""
from pydantic import BaseModel, Field


class AutocompleteCityItem(BaseModel):
    id: int
    name: str = Field(description="Название города для выбранной локали")


class AutocompleteCitiesResponse(BaseModel):
    items: list[AutocompleteCityItem]


class AutocompleteDirectionItem(BaseModel):
    """Платёжный метод из снимка BestChange (направление оплаты)."""

    payment_code: str
    cur: str
    name: str = Field(description="Отображаемое имя для выбранной локали")


class AutocompleteDirectionsResponse(BaseModel):
    items: list[AutocompleteDirectionItem]
    total_for_cur: int | None = Field(
        default=None,
        description="Сколько платёжных методов для cur в снимке; только если query-параметр cur задан.",
    )


class AutocompleteCurrencyItem(BaseModel):
    code: str = Field(description="Код валюты (поле cur из bc.yaml)")


class AutocompleteCurrenciesResponse(BaseModel):
    items: list[AutocompleteCurrencyItem]
