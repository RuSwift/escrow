"""Схема JSONB commissioners для PaymentRequest (чтение и запись API)."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field, RootModel, model_validator


class CommissionerAbsolute(BaseModel):
    kind: Literal["absolute"] = "absolute"
    amount: str = Field(..., min_length=1, max_length=64)
    code: str = Field(..., min_length=1, max_length=32)


class CommissionerPercent(BaseModel):
    kind: Literal["percent"] = "percent"
    value: str = Field(..., min_length=1, max_length=32)


CommissionerCommission = Union[CommissionerAbsolute, CommissionerPercent]

CommissionerRole = Literal["intermediary", "counterparty", "system", "participant"]


class CommissionerSlot(BaseModel):
    """Слот комиссионера; parent_id — ref-строка (public_ref заявки или alias_public_ref родителя)."""

    did: str = Field(..., min_length=1, max_length=512)
    commission: Optional[CommissionerCommission] = Field(
        default=None,
        description="Комиссия слота; обязательна для system/intermediary/counterparty, отсутствует для participant",
    )
    role: Optional[CommissionerRole] = Field(
        default=None,
        description="intermediary по умолчанию при отсутствии ключа (кроме явного system)",
    )
    parent_id: Optional[str] = Field(
        default=None,
        description="public_ref корня заявки или alias_public_ref родительского слота",
    )
    alias_public_ref: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=10,
        description="Публичный алиас узла для resolve и заморозки условий",
    )
    payment_amount: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Снимок суммы по фиат/расчётной ноге для узла",
    )
    borrow_amount: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Снимок объёма borrow (стейбл) для узла",
    )
    payout_address: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Адрес выплаты (напр. system commission wallet)",
    )

    @model_validator(mode="after")
    def _role_system_did(self) -> CommissionerSlot:
        r = self.role
        if r == "system" and (self.did or "").strip() != "system":
            raise ValueError("role=system requires did='system'")
        if r in ("system", "intermediary") and self.commission is None:
            raise ValueError("commission required for role")
        return self


class CommissionersPayload(RootModel[Dict[str, CommissionerSlot]]):
    """Корень commissioners: ключ — id слота (system, i_<id> для посредников, counterparty, legacy resell)."""

    @model_validator(mode="after")
    def _validate_slot_keys(self) -> CommissionersPayload:
        data = self.root
        for slot_key, slot in data.items():
            if slot.parent_id is not None and slot.parent_id == slot.alias_public_ref:
                raise ValueError(
                    f"parent_id cannot equal own alias_public_ref for slot {slot_key!r}"
                )
        return self


def validate_commissioners_parent_refs(
    data: Dict[str, Any],
    *,
    root_public_ref: str,
) -> None:
    """
    Проверка parent_id для сохранения: null, root_public_ref или alias_public_ref другого слота
    (или legacy: ключ другого слота). Обнаружение циклов при обходе к корню.
    """
    root = (root_public_ref or "").strip().lower()
    if not root:
        raise ValueError("root_public_ref required")

    slots: Dict[str, Dict[str, Any]] = {
        k: v for k, v in data.items() if isinstance(v, dict)
    }

    alias_to_slot: Dict[str, str] = {}
    for sk, slot in slots.items():
        ar = (slot.get("alias_public_ref") or "").strip().lower()
        if ar:
            alias_to_slot[ar] = sk

    def resolve_parent_slot_key(pid_raw: Optional[Any]) -> Optional[str]:
        """Возвращает ключ слота-родителя или None если родитель — корень заявки."""
        if pid_raw is None:
            return None
        p = str(pid_raw).strip()
        if not p:
            return None
        pl = p.lower()
        if pl == root:
            return None
        if p in slots:
            return p
        if pl in alias_to_slot:
            return alias_to_slot[pl]
        raise ValueError(f"invalid parent_id ref {p!r}")

    for slot_key, slot in slots.items():
        pid = slot.get("parent_id")
        if pid is None or str(pid).strip() == "":
            continue
        try:
            pk = resolve_parent_slot_key(pid)
        except ValueError as exc:
            raise ValueError(
                f"parent_id for slot {slot_key!r}: {exc.args[0]}"
            ) from exc
        if pk == slot_key:
            raise ValueError(f"parent_id cannot point to self for slot {slot_key!r}")

    for start_key in slots:
        seen: set[str] = set()
        cur: Optional[str] = start_key
        for _ in range(len(slots) + 4):
            if cur is None:
                break
            if cur in seen:
                raise ValueError("commissioners graph has a cycle")
            seen.add(cur)
            pid = slots[cur].get("parent_id")
            cur = resolve_parent_slot_key(pid)


def coerce_commissioners_payload(data: Dict[str, Any]) -> Dict[str, CommissionerSlot]:
    """Мягкое приведение для API: без проверки parent refs (чтение из БД)."""
    out: Dict[str, CommissionerSlot] = {}
    if not isinstance(data, dict):
        return out
    for key, raw in data.items():
        if not isinstance(raw, dict):
            continue
        try:
            out[key] = CommissionerSlot.model_validate(raw)
        except Exception:
            continue
    return out
