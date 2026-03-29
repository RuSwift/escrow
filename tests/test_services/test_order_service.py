"""OrderService.refresh_ephemeral и список ордеров."""

from __future__ import annotations

import pytest
from redis.asyncio import Redis

from db.models import Wallet, WalletUser
from services.multisig_wallet.constants import (
    MULTISIG_STATUS_ACTIVE,
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_PENDING_CONFIG,
)
from services.multisig_wallet.meta import default_meta_dict
from services.order import (
    ORDER_KIND_MULTISIG_PIPELINE,
    ORDER_KIND_MULTISIG_SPACE_DRIFT,
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
