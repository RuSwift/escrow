"""Схема JSONB commissioners для PaymentRequest (чтение API)."""

from __future__ import annotations

from typing import Dict, Literal, Optional, Union

from pydantic import BaseModel, Field, RootModel, model_validator


class CommissionerAbsolute(BaseModel):
    kind: Literal["absolute"] = "absolute"
    amount: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=32)


class CommissionerPercent(BaseModel):
    kind: Literal["percent"] = "percent"
    value: str = Field(..., min_length=1, max_length=32)


CommissionerCommission = Union[CommissionerAbsolute, CommissionerPercent]


class CommissionerSlot(BaseModel):
    did: str = Field(..., min_length=1, max_length=512)
    commission: CommissionerCommission
    parent_id: Optional[str] = Field(
        default=None,
        description="Ключ другого слота в этом же объекте или null",
    )


class CommissionersPayload(RootModel[Dict[str, CommissionerSlot]]):
    """Корень commissioners: ключ — id слота (короткий код), значение — слот."""

    @model_validator(mode="after")
    def _validate_graph(self) -> CommissionersPayload:
        data = self.root
        for slot_key, slot in data.items():
            pid = slot.parent_id
            if pid is None:
                continue
            if pid not in data:
                raise ValueError(f"parent_id {pid!r} missing for slot {slot_key!r}")
            if pid == slot_key:
                raise ValueError(f"parent_id cannot equal slot key {slot_key!r}")

        for start in data:
            seen: set[str] = set()
            cur: Optional[str] = start
            while cur is not None:
                if cur in seen:
                    raise ValueError("commissioners graph has a cycle")
                seen.add(cur)
                cur = data[cur].parent_id
        return self
