"""Схемы API /v1/simple/deals (Simple UI)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SimpleDealLegIn(BaseModel):
    asset_type: Literal["fiat", "stable"] = Field(..., description="Тип актива ноги")
    code: str = Field(..., min_length=1, max_length=32, description="Код валюты / символ стейбла")
    amount: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Десятичная сумма строкой; для counter может быть null",
    )
    side: Literal["give", "receive"] = Field(..., description="Отдаю / принимаю")
    amount_discussed: bool = Field(
        default=False,
        description="Для counter: сумма обсуждается с контрагентом",
    )


class SimpleApplicationCreateRequest(BaseModel):
    direction: Literal["fiat_to_stable", "stable_to_fiat"] = Field(...)
    primary_leg: SimpleDealLegIn
    counter_leg: SimpleDealLegIn


class SimpleDealOut(BaseModel):
    pk: int
    uid: str
    label: str
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    status: str
    requisites: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SimpleDealListResponse(BaseModel):
    items: List[SimpleDealOut]
    total: int


class SimpleApplicationCreateResponse(BaseModel):
    deal: SimpleDealOut
