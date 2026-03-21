"""Схемы ответов для GET /v1/autocomplete/cities и /v1/autocomplete/directions."""
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
