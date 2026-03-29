"""MultisigWalletMaintenanceService: баланс и state machine (с моками сети)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from db.models import Wallet
from services.multisig_wallet.constants import (
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_PENDING_CONFIG,
    MULTISIG_STATUS_READY_FOR_PERMISSIONS,
)
from services.multisig_wallet.maintenance import MultisigWalletMaintenanceService
from services.multisig_wallet.meta import default_meta_dict

# Адрес подписанта, отличный от tron_address тестового multisig-кошелька
_MSIG_SIGNER_TRON = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"


@pytest.fixture
def multisig_maintenance(test_db, test_redis: Redis, test_settings):
    return MultisigWalletMaintenanceService(
        session=test_db, redis=test_redis, settings=test_settings
    )


def _make_fake_client(
    account_data: Optional[Dict[str, Any]] = None,
    estimate_sun: int = 100_000,
):
    """Фейковый TronGridClient, пригодный для использования как async context manager."""

    class FakeClient:
        async def get_account(self, address: str) -> Dict[str, Any]:
            return account_data or {"active_permission": []}

        async def get_transaction_success(self, tx_id: str) -> Optional[bool]:
            return None

        async def estimate_permission_update_sun(self, **kwargs: Any) -> int:
            return estimate_sun

        async def permission_update_sign_and_broadcast(self, **kwargs: Any):
            return ("faketxid", {"result": True})

    @asynccontextmanager
    async def _ctx(*args: Any, **kwargs: Any):
        yield FakeClient()

    return _ctx


@pytest.mark.asyncio
async def test_process_wallet_pending_config_noop(
    multisig_maintenance: MultisigWalletMaintenanceService,
    test_db,
):
    w = Wallet(
        name="m",
        encrypted_mnemonic="enc",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x1111111111111111111111111111111111111111",
        role="multisig",
        owner_did="did:test",
        multisig_setup_status=MULTISIG_STATUS_PENDING_CONFIG,
        multisig_setup_meta=default_meta_dict(),
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)
    changed = await multisig_maintenance.process_wallet(w, force_balance_refresh=False)
    assert changed is False


@pytest.mark.asyncio
async def test_process_wallet_awaiting_funding_updates_balance_below_min(
    multisig_maintenance: MultisigWalletMaintenanceService,
    test_db,
    monkeypatch: pytest.MonkeyPatch,
):
    w = Wallet(
        name="m2",
        encrypted_mnemonic="enc",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x2222222222222222222222222222222222222222",
        role="multisig",
        owner_did="did:t",
        multisig_setup_status=MULTISIG_STATUS_AWAITING_FUNDING,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_MSIG_SIGNER_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
            "min_trx_sun": 999_999_999,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    async def fake_bal(*args, **kwargs):
        return {w.tron_address: 1_000_000}

    monkeypatch.setattr(
        multisig_maintenance._balances,
        "list_tron_native_trx_balances_raw",
        fake_bal,
    )
    monkeypatch.setattr(
        "services.multisig_wallet.maintenance.TronGridClient",
        _make_fake_client(account_data={"active_permission": []}),
    )

    changed = await multisig_maintenance.process_wallet(
        w, force_balance_refresh=False
    )
    assert changed is True
    await test_db.commit()
    await test_db.refresh(w)
    assert w.multisig_setup_status == MULTISIG_STATUS_AWAITING_FUNDING
    assert w.multisig_setup_meta.get("last_trx_balance_sun") == 1_000_000


@pytest.mark.asyncio
async def test_ready_for_permissions_precheck_recalculates_min_and_waits_funding(
    multisig_maintenance: MultisigWalletMaintenanceService,
    test_db,
    monkeypatch: pytest.MonkeyPatch,
):
    w = Wallet(
        name="m3",
        encrypted_mnemonic="enc",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x3333333333333333333333333333333333333333",
        role="multisig",
        owner_did="did:t",
        multisig_setup_status=MULTISIG_STATUS_READY_FOR_PERMISSIONS,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_MSIG_SIGNER_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
            "last_trx_balance_sun": 120_000,
            "min_trx_sun": 100_000,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    async def fake_bal(*args, **kwargs):
        return {w.tron_address: 120_000}

    monkeypatch.setattr(
        multisig_maintenance._balances,
        "list_tron_native_trx_balances_raw",
        fake_bal,
    )
    # estimate_sun=200_000 > last_trx_balance_sun=120_000 → ожидаем переход в AWAITING_FUNDING
    monkeypatch.setattr(
        "services.multisig_wallet.maintenance.TronGridClient",
        _make_fake_client(
            account_data={"active_permission": []},
            estimate_sun=200_000,
        ),
    )

    changed = await multisig_maintenance.process_wallet(w, force_balance_refresh=False)
    assert changed is True
    await test_db.commit()
    await test_db.refresh(w)
    assert w.multisig_setup_status == MULTISIG_STATUS_AWAITING_FUNDING
    assert int(w.multisig_setup_meta.get("min_trx_sun") or 0) == 200_000
