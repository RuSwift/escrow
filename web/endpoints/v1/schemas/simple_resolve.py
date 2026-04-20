"""Ответ GET /v1/arbiter/{arbiter_space_did}/resolve — контекст страницы Simple по публичному uid."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from db.models import Deal

from web.endpoints.v1.schemas.payment_requests import PaymentRequestOut


SimpleResolveKind = Literal["payment_request_only", "deal_only"]


class SimpleDealOut(BaseModel):
    uid: str
    status: str
    label: str
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(
        default=None,
        description="Сумма сделки (decimal из модели)",
    )
    escrow_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, row: Deal) -> SimpleDealOut:
        return cls(
            uid=str(row.uid),
            status=str(row.status or ""),
            label=str(row.label or ""),
            description=row.description,
            amount=row.amount,
            escrow_id=int(row.escrow_id) if row.escrow_id is not None else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SimpleResolveResponse(BaseModel):
    kind: SimpleResolveKind
    viewer_did: Optional[str] = Field(
        default=None,
        description="DID текущего пользователя (сеанс); для сравнения с owner_did в UI",
    )
    payment_request: Optional[PaymentRequestOut] = None
    deal: Optional[SimpleDealOut] = None

    @field_validator("viewer_did", mode="before")
    @classmethod
    def _strip_viewer_did(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @model_validator(mode="after")
    def _consistent_kind(self) -> SimpleResolveResponse:
        if self.kind == "payment_request_only":
            if self.payment_request is None:
                raise ValueError("payment_request required for payment_request_only")
            if self.deal is not None:
                raise ValueError("deal must be null for payment_request_only")
        else:
            if self.deal is None:
                raise ValueError("deal required for deal_only")
            if self.payment_request is not None:
                raise ValueError("payment_request must be null for deal_only")
        return self
