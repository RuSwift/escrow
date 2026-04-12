"""Схемы API переопределения форм payment_code в спейсе."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class EffectivePaymentFormResponse(BaseModel):
    payment_code: str
    source: Literal["exchange_service", "space", "system", "none"] = Field(
        ...,
        description=(
            "exchange_service — кастом направления (requisites_form_schema); "
            "space — override спейса; system — forms.yaml; none — не найдено"
        ),
    )
    form: Optional[dict[str, Any]] = Field(
        None,
        description="Тело PaymentForm (fields) или null если source=none",
    )


class SpacePaymentFormOverrideItem(BaseModel):
    id: int
    space: str
    payment_code: str
    form: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SpacePaymentFormOverrideSummary(BaseModel):
    """Список без полной формы (экономия трафика); для деталей — GET effective или отдельный путь."""

    id: int
    payment_code: str
    updated_at: datetime


class SpacePaymentFormOverrideListResponse(BaseModel):
    items: list[SpacePaymentFormOverrideSummary]


class PutSpacePaymentFormRequest(BaseModel):
    """Тело как у PaymentForm: { fields: [...] }."""

    fields: list[dict[str, Any]] = Field(..., description="Список полей формы реквизитов")
