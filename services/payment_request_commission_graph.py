"""
Расчёт borrow-базы B и снимков parallel_from_B для PaymentRequest (клиринг по стейбл-ноге).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from db.models import PaymentRequest

MONEY_Q = Decimal("0.1")


def is_system_commission_slot(slot_key: str, slot: Any) -> bool:
    if not isinstance(slot, dict):
        return False
    role = str(slot.get("role") or "").strip().lower()
    if role == "system" or slot_key == "system":
        return True
    return (slot.get("did") or "").strip() == "system"


def is_counterparty_commission_slot(slot_key: str, slot: Any) -> bool:
    if not isinstance(slot, dict):
        return False
    role = str(slot.get("role") or "").strip().lower()
    return role == "counterparty" or slot_key == "counterparty"


def is_intermediary_commission_slot(slot_key: str, slot: Any) -> bool:
    """Посредник: явная роль, legacy ключ resell, или слот с user did (не system/counterparty)."""
    if not isinstance(slot, dict):
        return False
    if is_system_commission_slot(slot_key, slot) or is_counterparty_commission_slot(slot_key, slot):
        return False
    role = str(slot.get("role") or "").strip().lower()
    if role == "intermediary":
        return True
    if slot_key == "resell":
        return True
    did = (slot.get("did") or "").strip()
    return bool(did and did != "system")


def intermediary_slot_keys_for_did(commissioners: Dict[str, Any], actor_did: str) -> List[str]:
    """Все ключи слотов-посредников с заданным did (в т.ч. legacy resell)."""
    ad = (actor_did or "").strip()
    if not ad:
        return []
    out: List[str] = []
    if not isinstance(commissioners, dict):
        return []
    for sk, slot in commissioners.items():
        if not isinstance(slot, dict):
            continue
        if (slot.get("did") or "").strip() != ad:
            continue
        if is_intermediary_commission_slot(sk, slot):
            out.append(sk)
    return sorted(out)


def _d(s: Any) -> Optional[Decimal]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def borrow_base_b(
    direction: str,
    primary_leg: Dict[str, Any],
    counter_leg: Dict[str, Any],
) -> Optional[Decimal]:
    """
    Номинальная база B (стейбл) из ног заявки.
    fiat_to_stable: стейбл в counter_leg (получение).
    stable_to_fiat: стейбл в primary_leg (отдача).
    """
    d = (direction or "").strip()
    pl = primary_leg if isinstance(primary_leg, dict) else {}
    cl = counter_leg if isinstance(counter_leg, dict) else {}
    if d == "fiat_to_stable":
        if str((cl or {}).get("asset_type") or "").lower() == "stable":
            return _d((cl or {}).get("amount"))
        return None
    if d == "stable_to_fiat":
        if str((pl or {}).get("asset_type") or "").lower() == "stable":
            return _d((pl or {}).get("amount"))
        return None
    return None


def _fee_from_b(b: Decimal, pct: Decimal) -> Decimal:
    return (b * pct / Decimal(100)).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def parallel_fees_from_b(
    b: Decimal, percent_values: List[Decimal]
) -> Tuple[List[Decimal], Decimal]:
    """
    Параллельные комиссии: fee_i = round(B * pct_i / 100); sum_fees = sum(fee_i).
    """
    fees = [_fee_from_b(b, p) for p in percent_values]
    return fees, sum(fees, start=Decimal(0))


def percent_str_to_decimal(s: str) -> Optional[Decimal]:
    t = (s or "").strip()
    if not t:
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def format_amount_str(d: Decimal) -> str:
    t = format(d, "f")
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    return t or "0"


def collect_slot_percents_in_order(commissioners: Dict[str, Any]) -> List[Decimal]:
    """
    Порядок: system → все посредники (ключи по сортировке) → counterparty.
    Параллельная сумма fee_i = B * pct_i / 100 для каждого слота.
    """
    if not isinstance(commissioners, dict):
        return []
    sys_p: List[Decimal] = []
    mid_p: List[Decimal] = []
    cp_p: List[Decimal] = []
    for key in sorted(commissioners.keys()):
        slot = commissioners[key]
        if not isinstance(slot, dict):
            continue
        comm = slot.get("commission")
        if not isinstance(comm, dict):
            continue
        if (comm.get("kind") or "") != "percent":
            continue
        p = percent_str_to_decimal(str(comm.get("value") or ""))
        if p is None:
            continue
        if is_system_commission_slot(key, slot):
            sys_p.append(p)
        elif is_counterparty_commission_slot(key, slot):
            cp_p.append(p)
        elif is_intermediary_commission_slot(key, slot):
            mid_p.append(p)
    return sys_p + mid_p + cp_p


def snapshot_borrow_for_fiat_to_stable_add(
    b: Optional[Decimal], total_fees: Decimal
) -> Optional[Decimal]:
    """Контрагент: B + sum fees (parallel)."""
    if b is None:
        return None
    return (b + total_fees).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def snapshot_borrow_for_stable_to_fiat_sub(
    b: Optional[Decimal], total_fees: Decimal
) -> Optional[Decimal]:
    """Контрагент: B - sum fees (parallel)."""
    if b is None:
        return None
    return (b - total_fees).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def fiat_side_amount(
    direction: str,
    primary_leg: Dict[str, Any],
    counter_leg: Dict[str, Any],
) -> Optional[Decimal]:
    d = (direction or "").strip()
    pl = primary_leg if isinstance(primary_leg, dict) else {}
    cl = counter_leg if isinstance(counter_leg, dict) else {}
    if d == "fiat_to_stable":
        if str((pl or {}).get("asset_type") or "").lower() == "fiat":
            return _d((pl or {}).get("amount"))
    if d == "stable_to_fiat":
        if str((cl or {}).get("asset_type") or "").lower() == "fiat":
            return _d((cl or {}).get("amount"))
    return None


def build_slot_snapshots(
    direction: str,
    primary_leg: Dict[str, Any],
    counter_leg: Dict[str, Any],
    commissioners: Dict[str, Any],
    commissioner_keys: List[str],
) -> Dict[str, Dict[str, str]]:
    """
    Снимки только для перечисленных слотов: доля узла в parallel fee (fee_i = B * pct_i / 100).
    При обновлении одного слота (напр. resell) чужие ключи в JSON не пересчитываются —
    их payment_amount / borrow_amount остаются как были.
    """
    pl = dict(primary_leg) if isinstance(primary_leg, dict) else {}
    cl = dict(counter_leg) if isinstance(counter_leg, dict) else {}
    d = str(direction or "").strip()
    b = borrow_base_b(d, pl, cl)
    fa = fiat_side_amount(d, pl, cl)
    comm = dict(commissioners) if isinstance(commissioners, dict) else {}
    out: Dict[str, Dict[str, str]] = {}
    for key in commissioner_keys:
        slot = comm.get(key)
        if not isinstance(slot, dict):
            out[key] = {"payment_amount": "", "borrow_amount": ""}
            continue
        comm_obj = slot.get("commission")
        if not isinstance(comm_obj, dict):
            out[key] = {"payment_amount": "", "borrow_amount": ""}
            continue
        kind = str(comm_obj.get("kind") or "").strip().lower()
        pay_s = ""
        bor_s = ""
        if kind == "percent":
            pct = percent_str_to_decimal(str(comm_obj.get("value") or ""))
            if pct is not None and b is not None:
                bor_s = format_amount_str(_fee_from_b(b, pct))
            if pct is not None and fa is not None:
                pay_s = format_amount_str(_fee_from_b(fa, pct))
        elif kind == "absolute":
            amt = _d(comm_obj.get("amount"))
            if amt is not None:
                s = format_amount_str(amt)
                pay_s = s
                bor_s = s
        out[key] = {
            "payment_amount": pay_s,
            "borrow_amount": bor_s,
        }
    return out


def build_slot_snapshots_for_pr(
    row: PaymentRequest, commissioner_keys: List[str]
) -> Dict[str, Dict[str, str]]:
    pl = dict(row.primary_leg) if isinstance(row.primary_leg, dict) else {}
    cl = dict(row.counter_leg) if isinstance(row.counter_leg, dict) else {}
    comm = dict(row.commissioners) if isinstance(row.commissioners, dict) else {}
    return build_slot_snapshots(
        str(row.direction or ""),
        pl,
        cl,
        comm,
        commissioner_keys,
    )
