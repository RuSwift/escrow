"""Схемы заявки на вывод."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from web.endpoints.v1.schemas.orders import OrderItem


class WithdrawalCreateRequest(BaseModel):
    wallet_id: int = Field(..., ge=1)
    token_type: str = Field(..., description="native | trc20")
    symbol: str = Field(..., min_length=1, max_length=32)
    contract_address: Optional[str] = Field(
        default=None,
        description="TRC-20 contract base58; обязателен для trc20",
    )
    amount_raw: int = Field(..., gt=0, description="SUN или минимальные единицы токена")
    destination_address: str = Field(..., min_length=26, max_length=64)
    purpose: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Назначение платежа (обязательный комментарий)",
    )

    @field_validator("purpose")
    @classmethod
    def purpose_stripped_nonempty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("purpose must not be empty")
        return s


class WithdrawalCreateResponse(BaseModel):
    order: OrderItem
    sign_url: str = Field(..., description="Публичная ссылка на подпись")


class OrderSignContextResponse(BaseModel):
    order_id: int
    status: Optional[str] = None
    wallet_role: Optional[str] = None
    tron_address: Optional[str] = None
    token: Optional[Dict[str, Any]] = None
    amount_raw: Optional[int] = None
    destination_address: Optional[str] = None
    purpose: Optional[str] = Field(
        default=None,
        description="Назначение платежа",
    )
    threshold_n: Optional[int] = None
    threshold_m: Optional[int] = None
    actors_snapshot: List[str] = Field(default_factory=list)
    active_permission_id: Optional[int] = Field(
        default=None,
        description="ID active permission на цепи (TRON multisig) для multiSign / permission_id в tx",
    )
    long_expiration_ms: bool = False
    offchain_expiration_ms: Optional[int] = Field(
        default=None,
        description="Срок действия off-chain tx (raw_data.expiration), мс с epoch",
    )
    offchain_timestamp_ms: Optional[int] = Field(
        default=None,
        description="Время сборки tx (raw_data.timestamp), мс с epoch",
    )
    offchain_signed_addresses: List[str] = Field(
        default_factory=list,
        description="Адреса подписантов по порядку записи off-chain подписей",
    )
    signatures: List[Dict[str, Any]] = Field(default_factory=list)
    broadcast_tx_id: Optional[str] = None
    last_error: Optional[str] = Field(
        default=None,
        description="Текст ошибки при status=failed",
    )


class OrderSignSubmitRequest(BaseModel):
    signer_address: str = Field(..., min_length=26, max_length=64)
    signed_transaction: Dict[str, Any] = Field(
        ...,
        description=(
            "Вариант A: объект транзакции Tron (после trx.sign или trx.multiSign). "
            "Для multisig накапливаются подписи в signature[]; broadcast — только при достижении порога."
        ),
    )
