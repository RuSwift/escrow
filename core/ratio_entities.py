"""
Сущности для движков котировок (forex, cbr, rapira, bestchange).
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class ExchangePair(BaseModel):
    """Пара валют и курс (base/quote = ratio)."""

    base: str = Field(..., description="Базовая валюта (например USD)")
    quote: str = Field(..., description="Котируемая валюта (например RUB)")
    ratio: float = Field(..., description="Курс: 1 base = ratio quote")
    utc: float = Field(..., description="Время котировки (Unix timestamp)")


class P2POrder(BaseModel):
    """Один P2P-ордер (BestChange и др.)."""

    id: str = Field(..., description="Уникальный идентификатор ордера")
    trader_nick: str = Field(..., description="Ник трейдера/обменника")
    price: float = Field(..., description="Цена")
    min_amount: float = Field(default=0.0, description="Минимальная сумма")
    max_amount: float = Field(default=0.0, description="Максимальная сумма")
    pay_methods: List[str] = Field(default_factory=list, description="Способы оплаты")
    bestchange_codes: Optional[List[str]] = Field(default=None, description="Коды BestChange")
    utc: Optional[float] = Field(default=None, description="Время (Unix timestamp)")


class P2POrders(BaseModel):
    """Список ордеров: asks (продажа фиата за токен) и bids (покупка фиата за токен)."""

    asks: List[P2POrder] = Field(default_factory=list, description="Ордера на продажу фиата")
    bids: List[P2POrder] = Field(default_factory=list, description="Ордера на покупку фиата")
