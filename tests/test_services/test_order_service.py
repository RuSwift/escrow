"""OrderService.refresh_ephemeral и список ордеров."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest
from redis.asyncio import Redis

from db.models import Wallet, WalletUser, WalletUserSub, WalletUserSubRole
from services.multisig_wallet.constants import (
    MULTISIG_STATUS_ACTIVE,
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_PENDING_CONFIG,
)
from services.multisig_wallet.meta import default_meta_dict
from repos.order import OrderRepository, withdrawal_dedupe_key
from services.order import (
    ORDER_KIND_MULTISIG_PIPELINE,
    ORDER_KIND_MULTISIG_SPACE_DRIFT,
    WITHDRAWAL_KIND,
    WITHDRAWAL_STATUS_AWAITING_SIGNATURES,
    WITHDRAWAL_STATUS_BROADCAST_SUBMITTED,
    WITHDRAWAL_STATUS_READY_TO_BROADCAST,
    OrderService,
)

_SPACE_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"
_SIGNER_OTHER = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"


@pytest.fixture
def order_service(test_db, test_redis: Redis, test_settings):
    return OrderService(session=test_db, redis=test_redis, settings=test_settings)


@pytest.mark.asyncio
async def test_refresh_creates_pipeline_order(
    order_service: OrderService,
    test_db,
):
    w = Wallet(
        name="ms",
        encrypted_mnemonic="enc",
        role="multisig",
        owner_did="did:web:escrow.ruswift.ru:sp1",
        multisig_setup_status=MULTISIG_STATUS_AWAITING_FUNDING,
        multisig_setup_meta=default_meta_dict(),
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    stats = await order_service.refresh_ephemeral()
    assert stats["upserted"] >= 1
    await test_db.commit()

    from sqlalchemy import select
    from db.models import Order
    from repos.order import ORDER_CATEGORY_EPHEMERAL

    r = await test_db.execute(
        select(Order).where(Order.dedupe_key == f"ephemeral:multisig_pipeline:{w.id}")
    )
    row = r.scalar_one_or_none()
    assert row is not None
    assert row.space_wallet_id == w.id
    assert row.payload and row.payload.get("kind") == ORDER_KIND_MULTISIG_PIPELINE


@pytest.mark.asyncio
async def test_refresh_no_pipeline_when_active(
    order_service: OrderService,
    test_db,
):
    w = Wallet(
        name="ms2",
        encrypted_mnemonic="enc",
        role="multisig",
        owner_did="did:web:escrow.ruswift.ru:sp2",
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta=default_meta_dict(),
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    await order_service.refresh_ephemeral()
    await test_db.commit()

    from sqlalchemy import select
    from db.models import Order

    r2 = await test_db.execute(
        select(Order).where(Order.dedupe_key == f"ephemeral:multisig_pipeline:{w.id}")
    )
    assert r2.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_refresh_space_drift_order(
    order_service: OrderService,
    test_db,
):
    owner = WalletUser(
        nickname="drift_space",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:drift_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w = Wallet(
        name="ms3",
        encrypted_mnemonic="enc",
        role="multisig",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_SIGNER_OTHER],
            "threshold_n": 1,
            "threshold_m": 1,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    await order_service.refresh_ephemeral()
    await test_db.commit()

    from sqlalchemy import select
    from db.models import Order

    r = await test_db.execute(
        select(Order).where(Order.dedupe_key == f"ephemeral:multisig_space_drift:{w.id}")
    )
    row = r.scalar_one_or_none()
    assert row is not None
    assert row.space_wallet_id == w.id
    assert row.payload and row.payload.get("kind") == ORDER_KIND_MULTISIG_SPACE_DRIFT


@pytest.mark.asyncio
async def test_refresh_owners_drift_only_actors_match_space(
    order_service: OrderService,
    test_db,
):
    """meta.owners ≠ space admins, при этом actors совпадают с owner+operator в спейсе."""
    owner = WalletUser(
        nickname="drift_owners_only",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:drift_owners_only",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w = Wallet(
        name="ms_owners",
        encrypted_mnemonic="enc",
        role="multisig",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_SPACE_TRON],
            "owners": [_SIGNER_OTHER],
            "threshold_n": 1,
            "threshold_m": 1,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    await order_service.refresh_ephemeral()
    await test_db.commit()

    from sqlalchemy import select
    from db.models import Order

    r = await test_db.execute(
        select(Order).where(Order.dedupe_key == f"ephemeral:multisig_space_drift:{w.id}")
    )
    row = r.scalar_one_or_none()
    assert row is not None
    pl = row.payload
    assert pl.get("owners_drift") is True
    assert pl.get("actors_drift") is False
    assert _SIGNER_OTHER in (pl.get("owners_only_in_meta") or [])


@pytest.mark.asyncio
async def test_refresh_no_actors_drift_when_meta_actors_subset_of_space(
    order_service: OrderService,
    test_db,
):
    """В спейсе есть лишний operator относительно actors в meta — actors ⊆ space, drift не создаётся."""
    owner = WalletUser(
        nickname="subset_actors",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:subset_actors",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    sub = WalletUserSub(
        wallet_user_id=owner.id,
        wallet_address=_SIGNER_OTHER,
        blockchain="tron",
        roles=[WalletUserSubRole.operator.value],
        is_verified=True,
        is_blocked=False,
    )
    test_db.add(sub)
    await test_db.commit()

    w = Wallet(
        name="ms_subset",
        encrypted_mnemonic="enc",
        role="multisig",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_SPACE_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    await order_service.refresh_ephemeral()
    await test_db.commit()

    from sqlalchemy import select
    from db.models import Order

    r = await test_db.execute(
        select(Order).where(Order.dedupe_key == f"ephemeral:multisig_space_drift:{w.id}")
    )
    assert r.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_refresh_no_space_drift_while_pending_config(
    order_service: OrderService,
    test_db,
):
    """Пока multisig в пайплайне (pending_config), drift со спейсом не создаётся."""
    owner = WalletUser(
        nickname="no_drift_pending",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:no_drift_pending",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w = Wallet(
        name="ms_pending",
        encrypted_mnemonic="enc",
        role="multisig",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_PENDING_CONFIG,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [],
            "threshold_n": None,
            "threshold_m": None,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    await order_service.refresh_ephemeral()
    await test_db.commit()

    from sqlalchemy import select
    from db.models import Order

    r = await test_db.execute(
        select(Order).where(Order.dedupe_key == f"ephemeral:multisig_space_drift:{w.id}")
    )
    assert r.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_clear_offchain_signatures_multisig(
    order_service: OrderService,
    test_db,
    test_redis,
    test_settings,
):
    owner = WalletUser(
        nickname="clr_wd_space",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:clr_wd_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w_ms = Wallet(
        name="ms_clr",
        encrypted_mnemonic="enc",
        role="multisig",
        tron_address="TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5B",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_SIGNER_OTHER, _SPACE_TRON],
            "threshold_n": 2,
            "threshold_m": 2,
        },
    )
    test_db.add(w_ms)
    await test_db.commit()
    await test_db.refresh(w_ms)

    repo = OrderRepository(session=test_db, redis=test_redis, settings=test_settings)
    created = await repo.insert_withdrawal_order(
        dedupe_key=withdrawal_dedupe_key("cleartokentest0001"),
        space_wallet_id=w_ms.id,
        payload={
            "kind": WITHDRAWAL_KIND,
            "status": "awaiting_signatures",
            "wallet_role": "multisig",
            "wallet_id": w_ms.id,
            "tron_address": w_ms.tron_address,
            "token": {"type": "native", "symbol": "TRX", "decimals": 6},
            "amount_raw": 1000,
            "destination_address": _SIGNER_OTHER,
            "threshold_n": 2,
            "threshold_m": 2,
            "actors_snapshot": [_SIGNER_OTHER, _SPACE_TRON],
            "long_expiration_ms": True,
            "broadcast_tx_id": None,
            "offchain_expiration_ms": 9_999_000_000_000,
            "offchain_timestamp_ms": 9_998_000_000_000,
            "offchain_signed_addresses": [_SIGNER_OTHER],
        },
    )
    await repo.upsert_withdrawal_signature(
        int(created.id),
        _SIGNER_OTHER,
        {"signed_transaction": {"txid": "x"}},
    )
    await test_db.commit()

    out = await order_service.clear_offchain_signatures(
        "clr_wd_space", _SPACE_TRON, int(created.id)
    )
    assert out.payload is not None
    assert out.payload.get("status") == "awaiting_signatures"
    assert out.payload.get("broadcast_tx_id") is None
    assert out.payload.get("offchain_expiration_ms") is None
    assert out.payload.get("offchain_timestamp_ms") is None
    assert out.payload.get("offchain_signed_addresses") is None
    sigs = await repo.list_withdrawal_signatures(int(created.id))
    assert sigs == []


@pytest.mark.asyncio
async def test_clear_offchain_signatures_rejects_external(
    order_service: OrderService,
    test_db,
    test_redis,
    test_settings,
):
    owner = WalletUser(
        nickname="clr_ext_space",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:clr_ext_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w_ext = Wallet(
        name="ext_clr",
        encrypted_mnemonic=None,
        role="external",
        tron_address=_SIGNER_OTHER,
        owner_did=owner.did,
    )
    test_db.add(w_ext)
    await test_db.commit()
    await test_db.refresh(w_ext)

    repo = OrderRepository(session=test_db, redis=test_redis, settings=test_settings)
    created = await repo.insert_withdrawal_order(
        dedupe_key=withdrawal_dedupe_key("cleartokentest0002"),
        space_wallet_id=w_ext.id,
        payload={
            "kind": WITHDRAWAL_KIND,
            "status": "awaiting_signatures",
            "wallet_role": "external",
            "wallet_id": w_ext.id,
            "tron_address": w_ext.tron_address,
            "token": {"type": "native", "symbol": "TRX", "decimals": 6},
            "amount_raw": 1000,
            "destination_address": _SIGNER_OTHER,
            "threshold_n": 1,
            "threshold_m": 1,
            "actors_snapshot": [],
            "long_expiration_ms": False,
        },
    )
    await test_db.commit()

    with pytest.raises(ValueError, match="multisig"):
        await order_service.clear_offchain_signatures(
            "clr_ext_space", _SPACE_TRON, int(created.id)
        )


@pytest.mark.asyncio
async def test_submit_signed_multisig_two_of_two_then_broadcast(
    order_service: OrderService,
    test_db,
    test_redis,
    test_settings,
):
    """Multisig 2/2: первый submit — awaiting_signatures, второй — ready_to_broadcast (broadcast в cron)."""
    owner = WalletUser(
        nickname="sub_ms_space",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:sub_ms_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w_ms = Wallet(
        name="ms_sub",
        encrypted_mnemonic="enc",
        role="multisig",
        tron_address="TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5B",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_SIGNER_OTHER, _SPACE_TRON],
            "threshold_n": 2,
            "threshold_m": 2,
        },
    )
    test_db.add(w_ms)
    await test_db.commit()
    await test_db.refresh(w_ms)

    repo = OrderRepository(session=test_db, redis=test_redis, settings=test_settings)
    tok = "submittok_multisig_22_abc12345"
    dk = withdrawal_dedupe_key(tok)
    created = await repo.insert_withdrawal_order(
        dedupe_key=dk,
        space_wallet_id=w_ms.id,
        payload={
            "kind": WITHDRAWAL_KIND,
            "status": WITHDRAWAL_STATUS_AWAITING_SIGNATURES,
            "wallet_role": "multisig",
            "wallet_id": w_ms.id,
            "tron_address": w_ms.tron_address,
            "token": {"type": "native", "symbol": "TRX", "decimals": 6},
            "amount_raw": 1000,
            "destination_address": _SIGNER_OTHER,
            "threshold_n": 2,
            "threshold_m": 2,
            "actors_snapshot": sorted([_SIGNER_OTHER, _SPACE_TRON]),
            "long_expiration_ms": True,
            "active_permission_id": 3,
            "broadcast_tx_id": None,
        },
    )
    await test_db.commit()

    raw1 = {"expiration": 2_000_000_000_000, "timestamp": 1_999_000_000_000}
    out1 = await order_service.submit_signed_transaction(
        tok,
        {"txID": "pending1", "signature": ["a"], "raw_data": raw1},
        _SIGNER_OTHER,
    )
    assert out1.payload is not None
    assert out1.payload.get("status") == WITHDRAWAL_STATUS_AWAITING_SIGNATURES
    assert out1.payload.get("broadcast_tx_id") is None
    assert out1.payload.get("offchain_expiration_ms") == 2_000_000_000_000
    assert out1.payload.get("offchain_timestamp_ms") == 1_999_000_000_000
    assert out1.payload.get("offchain_signed_addresses") == [_SIGNER_OTHER]

    raw2 = {"expiration": 2_000_000_000_001, "timestamp": 2_000_000_000_000}
    out2 = await order_service.submit_signed_transaction(
        tok,
        {"txID": "finaltxid", "signature": ["a", "b"], "raw_data": raw2},
        _SPACE_TRON,
    )
    assert out2.payload is not None
    assert out2.payload.get("status") == WITHDRAWAL_STATUS_READY_TO_BROADCAST
    assert out2.payload.get("broadcast_tx_id") is None
    assert out2.payload.get("offchain_signed_addresses") == [_SIGNER_OTHER, _SPACE_TRON]
    assert out2.payload.get("offchain_expiration_ms") == 2_000_000_000_001
    assert out2.payload.get("offchain_timestamp_ms") == 2_000_000_000_000


@pytest.mark.asyncio
async def test_broadcast_ready_withdrawals_success(
    order_service: OrderService,
    test_db,
    test_redis,
    test_settings,
    monkeypatch,
):
    """ready_to_broadcast + мок TronGrid: broadcast_submitted и txid из signed tx."""

    class FakeTronGrid:
        def __init__(self, settings=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def broadcast_transaction(self, signed):
            assert signed.get("txID") == "finaltxid"
            return {"result": True}

        monkeypatch.setattr(
            "services.order.TronGridClient",
            lambda settings=None: FakeTronGrid(),
        )

    owner = WalletUser(
        nickname="sub_ms_bcast_space",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:sub_ms_bcast_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w_ms = Wallet(
        name="ms_bcast",
        encrypted_mnemonic="enc",
        role="multisig",
        tron_address="TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5C",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_SIGNER_OTHER, _SPACE_TRON],
            "threshold_n": 2,
            "threshold_m": 2,
        },
    )
    test_db.add(w_ms)
    await test_db.commit()
    await test_db.refresh(w_ms)

    repo = OrderRepository(session=test_db, redis=test_redis, settings=test_settings)
    tok = "submittok_multisig_bcast_ok_xyz"
    dk = withdrawal_dedupe_key(tok)
    created = await repo.insert_withdrawal_order(
        dedupe_key=dk,
        space_wallet_id=w_ms.id,
        payload={
            "kind": WITHDRAWAL_KIND,
            "status": WITHDRAWAL_STATUS_AWAITING_SIGNATURES,
            "wallet_role": "multisig",
            "wallet_id": w_ms.id,
            "tron_address": w_ms.tron_address,
            "token": {"type": "native", "symbol": "TRX", "decimals": 6},
            "amount_raw": 1000,
            "destination_address": _SIGNER_OTHER,
            "threshold_n": 2,
            "threshold_m": 2,
            "actors_snapshot": sorted([_SIGNER_OTHER, _SPACE_TRON]),
            "long_expiration_ms": True,
            "active_permission_id": 3,
            "broadcast_tx_id": None,
        },
    )
    await test_db.commit()

    raw1 = {"expiration": 2_000_000_000_000, "timestamp": 1_999_000_000_000}
    await order_service.submit_signed_transaction(
        tok,
        {"txID": "pending1", "signature": ["a"], "raw_data": raw1},
        _SIGNER_OTHER,
    )
    raw2 = {"expiration": 2_000_000_000_001, "timestamp": 2_000_000_000_000}
    await order_service.submit_signed_transaction(
        tok,
        {"txID": "finaltxid", "signature": ["a", "b"], "raw_data": raw2},
        _SPACE_TRON,
    )

    with patch("services.order.NotifyService", autospec=True) as mock_notify_cls:
        mock_notify = mock_notify_cls.return_value
        async def fake_send(*args, **kwargs): pass
        mock_notify.send_message.side_effect = fake_send
        mock_notify._message_for_event.return_value = "Broadcast ok"
        mock_notify._language_for_scope.return_value = "ru"

        stats = await order_service.broadcast_ready_withdrawals()
        assert stats.get("broadcasted") == 1
        assert stats.get("broadcast_errors") == 0
        # No notification on success broadcast (it's not confirmed yet)
        assert not mock_notify.send_message.called

    await test_db.commit()

    final = await repo.get_by_id(int(created.id))
    assert final is not None
    assert final.payload is not None
    assert final.payload.get("status") == WITHDRAWAL_STATUS_BROADCAST_SUBMITTED
    assert final.payload.get("broadcast_tx_id") == "finaltxid"


@pytest.mark.asyncio
async def test_submit_signed_multisig_rejects_signer_not_in_actors(
    order_service: OrderService,
    test_db,
    test_redis,
    test_settings,
):
    owner = WalletUser(
        nickname="sub_ms_rej_space",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:sub_ms_rej_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w_ms = Wallet(
        name="ms_rej",
        encrypted_mnemonic="enc",
        role="multisig",
        tron_address="TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5B",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta=default_meta_dict(),
    )
    test_db.add(w_ms)
    await test_db.commit()
    await test_db.refresh(w_ms)

    repo = OrderRepository(session=test_db, redis=test_redis, settings=test_settings)
    tok = "submittok_multisig_reject_xyz"
    await repo.insert_withdrawal_order(
        dedupe_key=withdrawal_dedupe_key(tok),
        space_wallet_id=w_ms.id,
        payload={
            "kind": WITHDRAWAL_KIND,
            "status": WITHDRAWAL_STATUS_AWAITING_SIGNATURES,
            "wallet_role": "multisig",
            "tron_address": w_ms.tron_address,
            "threshold_n": 2,
            "threshold_m": 2,
            "actors_snapshot": [_SIGNER_OTHER],
            "long_expiration_ms": True,
        },
    )
    await test_db.commit()

    with pytest.raises(ValueError, match="actors"):
        await order_service.submit_signed_transaction(
            tok,
            {"txID": "x"},
            _SPACE_TRON,
        )


@pytest.mark.asyncio
async def test_submit_signed_external_single_signer_broadcast(
    order_service: OrderService,
    test_db,
    test_redis,
    test_settings,
):
    """External: один подписант — сразу broadcast_submitted."""
    owner = WalletUser(
        nickname="sub_ext_space",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:sub_ext_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w_ext = Wallet(
        name="ext_sub",
        encrypted_mnemonic=None,
        role="external",
        tron_address=_SIGNER_OTHER,
        owner_did=owner.did,
    )
    test_db.add(w_ext)
    await test_db.commit()
    await test_db.refresh(w_ext)

    repo = OrderRepository(session=test_db, redis=test_redis, settings=test_settings)
    tok = "submittok_external_one"
    await repo.insert_withdrawal_order(
        dedupe_key=withdrawal_dedupe_key(tok),
        space_wallet_id=w_ext.id,
        payload={
            "kind": WITHDRAWAL_KIND,
            "status": WITHDRAWAL_STATUS_AWAITING_SIGNATURES,
            "wallet_role": "external",
            "tron_address": w_ext.tron_address,
            "threshold_n": 1,
            "threshold_m": 1,
            "actors_snapshot": [],
            "long_expiration_ms": False,
        },
    )
    await test_db.commit()

    out = await order_service.submit_signed_transaction(
        tok,
        {"txID": "exttx1"},
        _SIGNER_OTHER,
    )
    assert out.payload is not None
    assert out.payload.get("status") == WITHDRAWAL_STATUS_BROADCAST_SUBMITTED
    assert out.payload.get("broadcast_tx_id") == "exttx1"


@pytest.mark.asyncio
async def test_broadcast_ready_withdrawals_notifies_on_error(
    order_service: OrderService,
    test_db,
    test_redis,
    test_settings,
    monkeypatch,
):
    """broadcast_ready_withdrawals: если нода вернула ошибку, отправляем уведомление."""

    class FakeTronGridError:
        def __init__(self, settings=None): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def broadcast_transaction(self, signed):
            return {"result": False, "message": "OUT_OF_ENERGY"}

    monkeypatch.setattr("services.order.TronGridClient", lambda settings=None: FakeTronGridError())

    owner = WalletUser(
        nickname="bcast_err_space",
        wallet_address=_SPACE_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:bcast_err_space",
    )
    test_db.add(owner)
    await test_db.commit()

    w_ms = Wallet(
        name="ms_err",
        encrypted_mnemonic="enc",
        role="multisig",
        tron_address="TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5C",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_SIGNER_OTHER, _SPACE_TRON],
            "threshold_n": 1,
            "threshold_m": 2,
        },
    )
    test_db.add(w_ms)
    await test_db.commit()

    repo = OrderRepository(session=test_db, redis=test_redis, settings=test_settings)
    tok = "tok_bcast_err"
    await repo.insert_withdrawal_order(
        dedupe_key=withdrawal_dedupe_key(tok),
        space_wallet_id=w_ms.id,
        payload={
            "kind": WITHDRAWAL_KIND,
            "status": WITHDRAWAL_STATUS_READY_TO_BROADCAST,
            "wallet_role": "multisig",
            "wallet_id": w_ms.id,
            "tron_address": w_ms.tron_address,
            "token": {"type": "native", "symbol": "TRX", "decimals": 6},
            "amount_raw": 1000,
            "destination_address": _SIGNER_OTHER,
            "threshold_n": 1,
            "threshold_m": 2,
            "actors_snapshot": [_SIGNER_OTHER, _SPACE_TRON],
        },
    )
    await test_db.commit()

    with patch("services.order.NotifyService", autospec=True) as mock_notify_cls:
        mock_notify = mock_notify_cls.return_value
        async def fake_send(*args, **kwargs): pass
        mock_notify.send_message.side_effect = fake_send
        mock_notify._message_for_event.return_value = "Error text"
        mock_notify._language_for_scope.return_value = "ru"

        stats = await order_service.broadcast_ready_withdrawals()
        assert stats.get("broadcast_errors") == 1
        
        assert mock_notify.send_message.called
        args, _ = mock_notify.send_message.call_args
        assert args[1] == "Error text"
