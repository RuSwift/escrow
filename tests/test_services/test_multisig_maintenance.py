"""MultisigWalletMaintenanceService: баланс и state machine (с моками сети)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis

from db.models import Wallet, WalletUser
from services.multisig_wallet.constants import (
    MULTISIG_DEFAULT_PERMISSION_NAME,
    MULTISIG_STATUS_ACTIVE,
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_FAILED,
    MULTISIG_STATUS_PENDING_CONFIG,
    MULTISIG_STATUS_READY_FOR_PERMISSIONS,
)
from services.multisig_wallet.maintenance import MultisigWalletMaintenanceService
from services.multisig_wallet.meta import default_meta_dict

# Адрес подписанта, отличный от tron_address тестового multisig-кошелька
_MSIG_SIGNER_TRON = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"
# TRON владельца спейса (WalletUser) для list_tron_owner_addresses
_SPACE_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"


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

    monkeypatch.setattr(
        "services.multisig_wallet.maintenance.TronGridClient",
        _make_fake_client(
            account_data={"active_permission": [], "balance": 1_000_000},
        ),
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
    owner_wu = WalletUser(
        wallet_address=_SPACE_OWNER_TRON,
        blockchain="tron",
        did="did:t",
        nickname="ms_maint_ready_fp",
    )
    test_db.add(owner_wu)
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

    # estimate_sun=200_000 > last_trx_balance_sun=120_000 → ожидаем переход в AWAITING_FUNDING
    # owner_permission: на цепи владелец ещё multisig (подпись возможна); Active — пусто
    monkeypatch.setattr(
        "services.multisig_wallet.maintenance.TronGridClient",
        _make_fake_client(
            account_data={
                "active_permission": [],
                "balance": 120_000,
                "owner_permission": {
                    "permission_name": "owner",
                    "threshold": 1,
                    "keys": [
                        {
                            "address": "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
                            "weight": 1,
                        }
                    ],
                },
            },
            estimate_sun=200_000,
        ),
    )

    changed = await multisig_maintenance.process_wallet(w, force_balance_refresh=False)
    assert changed is True
    await test_db.commit()
    await test_db.refresh(w)
    assert w.multisig_setup_status == MULTISIG_STATUS_AWAITING_FUNDING
    assert int(w.multisig_setup_meta.get("min_trx_sun") or 0) == 200_000


@pytest.mark.asyncio
async def test_no_early_active_while_reconfigure_branch(
    multisig_maintenance: MultisigWalletMaintenanceService,
    test_db,
    monkeypatch: pytest.MonkeyPatch,
):
    """При незавершённой реконфигурации не ставим active по снимку цепи."""
    tron = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
    account_data = {
        "active_permission": [
            {
                "type": 2,
                "permission_name": MULTISIG_DEFAULT_PERMISSION_NAME,
                "threshold": 1,
                "keys": [{"address": _MSIG_SIGNER_TRON, "weight": 1}],
            }
        ]
    }
    w = Wallet(
        name="m_reconf_guard",
        encrypted_mnemonic="enc",
        tron_address=tron,
        ethereum_address="0x4444444444444444444444444444444444444444",
        role="multisig",
        owner_did="did:t",
        multisig_setup_status=MULTISIG_STATUS_AWAITING_FUNDING,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_MSIG_SIGNER_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
            "reconfigure_previous_status": MULTISIG_STATUS_ACTIVE,
            "min_trx_sun": 999_999_999,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    monkeypatch.setattr(
        "services.multisig_wallet.maintenance.TronGridClient",
        _make_fake_client(account_data=account_data),
    )

    changed = await multisig_maintenance.process_wallet(
        w, force_balance_refresh=False
    )
    assert changed is True
    await test_db.commit()
    await test_db.refresh(w)
    assert w.multisig_setup_status == MULTISIG_STATUS_AWAITING_FUNDING


@pytest.mark.asyncio
async def test_early_chain_active_syncs_without_notify(
    multisig_maintenance: MultisigWalletMaintenanceService,
    test_db,
    monkeypatch: pytest.MonkeyPatch,
):
    notify_events: list[str] = []

    async def capture_notify(wallet: Wallet, event: str) -> None:
        notify_events.append(event)

    monkeypatch.setattr(
        multisig_maintenance, "_notify_owners_multisig_event", capture_notify
    )

    tron = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
    account_data = {
        "active_permission": [
            {
                "type": 2,
                "permission_name": MULTISIG_DEFAULT_PERMISSION_NAME,
                "threshold": 1,
                "keys": [{"address": _MSIG_SIGNER_TRON, "weight": 1}],
            }
        ]
    }
    w = Wallet(
        name="m_early_sync",
        encrypted_mnemonic="enc",
        tron_address=tron,
        ethereum_address="0x5555555555555555555555555555555555555555",
        role="multisig",
        owner_did="did:owner_early",
        multisig_setup_status=MULTISIG_STATUS_AWAITING_FUNDING,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_MSIG_SIGNER_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    monkeypatch.setattr(
        "services.multisig_wallet.maintenance.TronGridClient",
        _make_fake_client(account_data=account_data),
    )

    changed = await multisig_maintenance.process_wallet(
        w, force_balance_refresh=False
    )
    assert changed is True
    assert notify_events == []
    await test_db.commit()
    await test_db.refresh(w)
    assert w.multisig_setup_status == MULTISIG_STATUS_ACTIVE


@pytest.mark.asyncio
async def test_ready_for_permissions_fails_without_tron_space_owner(
    multisig_maintenance: MultisigWalletMaintenanceService,
    test_db,
    monkeypatch: pytest.MonkeyPatch,
):
    """Нет TRON owner в спейсе — FAILED, без broadcast."""
    w = Wallet(
        name="m_no_owner",
        encrypted_mnemonic="enc",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x6666666666666666666666666666666666666666",
        role="multisig",
        owner_did="did:no_wallet_user",
        multisig_setup_status=MULTISIG_STATUS_READY_FOR_PERMISSIONS,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_MSIG_SIGNER_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
            "last_trx_balance_sun": 500_000,
            "min_trx_sun": 1,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    monkeypatch.setattr(
        "services.multisig_wallet.maintenance.TronGridClient",
        _make_fake_client(
            account_data={"active_permission": [], "balance": 500_000_000},
        ),
    )

    changed = await multisig_maintenance.process_wallet(w, force_balance_refresh=False)
    assert changed is True
    await test_db.commit()
    await test_db.refresh(w)
    assert w.multisig_setup_status == MULTISIG_STATUS_FAILED
    err = (w.multisig_setup_meta or {}).get("last_error") or ""
    assert "no TRON owner" in err.lower() or "tron owner" in err.lower()


@pytest.mark.asyncio
async def test_ready_for_permissions_fails_when_chain_owner_not_multisig(
    multisig_maintenance: MultisigWalletMaintenanceService,
    test_db,
    monkeypatch: pytest.MonkeyPatch,
):
    """Owner на цепи уже без ключа multisig — подпись с мнемоники невозможна."""
    owner_wu = WalletUser(
        wallet_address=_SPACE_OWNER_TRON,
        blockchain="tron",
        did="did:guard_t",
        nickname="ms_maint_guard_u",
    )
    test_db.add(owner_wu)
    w = Wallet(
        name="m_guard",
        encrypted_mnemonic="enc",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x7777777777777777777777777777777777777777",
        role="multisig",
        owner_did="did:guard_t",
        multisig_setup_status=MULTISIG_STATUS_READY_FOR_PERMISSIONS,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_MSIG_SIGNER_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
            "last_trx_balance_sun": 500_000,
            "min_trx_sun": 1,
        },
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    monkeypatch.setattr(
        "services.multisig_wallet.maintenance.TronGridClient",
        _make_fake_client(
            account_data={
                "active_permission": [],
                "balance": 500_000_000,
                "owner_permission": {
                    "keys": [
                        {"address": "TONLYOTHER111111111111111111111111111111", "weight": 1}
                    ],
                },
            },
        ),
    )

    changed = await multisig_maintenance.process_wallet(w, force_balance_refresh=False)
    assert changed is True
    await test_db.commit()
    await test_db.refresh(w)
    assert w.multisig_setup_status == MULTISIG_STATUS_FAILED
    err = (w.multisig_setup_meta or {}).get("last_error") or ""
    assert "on-chain owner" in err.lower() or "outside the app" in err.lower()
