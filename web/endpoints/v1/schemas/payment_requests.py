"""Схемы API /v1/arbiter/{arbiter_space_did}/payment-requests (Simple UI)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from db.models import PaymentRequest
from services.payment_request import PaymentRequestService, SimplePaymentLifetime
from web.endpoints.v1.schemas.payment_request_commissioners import (
    CommissionerSlot,
    CommissionersPayload,
    coerce_commissioners_payload,
)


class PaymentRequestLegIn(BaseModel):
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


class PaymentRequestCreateBody(BaseModel):
    direction: Literal["fiat_to_stable", "stable_to_fiat"] = Field(...)
    primary_leg: PaymentRequestLegIn
    counter_leg: PaymentRequestLegIn
    heading: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Заголовок заявки; пустой — только «Заявка #{pk}» на фронте",
    )
    lifetime: SimplePaymentLifetime = Field(
        default="72h",
        description="Срок действия: 24ч / 48ч / 72ч или без ограничения",
    )

    @field_validator("heading", mode="before")
    @classmethod
    def _strip_heading(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class PaymentRequestOut(BaseModel):
    pk: int
    uid: str
    public_ref: str = Field(
        ...,
        description="Короткий код для ссылок: для комиссионера — его alias_public_ref",
    )
    original_public_ref: Optional[str] = Field(
        default=None,
        description="public_ref строки заявки (владелец); для комиссионера при подмене ref",
    )
    pair_label: str = Field(..., description="Пара активов, напр. CNY — USDT")
    amount: Optional[Decimal] = None
    direction: str
    owner_did: str = Field(..., description="DID автора заявки (владелец; для UI «перепродать»)")
    arbiter_did: str = Field(..., description="DID арбитра (контекст Simple из URL)")
    heading: Optional[str] = None
    space_id: int
    space_nickname: Optional[str] = Field(
        default=None,
        description="Nickname WalletUser для отображения (primary space)",
    )
    primary_leg: Dict[str, Any]
    counter_leg: Dict[str, Any]
    commissioners: Dict[str, CommissionerSlot] = Field(
        default_factory=dict,
        description="Слоты комиссионеров; запись через API позже",
    )
    primary_ramp_wallet_id: Optional[int] = None
    deal_id: Optional[int] = None
    owner_confirm_pending: bool = Field(
        default=False,
        description="Ждём подтверждения владельца после accept контрагента",
    )
    counterparty_accept_at: Optional[datetime] = Field(
        default=None,
        description="Время accept контрагента",
    )
    counterparty_accept_did: Optional[str] = Field(
        default=None,
        description="DID контрагента, принявшего заявку (до Deal)",
    )
    owner_confirmed_at: Optional[datetime] = Field(
        default=None,
        description="Время подтверждения владельцем / создания Deal",
    )
    handshake_locked_by_other: bool = Field(
        default=False,
        description="Другой контрагент уже принял (first lock); текущему недоступно",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Окончание срока; null — без ограничения",
    )
    deactivated_at: Optional[datetime] = Field(
        default=None,
        description="Деактивация владельцем; null — активна",
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(
        cls,
        row: PaymentRequest,
        *,
        space_nickname: Optional[str] = None,
        viewer_did: Optional[str] = None,
        segment_public_ref: Optional[str] = None,
    ) -> PaymentRequestOut:
        pl = dict(row.primary_leg) if isinstance(row.primary_leg, dict) else {}
        cl = dict(row.counter_leg) if isinstance(row.counter_leg, dict) else {}
        direction_out = str(row.direction or "").strip()
        if direction_out not in ("fiat_to_stable", "stable_to_fiat"):
            direction_out = "fiat_to_stable"
        pair_label = PaymentRequestService.build_pair_label(direction_out, pl, cl)
        raw_head = getattr(row, "heading", None)
        head_out: Optional[str] = None
        if raw_head is not None:
            sh = str(raw_head).strip()
            head_out = sh if sh else None
        amt: Optional[Decimal] = None
        raw_amt = pl.get("amount")
        if raw_amt is not None:
            s = str(raw_amt).strip()
            if s:
                try:
                    amt = Decimal(s)
                except InvalidOperation:
                    amt = None
        raw_comm = getattr(row, "commissioners", None)
        if not isinstance(raw_comm, dict):
            raw_comm = {}
        try:
            commissioners_out = CommissionersPayload.model_validate(raw_comm).root
        except ValidationError:
            commissioners_out = coerce_commissioners_payload(raw_comm)

        column_ref = str(getattr(row, "public_ref", "") or "")
        public_ref_out = column_ref
        original_out: Optional[str] = None
        vw = (viewer_did or "").strip()
        owner_did = str(getattr(row, "owner_did", "") or "").strip()
        if vw and vw != owner_did:
            for _sk, slot in commissioners_out.items():
                if (slot.did or "").strip() != vw:
                    continue
                if str(slot.role or "").strip().lower() == "system":
                    continue
                alias = (slot.alias_public_ref or "").strip()
                if alias:
                    public_ref_out = alias
                    original_out = column_ref
                break
            # Если viewer не имеет слота и пришёл по alias в URL (commissioner_alias),
            # сохраняем сегмент как public_ref для стабильного URL (иначе UI перепишет на owner public_ref).
            seg = (segment_public_ref or "").strip()
            if seg and public_ref_out == column_ref:
                public_ref_out = seg
                original_out = column_ref

        acc_did = str(getattr(row, "counterparty_accept_did", "") or "").strip()
        pending_own = bool(getattr(row, "owner_confirm_pending", False))
        locked_other = False
        if vw and vw != owner_did and pending_own and acc_did and vw != acc_did:
            locked_other = True

        return cls(
            pk=int(row.pk),
            uid=str(row.uid),
            public_ref=public_ref_out,
            original_public_ref=original_out,
            pair_label=pair_label,
            amount=amt,
            direction=direction_out,
            owner_did=owner_did,
            arbiter_did=str(getattr(row, "arbiter_did", "") or "").strip(),
            heading=head_out,
            space_id=int(row.space_id),
            space_nickname=space_nickname,
            primary_leg=pl,
            counter_leg=cl,
            commissioners=commissioners_out,
            primary_ramp_wallet_id=(
                int(row.primary_ramp_wallet_id)
                if row.primary_ramp_wallet_id is not None
                else None
            ),
            deal_id=int(row.deal_id) if row.deal_id is not None else None,
            owner_confirm_pending=pending_own,
            counterparty_accept_at=getattr(row, "counterparty_accept_at", None),
            counterparty_accept_did=acc_did if acc_did else None,
            owner_confirmed_at=getattr(row, "owner_confirmed_at", None),
            handshake_locked_by_other=locked_other,
            expires_at=getattr(row, "expires_at", None),
            deactivated_at=getattr(row, "deactivated_at", None),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class PaymentRequestDeactivateBody(BaseModel):
    confirm_pk: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Должен совпадать с номером заявки (pk)",
    )

    @field_validator("confirm_pk", mode="before")
    @classmethod
    def _strip_confirm_pk(cls, v: object) -> str:
        return str(v).strip() if v is not None else ""


class PaymentRequestListResponse(BaseModel):
    items: List[PaymentRequestOut]
    total: int


class PaymentRequestCreateResponse(BaseModel):
    payment_request: PaymentRequestOut


class PaymentRequestDeactivateResponse(BaseModel):
    payment_request: PaymentRequestOut


class PaymentRequestResellBody(BaseModel):
    intermediary_percent: Optional[str] = Field(
        default="0.5",
        max_length=32,
        description="Процент комиссии посредника-комиссионера (по умолчанию 0.5)",
    )


class PaymentRequestResellResponse(BaseModel):
    payment_request: PaymentRequestOut


class PaymentRequestViewerRoleBody(BaseModel):
    role: Literal["counterparty", "intermediary"] = Field(
        ...,
        description="Роль зрителя на стадии согласования условий: контрагент или посредник",
    )
    parent_ref: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Опциональный parent ref (alias) из URL, если роль=intermediary и нужно встроиться после конкретного посредника",
    )


class PaymentRequestViewerRoleResponse(BaseModel):
    payment_request: PaymentRequestOut


class PaymentRequestAcceptBody(BaseModel):
    counter_stable_amount: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Финальная сумма stable для counter leg (если сумма была «на согласовании»)",
    )


class PaymentRequestHandshakeResponse(BaseModel):
    payment_request: PaymentRequestOut
    deal_uid: Optional[str] = Field(
        default=None,
        description="Публичный uid созданной сделки (только после успешного confirm)",
    )


class PaymentRequestExtendBody(BaseModel):
    lifetime: SimplePaymentLifetime = Field(
        default="72h",
        description="На сколько продлить: 24h / 48h / 72h",
    )
