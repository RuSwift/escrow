"""Схемы API ордеров дашборда."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Идентификатор записи orders")
    category: str
    dedupe_key: str
    space_wallet_id: Optional[int] = Field(
        default=None,
        description="Ramp-кошелёк спейса (wallets.id)",
    )
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class OrderListResponse(BaseModel):
    items: List[OrderItem] = Field(default_factory=list)
    total: int = Field(0, description="Число записей по фильтрам (для пагинации)")
