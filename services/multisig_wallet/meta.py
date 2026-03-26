"""Валидация и слияние multisig_setup_meta."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.multisig_wallet.constants import MULTISIG_DEFAULT_MIN_TRX_SUN
from services.tron.utils import is_valid_tron_address


def default_meta_dict() -> Dict[str, Any]:
    return {
        "actors": [],
        "threshold_n": None,
        "threshold_m": None,
        "min_trx_sun": MULTISIG_DEFAULT_MIN_TRX_SUN,
        "last_trx_balance_sun": None,
        "last_chain_check_at": None,
        "last_error": None,
        "permission_tx_id": None,
        "broadcast_at": None,
        "retry_desired": False,
    }


def merge_meta(
    existing: Optional[Dict[str, Any]], patch: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    base = default_meta_dict()
    if existing:
        base.update(existing)
    if patch:
        base.update(patch)
    return base


def validate_actors_threshold(
    actors: List[str],
    threshold_n: int,
    threshold_m: int,
    *,
    main_tron_address: str,
) -> None:
    """N-of-M: уникальные base58 адреса; main-адрес кошелька должен быть среди actors."""

    if threshold_m < 1 or threshold_n < 1 or threshold_n > threshold_m:
        raise ValueError("Invalid threshold: need 1 <= n <= m")
    cleaned: List[str] = []
    seen = set()
    for a in actors:
        s = (a or "").strip()
        if not s:
            raise ValueError("Empty actor address")
        if not is_valid_tron_address(s):
            raise ValueError(f"Invalid TRON address: {s}")
        if s in seen:
            raise ValueError(f"Duplicate actor: {s}")
        seen.add(s)
        cleaned.append(s)
    if len(cleaned) != threshold_m:
        raise ValueError(f"Need exactly threshold_m={threshold_m} actors, got {len(cleaned)}")
    main = (main_tron_address or "").strip()
    if main not in seen:
        raise ValueError("Multisig account address (from mnemonic) must be included in actors")


def meta_for_api(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Подмножество meta для ответа API / UI (без секретов)."""
    if not meta:
        return {}
    keys = (
        "actors",
        "threshold_n",
        "threshold_m",
        "min_trx_sun",
        "last_trx_balance_sun",
        "last_chain_check_at",
        "last_error",
        "permission_tx_id",
        "broadcast_at",
        "retry_desired",
        "permission_name",
    )
    return {k: meta[k] for k in keys if k in meta}
