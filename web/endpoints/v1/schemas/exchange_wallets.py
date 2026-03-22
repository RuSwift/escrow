"""Схемы API /v1/spaces/{space}/exchange-wallets."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ExchangeWalletItem(BaseModel):
    id: int
    name: str
    tron_address: str
    ethereum_address: str
    role: Literal["external", "multisig"]
    owner_did: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExchangeWalletListResponse(BaseModel):
    items: List[ExchangeWalletItem]


class CreateExchangeWalletRequest(BaseModel):
    name: str = Field(..., max_length=255)
    role: Literal["external", "multisig"]
    tron_address: str = Field(..., max_length=34)
    ethereum_address: str = Field(..., max_length=42)
    mnemonic: Optional[str] = Field(
        default=None,
        description="Мнемоника в открытом виде; на сервере шифруется. Для multisig обязательна (после нормализации).",
    )


class PatchExchangeWalletRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    tron_address: Optional[str] = Field(None, max_length=34)
    ethereum_address: Optional[str] = Field(None, max_length=42)
    mnemonic: Optional[str] = Field(
        default=None,
        description="Новая мнемоника или пустая строка для сброса (только вместе с переходом на external).",
    )
