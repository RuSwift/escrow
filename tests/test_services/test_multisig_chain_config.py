"""Утилиты сравнения multisig-конфигурации с цепью."""

from __future__ import annotations

from services.multisig_wallet.chain_config import (
    chain_config_matches_submission,
    chain_snapshots_equal,
    extract_chain_multisig_config,
    meta_multisig_snapshot,
    normalize_tron_permission_address,
)

_A = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"
_B = "TYDkyTwMF7ti5R8VstRruqz4N9mGne2CdF"


def test_normalize_tron_permission_address_base58():
    assert normalize_tron_permission_address(_A) == _A


def test_extract_chain_multisig_custom():
    acc = {
        "active_permission": [
            {
                "type": 2,
                "permission_name": "ms_test",
                "threshold": 2,
                "keys": [
                    {"address": _A, "weight": 1},
                    {"address": _B, "weight": 1},
                ],
            }
        ]
    }
    cfg = extract_chain_multisig_config(acc)
    assert cfg is not None
    assert cfg["threshold_n"] == 2
    assert cfg["threshold_m"] == 2
    assert cfg["permission_name"] == "ms_test"
    assert cfg["actors"] == sorted([_A, _B])


def test_extract_skips_default_active():
    acc = {
        "active_permission": [
            {
                "type": 0,
                "permission_name": "active",
                "threshold": 1,
                "keys": [{"address": _A, "weight": 1}],
            }
        ]
    }
    assert extract_chain_multisig_config(acc) is None


def test_chain_config_matches_submission_permission_name():
    chain = {
        "actors": sorted([_A, _B]),
        "threshold_n": 2,
        "threshold_m": 2,
        "permission_name": "m1",
    }
    assert chain_config_matches_submission(
        chain, [_B, _A], 2, 2, permission_name="m1"
    )
    assert not chain_config_matches_submission(
        chain, [_B, _A], 2, 2, permission_name="m2"
    )


def test_meta_snapshot_and_chain_equal():
    meta = {
        "actors": [_B, _A],
        "threshold_n": 2,
        "threshold_m": 2,
    }
    db = meta_multisig_snapshot(meta)
    ch = {
        "actors": sorted([_A, _B]),
        "threshold_n": 2,
        "threshold_m": 2,
        "permission_name": "x",
    }
    assert db is not None
    assert chain_snapshots_equal(
        db, {k: ch[k] for k in ("actors", "threshold_n", "threshold_m")}
    )
