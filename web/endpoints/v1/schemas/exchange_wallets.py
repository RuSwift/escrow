"""Схемы API /v1/spaces/{space}/exchange-wallets."""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ExchangeWalletItem(BaseModel):
    id: int
    name: str
    tron_address: Optional[str] = None
    ethereum_address: Optional[str] = None
    role: Literal["external", "multisig"]
    owner_did: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExchangeWalletListResponse(BaseModel):
    items: List[ExchangeWalletItem]


class CreateExchangeWalletRequest(BaseModel):
    """
    Создание Ramp-кошелька (POST).
    external: либо participant_sub_id, либо пара name + tron_address (произвольный).
    multisig: только name; мнемоника и адреса генерируются на сервере.
    """

    role: Literal["external", "multisig"]
    blockchain: Literal["tron"] = "tron"
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Обязательно для multisig и external с произвольным адресом; для participant_sub_id игнорируется",
    )
    tron_address: Optional[str] = Field(
        default=None,
        max_length=34,
        description="Только для external без participant_sub_id",
    )
    participant_sub_id: Optional[int] = Field(
        default=None,
        description="ID WalletUserSub участника спейса (external)",
    )

    @model_validator(mode="after")
    def validate_shape(self) -> CreateExchangeWalletRequest:
        if self.role == "multisig":
            if not (self.name or "").strip():
                raise ValueError("name is required for multisig")
            if self.participant_sub_id is not None:
                raise ValueError("participant_sub_id is not allowed for multisig")
            if (self.tron_address or "").strip():
                raise ValueError("tron_address is not allowed for multisig")
            return self

        # external
        if self.participant_sub_id is not None:
            if (self.tron_address or "").strip():
                raise ValueError(
                    "tron_address must not be set when participant_sub_id is set",
                )
            if (self.name or "").strip():
                raise ValueError(
                    "name must not be set when participant_sub_id is set (server-derived)",
                )
            return self

        if not (self.name or "").strip():
            raise ValueError("name is required for external wallet with custom address")
        if not (self.tron_address or "").strip():
            raise ValueError("tron_address is required for external wallet without participant_sub_id")
        return self


class PatchExchangeWalletRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    tron_address: Optional[str] = Field(None, max_length=34)
    ethereum_address: Optional[str] = Field(None, max_length=42)
    mnemonic: Optional[str] = Field(
        default=None,
        description="Новая мнемоника или пустая строка для сброса (только вместе с переходом на external).",
    )
