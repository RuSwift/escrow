"""Схемы POST /v1/spaces/{space}/balances."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SpaceBalanceQueryItem(BaseModel):
    address: str = Field(..., min_length=1)
    blockchain: str = Field(
        ...,
        min_length=1,
        description="Сеть: TRON, ETH (Ethereum)",
    )
    force_update: bool = Field(
        default=False,
        description="Если true — обход Redis/кеша и запрос в API сети",
    )


class SpaceBalancesQueryRequest(BaseModel):
    items: List[SpaceBalanceQueryItem] = Field(..., min_length=1)


class SpaceBalanceItemResult(BaseModel):
    address: str
    blockchain: str
    balances_raw: Dict[str, str] = Field(
        default_factory=dict,
        description="Адрес TRC-20 контракта → баланс в base-units (строка для uint256)",
    )
    native_balances: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Нативный токен сети в base-units: для TRON ключ TRX — баланс в SUN (1 TRX = 10⁶ SUN)"
        ),
    )
    error: Optional[str] = Field(
        default=None,
        description="Код ошибки уровня реализации (например сеть пока не поддерживается)",
    )


class SpaceBalancesQueryResponse(BaseModel):
    items: List[SpaceBalanceItemResult]
