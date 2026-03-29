"""Извлечение multisig active permission из ответа TRON getaccount + сравнение с meta/PATCH."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tronpy.keys import is_hex_address, to_base58check_address

from services.tron.utils import is_valid_tron_address


def normalize_tron_permission_address(raw: Any) -> Optional[str]:
    """Адрес ключа из поля permission.key: base58 или hex (tronpy)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if is_valid_tron_address(s):
        return s
    if is_hex_address(s):
        try:
            return to_base58check_address(s)
        except Exception:
            return None
    return None


def _active_permission_entry_is_custom(perm: Dict[str, Any]) -> bool:
    """Согласовано с is_custom_multisig_active_permission по одному элементу."""
    threshold = int(perm.get("threshold", 1) or 1)
    keys = perm.get("keys") or []
    if not isinstance(keys, list):
        keys = []
    permission_name = str(perm.get("permission_name", "") or "").strip()
    return (
        threshold > 1
        or len(keys) > 1
        or (permission_name not in ("active", "") and permission_name)
    )


def extract_chain_multisig_config(account: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Снимок custom active multisig с цепи для сравнения с multisig_setup_meta.

    Возвращает actors (sorted, unique), threshold_n, threshold_m, permission_name
    или None, если кастомной multisig active permission нет.
    """
    perms = account.get("active_permission")
    if not isinstance(perms, list):
        return None
    chosen: Optional[Dict[str, Any]] = None
    for perm in perms:
        if not isinstance(perm, dict):
            continue
        if not _active_permission_entry_is_custom(perm):
            continue
        chosen = perm
        break
    if chosen is None:
        return None
    keys = chosen.get("keys") or []
    if not isinstance(keys, list):
        keys = []
    actors: List[str] = []
    for k in keys:
        if not isinstance(k, dict):
            continue
        addr = normalize_tron_permission_address(k.get("address"))
        if addr:
            actors.append(addr)
    actors_u = sorted(set(actors))
    threshold_n = int(chosen.get("threshold", 1) or 1)
    threshold_m = len(actors_u)
    permission_name = str(chosen.get("permission_name", "") or "").strip()
    if threshold_m < 1 or threshold_n < 1:
        return None
    return {
        "actors": actors_u,
        "threshold_n": threshold_n,
        "threshold_m": threshold_m,
        "permission_name": permission_name,
    }


def meta_multisig_snapshot(meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Канонический снимок из БД meta (actors / thresholds) или None."""
    actors = meta.get("actors")
    if not isinstance(actors, list) or not actors:
        return None
    tn = meta.get("threshold_n")
    tm = meta.get("threshold_m")
    if tn is None or tm is None:
        return None
    cleaned: List[str] = []
    for a in actors:
        s = (a or "").strip()
        if not s or not is_valid_tron_address(s):
            return None
        cleaned.append(s)
    cleaned_u = sorted(set(cleaned))
    if len(cleaned_u) != int(tm):
        return None
    return {
        "actors": cleaned_u,
        "threshold_n": int(tn),
        "threshold_m": int(tm),
    }


def chain_snapshots_equal(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> bool:
    if not a or not b:
        return False
    return (
        a["actors"] == b["actors"]
        and int(a["threshold_n"]) == int(b["threshold_n"])
        and int(a["threshold_m"]) == int(b["threshold_m"])
    )


def chain_config_matches_submission(
    chain: Optional[Dict[str, Any]],
    actors: List[str],
    threshold_n: int,
    threshold_m: int,
    *,
    permission_name: Optional[str] = None,
) -> bool:
    """Совпадает ли PATCH с фактической конфигурацией на цепи."""
    if chain is None:
        return False
    sub_actors = sorted({(x or "").strip() for x in actors if (x or "").strip()})
    if sub_actors != chain["actors"]:
        return False
    if int(threshold_n) != int(chain["threshold_n"]):
        return False
    if int(threshold_m) != int(chain["threshold_m"]):
        return False
    pn = (permission_name or "").strip()
    cpn = (chain.get("permission_name") or "").strip()
    if pn and cpn and pn != cpn:
        return False
    return True
