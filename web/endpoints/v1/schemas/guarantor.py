"""Схемы API /v1/spaces/{space}/guarantor."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class GuarantorProfileResponse(BaseModel):
    id: int
    wallet_user_id: int
    space: str
    commission_percent: Optional[Decimal] = None
    conditions_text: Optional[str] = None


class GuarantorDirectionResponse(BaseModel):
    id: int
    space: str
    currency_code: str
    payment_code: str
    payment_name: Optional[str] = None
    conditions_text: Optional[str] = None
    commission_percent: Optional[Decimal] = None
    sort_order: int


class GuarantorStateResponse(BaseModel):
    profile: GuarantorProfileResponse
    directions: list[GuarantorDirectionResponse]
    is_verified: bool


class PatchGuarantorProfileRequest(BaseModel):
    commission_percent: Optional[Decimal] = Field(
        None,
        description="Базовая комиссия %; не ниже 0.1 при указании.",
    )
    conditions_text: Optional[str] = Field(None, description="Общие условия гаранта в space")


class PatchGuarantorDirectionRequest(BaseModel):
    conditions_text: Optional[str] = Field(
        ...,
        description="Текст условий направления; пустая строка или null сбрасывает поле.",
    )


class CreateGuarantorDirectionRequest(BaseModel):
    currency_code: str = Field(..., min_length=1, max_length=64)
    payment_code: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description='Код метода из BestChange; «*» означает все способы оплаты для валюты (исключает другие направления с той же валютой).',
    )
    payment_name: Optional[str] = Field(None, max_length=512)
    conditions_text: Optional[str] = None
    commission_percent: Optional[Decimal] = None
    sort_order: int = 0
