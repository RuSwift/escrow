"""Схемы API /v1/spaces/{space}/exchange-services."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ExchangeServiceFeeTierIn(BaseModel):
    fiat_min: Decimal = Field(..., description="Нижняя граница суммы в фиате")
    fiat_max: Decimal = Field(..., description="Верхняя граница суммы в фиате")
    fee_percent: Decimal = Field(..., ge=Decimal("0"), description="Комиссия для диапазона, %")
    sort_order: int = 0


class ExchangeServiceFeeTierOut(BaseModel):
    id: int
    fiat_min: Decimal
    fiat_max: Decimal
    fee_percent: Decimal
    sort_order: int


class ExchangeServiceOut(BaseModel):
    id: int
    space: str
    service_type: str
    fiat_currency_code: str
    stablecoin_symbol: str
    network: str
    contract_address: str
    stablecoin_base_currency: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    payment_code: Optional[str] = None
    rate_mode: str
    manual_rate: Optional[Decimal] = None
    manual_rate_valid_until: Optional[datetime] = None
    ratios_engine_key: Optional[str] = None
    ratios_commission_percent: Optional[Decimal] = None
    min_fiat_amount: Decimal
    max_fiat_amount: Decimal
    requisites_form_schema: dict[str, Any]
    verification_requirements: dict[str, Any]
    is_active: bool
    is_deleted: bool = False
    created_at: datetime
    updated_at: datetime
    fee_tiers: list[ExchangeServiceFeeTierOut] = Field(default_factory=list)


class ExchangeServiceListResponse(BaseModel):
    items: list[ExchangeServiceOut]


class CreateExchangeServiceRequest(BaseModel):
    service_type: str = Field(..., description="on_ramp | off_ramp")
    fiat_currency_code: str = Field(..., min_length=3, max_length=3)
    stablecoin_symbol: str = Field(..., min_length=1, max_length=32)
    network: str = Field(..., min_length=1, max_length=64)
    contract_address: str = Field(..., min_length=1, max_length=128)
    stablecoin_base_currency: Optional[str] = Field(None, max_length=3)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    payment_code: Optional[str] = Field(None, max_length=128)
    rate_mode: str = Field(..., description="manual | on_request | ratios")
    manual_rate: Optional[Decimal] = None
    manual_rate_valid_until: Optional[datetime] = None
    ratios_engine_key: Optional[str] = Field(None, max_length=255)
    ratios_commission_percent: Optional[Decimal] = None
    min_fiat_amount: Decimal
    max_fiat_amount: Decimal
    requisites_form_schema: dict[str, Any] = Field(default_factory=dict)
    verification_requirements: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Произвольный JSON; для наличных (cash): "
            "`cash: true`, `cash_cities: [{id?, name}]`, при этом `payment_code` должен быть `CASH`+ISO фиата."
        ),
    )
    is_active: bool = True
    fee_tiers: Optional[list[ExchangeServiceFeeTierIn]] = None


class PatchExchangeServiceRequest(BaseModel):
    service_type: Optional[str] = None
    fiat_currency_code: Optional[str] = Field(None, min_length=3, max_length=3)
    stablecoin_symbol: Optional[str] = Field(None, min_length=1, max_length=32)
    network: Optional[str] = Field(None, min_length=1, max_length=64)
    contract_address: Optional[str] = Field(None, min_length=1, max_length=128)
    stablecoin_base_currency: Optional[str] = Field(None, max_length=3)
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    payment_code: Optional[str] = Field(None, max_length=128)
    rate_mode: Optional[str] = None
    manual_rate: Optional[Decimal] = None
    manual_rate_valid_until: Optional[datetime] = None
    ratios_engine_key: Optional[str] = Field(None, max_length=255)
    ratios_commission_percent: Optional[Decimal] = None
    min_fiat_amount: Optional[Decimal] = None
    max_fiat_amount: Optional[Decimal] = None
    requisites_form_schema: Optional[dict[str, Any]] = None
    verification_requirements: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    fee_tiers: Optional[list[ExchangeServiceFeeTierIn]] = None
    replace_fee_tiers: bool = Field(
        False,
        description="Если true — заменить сетку комиссий на fee_tiers (пустой список удаляет все)",
    )


def exchange_service_to_out(row, tiers) -> ExchangeServiceOut:
    ft_out = [
        ExchangeServiceFeeTierOut(
            id=int(t.id),
            fiat_min=t.fiat_min,
            fiat_max=t.fiat_max,
            fee_percent=t.fee_percent,
            sort_order=int(t.sort_order),
        )
        for t in tiers
    ]
    return ExchangeServiceOut(
        id=int(row.id),
        space=row.space,
        service_type=row.service_type,
        fiat_currency_code=row.fiat_currency_code,
        stablecoin_symbol=row.stablecoin_symbol,
        network=row.network,
        contract_address=row.contract_address,
        stablecoin_base_currency=row.stablecoin_base_currency,
        title=row.title,
        description=row.description,
        payment_code=row.payment_code,
        rate_mode=row.rate_mode,
        manual_rate=row.manual_rate,
        manual_rate_valid_until=row.manual_rate_valid_until,
        ratios_engine_key=row.ratios_engine_key,
        ratios_commission_percent=row.ratios_commission_percent,
        min_fiat_amount=row.min_fiat_amount,
        max_fiat_amount=row.max_fiat_amount,
        requisites_form_schema=dict(row.requisites_form_schema or {}),
        verification_requirements=dict(row.verification_requirements or {}),
        is_active=bool(row.is_active),
        is_deleted=bool(row.is_deleted),
        created_at=row.created_at,
        updated_at=row.updated_at,
        fee_tiers=ft_out,
    )
