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
    # Контрагент не является узлом комиссии: не должен участвовать в расчёте fee_i и escrow totals.
    # Роль counterparty используется для UX/handshake, но проценты цепочки строятся только по system + intermediary.
    return False


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


def _slot_role_priority(slot_key: str, slot: Dict[str, Any]) -> int:
    """Стабильный приоритет роли внутри одного уровня графа commissioners."""
    if is_system_commission_slot(slot_key, slot):
        return 0
    if is_intermediary_commission_slot(slot_key, slot):
        return 1
    if is_counterparty_commission_slot(slot_key, slot):
        return 2
    return 3


def get_ordered_commissioner_keys(
    commissioners: Dict[str, Any],
    root_public_ref: str,
) -> List[str]:
    """
    Топологический порядок ключей слотов commissioners по графу parent_id (от корня заявки вниз).

    Семантика parent_id (совместимая со схемой `validate_commissioners_parent_refs`):
      - None/"" или равенство `root_public_ref` (case-insensitive) — слот привязан к корню заявки;
      - совпадение с `alias_public_ref` другого слота — слот является ребёнком этого слота;
      - legacy: совпадение с ключом другого слота — также трактуется как ребёнок.

    Внутри одного уровня (общий родитель) порядок стабилен:
        system → intermediary → counterparty/прочее, далее лексикографически по ключу.

    Циклы и недопустимые ссылки не вызывают исключений: такие слоты обходятся в детерминированном
    порядке после валидных, чтобы сборка снимков не падала на поврежденных данных.
    """
    if not isinstance(commissioners, dict):
        return []
    slots: Dict[str, Dict[str, Any]] = {
        k: v for k, v in commissioners.items() if isinstance(v, dict)
    }
    if not slots:
        return []

    root_norm = (root_public_ref or "").strip().lower()
    alias_to_key: Dict[str, str] = {}
    for sk, slot in slots.items():
        ar = (slot.get("alias_public_ref") or "").strip().lower()
        if ar and ar not in alias_to_key:
            alias_to_key[ar] = sk

    def parent_slot_key(slot_key: str) -> Optional[str]:
        slot = slots[slot_key]
        pid_raw = slot.get("parent_id")
        if pid_raw is None:
            return None
        p = str(pid_raw).strip()
        if not p:
            return None
        pl = p.lower()
        if root_norm and pl == root_norm:
            return None
        if p in slots:
            return p
        if pl in alias_to_key:
            return alias_to_key[pl]
        return None

    def resolved_parent(slot_key: str) -> Optional[str]:
        seen: set[str] = {slot_key}
        cur: Optional[str] = slot_key
        for _ in range(len(slots) + 4):
            p = parent_slot_key(cur) if cur is not None else None
            if p is None:
                return None
            if p == slot_key or p in seen:
                return None
            return p
        return None

    children: Dict[Optional[str], List[str]] = {}
    for sk in slots:
        children.setdefault(resolved_parent(sk), []).append(sk)
    for lst in children.values():
        lst.sort(key=lambda x: (_slot_role_priority(x, slots[x]), x))

    visited: set[str] = set()
    out: List[str] = []

    def dfs(node: Optional[str]) -> None:
        for child in children.get(node, []):
            if child in visited:
                continue
            visited.add(child)
            out.append(child)
            dfs(child)

    dfs(None)

    if len(out) < len(slots):
        leftovers = sorted(
            (k for k in slots if k not in visited),
            key=lambda x: (_slot_role_priority(x, slots[x]), x),
        )
        out.extend(leftovers)
    return out


def collect_slot_percents_in_order(
    commissioners: Dict[str, Any],
    root_public_ref: str = "",
) -> List[Decimal]:
    """
    Порядок процентов: обход графа commissioners от корня заявки (см. `get_ordered_commissioner_keys`).

    Параллельная сумма fee_i = B * pct_i / 100 для каждого слота.
    Для system-слота учитываются обе части: основная и арбитражная комиссия.
    `root_public_ref` опционален для обратной совместимости вызывающего кода; для слотов,
    привязанных к корню без явного `parent_id`, порядок корректен и при пустом `root_public_ref`.
    """
    if not isinstance(commissioners, dict):
        return []
    out: List[Decimal] = []
    for key in get_ordered_commissioner_keys(commissioners, root_public_ref):
        slot = commissioners[key]
        if not isinstance(slot, dict):
            continue

        comm = slot.get("commission")
        if isinstance(comm, dict) and (comm.get("kind") or "") == "percent":
            p = percent_str_to_decimal(str(comm.get("value") or ""))
            if p is not None:
                out.append(p)

        if is_system_commission_slot(key, slot):
            arb_comm = slot.get("arbiter_commission")
            if isinstance(arb_comm, dict) and (arb_comm.get("kind") or "") == "percent":
                ap = percent_str_to_decimal(str(arb_comm.get("value") or ""))
                if ap is not None:
                    out.append(ap)
    return out


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
            # Суммируем с комиссией арбитра для system слота
            if is_system_commission_slot(key, slot):
                arb_comm = slot.get("arbiter_commission")
                if isinstance(arb_comm, dict) and (arb_comm.get("kind") or "") == "percent":
                    ap = percent_str_to_decimal(str(arb_comm.get("value") or ""))
                    if ap is not None:
                        pct = (pct or Decimal(0)) + ap

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
