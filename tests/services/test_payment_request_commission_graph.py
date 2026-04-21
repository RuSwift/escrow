"""Юнит-тесты параллельной базы B из payment_request_commission_graph."""

from decimal import Decimal

from services.payment_request_commission_graph import (
    borrow_base_b,
    build_slot_snapshots,
    collect_slot_percents_in_order,
    parallel_fees_from_b,
    snapshot_borrow_for_fiat_to_stable_add,
    snapshot_borrow_for_stable_to_fiat_sub,
)


def test_parallel_from_b_totals_reference_table():
    b = Decimal("500")
    fees, total = parallel_fees_from_b(
        b,
        [
            Decimal("0.2"),
            Decimal("0.5"),
            Decimal("1"),
        ],
    )
    assert len(fees) == 3
    assert snapshot_borrow_for_fiat_to_stable_add(b, total) == Decimal("508.5")
    assert snapshot_borrow_for_stable_to_fiat_sub(b, total) == Decimal("491.5")


def test_borrow_base_fiat_to_stable():
    pl = {
        "asset_type": "fiat",
        "code": "CNY",
        "amount": "10000",
        "side": "give",
    }
    cl = {
        "asset_type": "stable",
        "code": "USDT",
        "amount": "500",
        "side": "receive",
    }
    assert borrow_base_b("fiat_to_stable", pl, cl) == Decimal("500")


def test_collect_slot_percents_multiple_intermediaries_ordered():
    comm = {
        "system": {
            "did": "system",
            "role": "system",
            "commission": {"kind": "percent", "value": "0.2"},
        },
        "i_bbbbbbbbbbbb": {
            "did": "did:tron:b",
            "role": "intermediary",
            "commission": {"kind": "percent", "value": "1"},
        },
        "i_aaaaaaaaaaaa": {
            "did": "did:tron:a",
            "role": "intermediary",
            "commission": {"kind": "percent", "value": "0.5"},
        },
    }
    pcts = collect_slot_percents_in_order(comm)
    assert pcts == [
        Decimal("0.2"),
        Decimal("0.5"),
        Decimal("1"),
    ]


def test_build_slot_snapshots_per_slot_percent_slice_only():
    """Снимок слота зависит только от его pct; обновление resell не требует пересчёта system в JSON."""
    pl = {
        "asset_type": "fiat",
        "code": "CNY",
        "amount": "10000",
        "side": "give",
    }
    cl = {
        "asset_type": "stable",
        "code": "USDT",
        "amount": "500",
        "side": "receive",
    }
    comm = {
        "system": {
            "did": "system",
            "role": "system",
            "commission": {"kind": "percent", "value": "0.2"},
        },
        "resell": {
            "did": "did:peer:mid",
            "commission": {"kind": "percent", "value": "0.5"},
            "parent_id": "AbCdEfGh",
        },
    }
    r_only = build_slot_snapshots("fiat_to_stable", pl, cl, comm, ["resell"])
    assert r_only["resell"]["borrow_amount"] == "2.5"
    assert r_only["resell"]["payment_amount"] == "50"

    s_only = build_slot_snapshots("fiat_to_stable", pl, cl, comm, ["system"])
    assert s_only["system"]["borrow_amount"] == "1"
    assert s_only["system"]["payment_amount"] == "20"


def test_borrow_base_stable_to_fiat():
    pl = {
        "asset_type": "stable",
        "code": "USDT",
        "amount": "500",
        "side": "give",
    }
    cl = {
        "asset_type": "fiat",
        "code": "CNY",
        "amount": "10000",
        "side": "receive",
    }
    assert borrow_base_b("stable_to_fiat", pl, cl) == Decimal("500")
