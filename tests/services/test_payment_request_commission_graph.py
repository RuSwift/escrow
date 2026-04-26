"""Юнит-тесты параллельной базы B из payment_request_commission_graph."""

from decimal import Decimal

from services.payment_request_commission_graph import (
    borrow_base_b,
    build_slot_snapshots,
    collect_slot_percents_in_order,
    get_ordered_commissioner_keys,
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
    """Все intermediaries — прямые дети корня; порядок: system, затем посредники по ключу."""
    root = "RootRef00"
    comm = {
        "system": {
            "did": "system",
            "role": "system",
            "commission": {"kind": "percent", "value": "0.2"},
            "alias_public_ref": "SysAlias1",
            "parent_id": root,
        },
        "i_bbbbbbbbbbbb": {
            "did": "did:tron:b",
            "role": "intermediary",
            "commission": {"kind": "percent", "value": "1"},
            "parent_id": root,
        },
        "i_aaaaaaaaaaaa": {
            "did": "did:tron:a",
            "role": "intermediary",
            "commission": {"kind": "percent", "value": "0.5"},
            "parent_id": root,
        },
    }
    pcts = collect_slot_percents_in_order(comm, root_public_ref=root)
    assert pcts == [
        Decimal("0.2"),
        Decimal("0.5"),
        Decimal("1"),
    ]


def test_get_ordered_commissioner_keys_follows_parent_chain():
    """parent_id-цепочка: ребёнок alias-родителя должен идти после него, а не лексикографически."""
    root = "RootRef00"
    comm = {
        "system": {
            "did": "system",
            "role": "system",
            "alias_public_ref": "SysAlias1",
            "commission": {"kind": "percent", "value": "0.2"},
            "parent_id": root,
        },
        "i_aaaaaaaaaaaa": {
            "did": "did:tron:a",
            "role": "intermediary",
            "alias_public_ref": "AliasAaaa",
            "commission": {"kind": "percent", "value": "0.5"},
            "parent_id": "AliasBbbb",
        },
        "i_bbbbbbbbbbbb": {
            "did": "did:tron:b",
            "role": "intermediary",
            "alias_public_ref": "AliasBbbb",
            "commission": {"kind": "percent", "value": "1"},
            "parent_id": root,
        },
    }
    order = get_ordered_commissioner_keys(comm, root_public_ref=root)
    assert order == ["system", "i_bbbbbbbbbbbb", "i_aaaaaaaaaaaa"]


def test_collect_slot_percents_respects_parent_chain_order():
    """Проценты выдаются в порядке цепочки родитель→ребёнок, а не алфавитно."""
    root = "RootRef00"
    comm = {
        "system": {
            "did": "system",
            "role": "system",
            "alias_public_ref": "SysAlias1",
            "commission": {"kind": "percent", "value": "0.2"},
            "arbiter_commission": {"kind": "percent", "value": "0.1"},
            "parent_id": root,
        },
        "i_aaaaaaaaaaaa": {
            "did": "did:tron:a",
            "role": "intermediary",
            "alias_public_ref": "AliasAaaa",
            "commission": {"kind": "percent", "value": "0.7"},
            "parent_id": "AliasBbbb",
        },
        "i_bbbbbbbbbbbb": {
            "did": "did:tron:b",
            "role": "intermediary",
            "alias_public_ref": "AliasBbbb",
            "commission": {"kind": "percent", "value": "1"},
            "parent_id": root,
        },
    }
    pcts = collect_slot_percents_in_order(comm, root_public_ref=root)
    assert pcts == [
        Decimal("0.2"),
        Decimal("0.1"),
        Decimal("1"),
        Decimal("0.7"),
    ]


def test_get_ordered_commissioner_keys_legacy_parent_id_as_slot_key():
    """Legacy-формат: parent_id хранит slot_key другого слота (без alias_public_ref)."""
    root = "RootRef00"
    comm = {
        "system": {
            "did": "system",
            "role": "system",
            "commission": {"kind": "percent", "value": "0.2"},
            "parent_id": root,
        },
        "resell": {
            "did": "did:tron:c",
            "commission": {"kind": "percent", "value": "0.5"},
            "parent_id": "system",
        },
    }
    order = get_ordered_commissioner_keys(comm, root_public_ref=root)
    assert order == ["system", "resell"]


def test_get_ordered_commissioner_keys_handles_cycle_gracefully():
    """Цикл не должен ронять обход; зацикленные слоты добавляются после валидных."""
    root = "RootRef00"
    comm = {
        "system": {
            "did": "system",
            "role": "system",
            "commission": {"kind": "percent", "value": "0.2"},
            "parent_id": root,
        },
        "i_aa": {
            "did": "did:tron:a",
            "role": "intermediary",
            "alias_public_ref": "AliasAaaa",
            "commission": {"kind": "percent", "value": "1"},
            "parent_id": "AliasBbbb",
        },
        "i_bb": {
            "did": "did:tron:b",
            "role": "intermediary",
            "alias_public_ref": "AliasBbbb",
            "commission": {"kind": "percent", "value": "1"},
            "parent_id": "AliasAaaa",
        },
    }
    order = get_ordered_commissioner_keys(comm, root_public_ref=root)
    assert order[0] == "system"
    assert set(order) == {"system", "i_aa", "i_bb"}
    assert len(order) == 3


def test_get_ordered_commissioner_keys_unknown_parent_falls_back_to_root():
    """parent_id с неизвестным ref-ом трактуется как корневой, чтобы слот не терялся."""
    root = "RootRef00"
    comm = {
        "system": {
            "did": "system",
            "role": "system",
            "commission": {"kind": "percent", "value": "0.2"},
            "parent_id": root,
        },
        "i_orphan": {
            "did": "did:tron:o",
            "role": "intermediary",
            "commission": {"kind": "percent", "value": "0.3"},
            "parent_id": "NoSuchRf",
        },
    }
    order = get_ordered_commissioner_keys(comm, root_public_ref=root)
    assert order == ["system", "i_orphan"]


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
