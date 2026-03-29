"""Тесты ExchangeWalletService.create_wallet (Ramp POST)."""
import pytest
from sqlalchemy import select

from db.models import Wallet, WalletUserSubRole
from repos.wallet_user import WalletUserSubResource
from services.exchange_wallets import (
    ExchangeWalletService,
    MultisigDeleteBlockedError,
)
from services.notify import NotifyService, RampNotifyEvent
from services.multisig_wallet.constants import (
    MULTISIG_DEFAULT_PERMISSION_NAME,
    MULTISIG_STATUS_ACTIVE,
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_FAILED,
    MULTISIG_STATUS_PENDING_CONFIG,
    MULTISIG_STATUS_RECONFIGURE,
)
from services.multisig_wallet.meta import merge_meta
from services.wallet_user import WalletUserService


SPACE_NAME = "exch_wallet_test_space"
OWNER_WALLET = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
SUB_VALID_TRON = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"
CUSTOM_VALID_TRON = "TYDkyTwMF7ti5R8VstRruqz4N9mGne2CdF"


def _mock_tron_grid_getaccount(monkeypatch: pytest.MonkeyPatch, account: dict) -> None:
    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get_account(self, address: str):
            return account

    monkeypatch.setattr(
        "services.exchange_wallets.TronGridClient",
        lambda **kwargs: Client(),
    )


@pytest.fixture
def exchange_wallet_service(test_db, test_redis, test_settings) -> ExchangeWalletService:
    return ExchangeWalletService(
        session=test_db, redis=test_redis, settings=test_settings
    )


@pytest.fixture
async def exchange_space_owner_sub(exchange_wallet_service):
    wu = WalletUserService(
        session=exchange_wallet_service._session,
        redis=exchange_wallet_service._redis,
        settings=exchange_wallet_service._settings,
    )
    owner = await wu.create_user(OWNER_WALLET, "tron", SPACE_NAME)
    sub = await exchange_wallet_service._users.add_sub(
        owner.id,
        WalletUserSubResource.Create(
            wallet_address=SUB_VALID_TRON,
            blockchain="tron",
            nickname="mgr_one",
            roles=[WalletUserSubRole.operator],
        ),
    )
    await exchange_wallet_service._session.commit()
    return {"owner": owner, "sub": sub}


@pytest.mark.asyncio
async def test_create_multisig_server_mnemonic(
    exchange_space_owner_sub, exchange_wallet_service, monkeypatch
):
    calls = []

    async def _capture(self, scope, roles, event, payload, *, language=None):
        calls.append((scope, list(roles), event, dict(payload), language))

    monkeypatch.setattr(NotifyService, "notify_roles_event", _capture)

    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Msig A",
    )
    assert len(calls) == 1
    assert calls[0][0] == SPACE_NAME
    assert calls[0][1] == ["owner"]
    assert calls[0][2] == RampNotifyEvent.RAMP_WALLET_CREATED
    assert calls[0][3]["wallet_name"] == "Msig A"
    assert calls[0][3]["role"] == "multisig"
    assert calls[0][4] is None

    assert row.role == "multisig"
    assert row.tron_address.startswith("T")
    assert row.ethereum_address and row.ethereum_address.startswith("0x")
    assert row.multisig_setup_status == MULTISIG_STATUS_PENDING_CONFIG
    assert row.multisig_setup_meta is not None
    assert row.multisig_setup_meta.get("min_trx_sun")


@pytest.mark.asyncio
async def test_create_external_custom_tron_only(
    exchange_space_owner_sub, exchange_wallet_service, monkeypatch
):
    calls = []

    async def _capture(self, scope, roles, event, payload, *, language="ru"):
        calls.append(event)

    monkeypatch.setattr(NotifyService, "notify_roles_event", _capture)

    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="external",
        blockchain="tron",
        name="Bank ext",
        tron_address=CUSTOM_VALID_TRON,
    )
    assert calls == [RampNotifyEvent.RAMP_WALLET_CREATED]
    assert row.role == "external"
    assert row.tron_address == CUSTOM_VALID_TRON
    assert row.ethereum_address is None


@pytest.mark.asyncio
async def test_delete_wallet_notifies_owners(
    exchange_space_owner_sub, exchange_wallet_service, monkeypatch
):
    calls = []

    async def _capture(self, scope, roles, event, payload, *, language=None):
        calls.append((scope, list(roles), event, dict(payload)))

    monkeypatch.setattr(NotifyService, "notify_roles_event", _capture)

    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="external",
        blockchain="tron",
        name="ToDelete",
        tron_address=CUSTOM_VALID_TRON,
    )
    assert calls[0][2] == RampNotifyEvent.RAMP_WALLET_CREATED
    calls.clear()

    ok = await exchange_wallet_service.delete_wallet(
        SPACE_NAME, OWNER_WALLET, row.id
    )
    assert ok is True
    assert len(calls) == 1
    assert calls[0][0] == SPACE_NAME
    assert calls[0][1] == ["owner"]
    assert calls[0][2] == RampNotifyEvent.RAMP_WALLET_DELETED
    assert calls[0][3]["wallet_name"] == "ToDelete"
    assert calls[0][3]["wallet_id"] == row.id
    assert calls[0][3]["role"] == "external"
    assert calls[0][3]["tron_address"] == CUSTOM_VALID_TRON


@pytest.mark.asyncio
async def test_delete_multisig_ok_with_balance_guard_skipped(
    exchange_space_owner_sub, exchange_wallet_service, monkeypatch
):
    """Удаление multisig: проверка балансов заменена noop (без TronGrid в тесте)."""

    async def _noop(self, addr):
        return None

    monkeypatch.setattr(
        ExchangeWalletService,
        "_assert_multisig_balances_allow_delete",
        _noop,
    )
    calls = []

    async def _capture(self, scope, roles, event, payload, *, language=None):
        calls.append((scope, list(roles), event, dict(payload)))

    monkeypatch.setattr(NotifyService, "notify_roles_event", _capture)

    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="MsigDel",
    )
    calls.clear()
    ok = await exchange_wallet_service.delete_wallet(
        SPACE_NAME, OWNER_WALLET, row.id
    )
    assert ok is True
    assert len(calls) == 1
    assert calls[0][2] == RampNotifyEvent.RAMP_WALLET_DELETED
    assert calls[0][3]["role"] == "multisig"


@pytest.mark.asyncio
async def test_delete_multisig_blocked_by_balance_check(
    exchange_space_owner_sub, exchange_wallet_service, monkeypatch
):
    async def _block(self, addr):
        raise MultisigDeleteBlockedError(
            "stable_balance_too_high",
            total_usd_approx=6.0,
        )

    monkeypatch.setattr(
        ExchangeWalletService,
        "_assert_multisig_balances_allow_delete",
        _block,
    )
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="MsigBlock",
    )
    with pytest.raises(MultisigDeleteBlockedError) as ei:
        await exchange_wallet_service.delete_wallet(
            SPACE_NAME, OWNER_WALLET, row.id
        )
    assert ei.value.code == "stable_balance_too_high"


@pytest.mark.asyncio
async def test_create_external_participant_sub(
    exchange_space_owner_sub, exchange_wallet_service
):
    sub = exchange_space_owner_sub["sub"]
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="external",
        blockchain="tron",
        participant_sub_id=sub.id,
    )
    assert row.tron_address == SUB_VALID_TRON
    assert row.name == "mgr_one"


@pytest.mark.asyncio
async def test_duplicate_name_raises(exchange_space_owner_sub, exchange_wallet_service):
    await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Dup",
    )
    with pytest.raises(ValueError, match="name already exists"):
        await exchange_wallet_service.create_wallet(
            SPACE_NAME,
            OWNER_WALLET,
            role="multisig",
            blockchain="tron",
            name="Dup",
        )


@pytest.mark.asyncio
async def test_participant_wrong_id_raises(
    exchange_space_owner_sub, exchange_wallet_service
):
    with pytest.raises(ValueError, match="Participant not found"):
        await exchange_wallet_service.create_wallet(
            SPACE_NAME,
            OWNER_WALLET,
            role="external",
            blockchain="tron",
            participant_sub_id=999999,
        )


@pytest.mark.asyncio
async def test_patch_multisig_setup_actors(
    exchange_space_owner_sub, exchange_wallet_service
):
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Patch Msig",
    )
    tr = row.tron_address
    assert tr
    signer = SUB_VALID_TRON
    assert signer != tr
    updated = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_actors=[signer],
        multisig_threshold_n=1,
        multisig_threshold_m=1,
    )
    assert updated is not None
    assert updated.multisig_setup_status == MULTISIG_STATUS_AWAITING_FUNDING
    assert updated.multisig_setup_meta.get("actors") == [signer]


@pytest.mark.asyncio
async def test_patch_multisig_begin_cancel_reconfigure(
    exchange_space_owner_sub, exchange_wallet_service, test_db, monkeypatch
):
    _mock_tron_grid_getaccount(
        monkeypatch,
        {
            "active_permission": [
                {
                    "type": 2,
                    "permission_name": "ms_cancel",
                    "threshold": 1,
                    "keys": [{"address": SUB_VALID_TRON, "weight": 1}],
                }
            ]
        },
    )
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Reconf Msig",
    )
    res = await test_db.execute(select(Wallet).where(Wallet.id == row.id))
    w = res.scalar_one()
    w.multisig_setup_status = MULTISIG_STATUS_ACTIVE
    await test_db.commit()

    u1 = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_begin_reconfigure=True,
    )
    assert u1 is not None
    assert u1.multisig_setup_status == MULTISIG_STATUS_RECONFIGURE
    assert u1.multisig_setup_meta.get("reconfigure_previous_status") == MULTISIG_STATUS_ACTIVE

    u2 = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_cancel_reconfigure=True,
    )
    assert u2 is not None
    assert u2.multisig_setup_status == MULTISIG_STATUS_ACTIVE
    assert "reconfigure_previous_status" not in (u2.multisig_setup_meta or {})


@pytest.mark.asyncio
async def test_patch_multisig_begin_reconfigure_from_failed(
    exchange_space_owner_sub, exchange_wallet_service, test_db, monkeypatch
):
    _mock_tron_grid_getaccount(
        monkeypatch,
        {
            "active_permission": [
                {
                    "type": 2,
                    "permission_name": "ms_fail_cancel",
                    "threshold": 1,
                    "keys": [{"address": SUB_VALID_TRON, "weight": 1}],
                }
            ]
        },
    )
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Reconf Fail",
    )
    res = await test_db.execute(select(Wallet).where(Wallet.id == row.id))
    w = res.scalar_one()
    w.multisig_setup_status = MULTISIG_STATUS_FAILED
    w.multisig_setup_meta = {**(w.multisig_setup_meta or {}), "last_error": "x"}
    await test_db.commit()

    u1 = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_begin_reconfigure=True,
    )
    assert u1.multisig_setup_status == MULTISIG_STATUS_RECONFIGURE
    assert u1.multisig_setup_meta.get("reconfigure_previous_status") == MULTISIG_STATUS_FAILED

    u2 = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_cancel_reconfigure=True,
    )
    assert u2.multisig_setup_status == MULTISIG_STATUS_FAILED


@pytest.mark.asyncio
async def test_patch_reconfigure_actors_matches_chain_noop(
    exchange_space_owner_sub, exchange_wallet_service, test_db, monkeypatch
):
    notify_events = []

    async def _cap_notify(self, scope, roles, event, payload, *, language="ru"):
        notify_events.append(event)

    monkeypatch.setattr(NotifyService, "notify_roles_event", _cap_notify)

    signer = SUB_VALID_TRON
    _mock_tron_grid_getaccount(
        monkeypatch,
        {
            "active_permission": [
                {
                    "type": 2,
                    "permission_name": MULTISIG_DEFAULT_PERMISSION_NAME,
                    "threshold": 1,
                    "keys": [{"address": signer, "weight": 1}],
                }
            ]
        },
    )
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Reconf Noop",
    )
    res = await test_db.execute(select(Wallet).where(Wallet.id == row.id))
    w = res.scalar_one()
    w.multisig_setup_status = MULTISIG_STATUS_ACTIVE
    w.multisig_setup_meta = merge_meta(
        w.multisig_setup_meta,
        {
            "actors": [signer],
            "threshold_n": 1,
            "threshold_m": 1,
            "permission_name": MULTISIG_DEFAULT_PERMISSION_NAME,
        },
    )
    await test_db.commit()

    await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_begin_reconfigure=True,
    )
    out = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_actors=[signer],
        multisig_threshold_n=1,
        multisig_threshold_m=1,
    )
    assert out.multisig_setup_status == MULTISIG_STATUS_ACTIVE
    assert out.multisig_setup_meta.get("reconfigure_unchanged") is True
    assert "reconfigure_previous_status" not in (out.multisig_setup_meta or {})
    assert RampNotifyEvent.RAMP_WALLET_CREATED in notify_events
    assert notify_events[-1] == RampNotifyEvent.MULTISIG_RECONFIGURED_NOOP


@pytest.mark.asyncio
async def test_patch_reconfigure_actors_differs_goes_funding(
    exchange_space_owner_sub, exchange_wallet_service, test_db, monkeypatch
):
    _mock_tron_grid_getaccount(
        monkeypatch,
        {
            "active_permission": [
                {
                    "type": 2,
                    "permission_name": MULTISIG_DEFAULT_PERMISSION_NAME,
                    "threshold": 1,
                    "keys": [{"address": SUB_VALID_TRON, "weight": 1}],
                }
            ]
        },
    )
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Reconf Diff",
    )
    res = await test_db.execute(select(Wallet).where(Wallet.id == row.id))
    w = res.scalar_one()
    w.multisig_setup_status = MULTISIG_STATUS_ACTIVE
    w.multisig_setup_meta = merge_meta(
        w.multisig_setup_meta,
        {
            "actors": [SUB_VALID_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
            "permission_name": MULTISIG_DEFAULT_PERMISSION_NAME,
        },
    )
    await test_db.commit()

    await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_begin_reconfigure=True,
    )
    out = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_actors=[CUSTOM_VALID_TRON],
        multisig_threshold_n=1,
        multisig_threshold_m=1,
    )
    assert out.multisig_setup_status == MULTISIG_STATUS_AWAITING_FUNDING
    assert out.multisig_setup_meta.get("reconfigure_previous_status") == MULTISIG_STATUS_ACTIVE
    assert out.multisig_setup_meta.get("actors") == [CUSTOM_VALID_TRON]


@pytest.mark.asyncio
async def test_patch_cancel_reconfigure_from_awaiting_funding(
    exchange_space_owner_sub, exchange_wallet_service, test_db, monkeypatch
):
    chain_acc = {
        "active_permission": [
            {
                "type": 2,
                "permission_name": MULTISIG_DEFAULT_PERMISSION_NAME,
                "threshold": 1,
                "keys": [{"address": SUB_VALID_TRON, "weight": 1}],
            }
        ]
    }
    _mock_tron_grid_getaccount(monkeypatch, chain_acc)
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Reconf Cancel Fund",
    )
    res = await test_db.execute(select(Wallet).where(Wallet.id == row.id))
    w = res.scalar_one()
    w.multisig_setup_status = MULTISIG_STATUS_ACTIVE
    w.multisig_setup_meta = merge_meta(
        w.multisig_setup_meta,
        {
            "actors": [SUB_VALID_TRON],
            "threshold_n": 1,
            "threshold_m": 1,
            "permission_name": MULTISIG_DEFAULT_PERMISSION_NAME,
        },
    )
    await test_db.commit()
    await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_begin_reconfigure=True,
    )
    await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_actors=[CUSTOM_VALID_TRON],
        multisig_threshold_n=1,
        multisig_threshold_m=1,
    )
    _mock_tron_grid_getaccount(monkeypatch, chain_acc)
    out = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_cancel_reconfigure=True,
    )
    assert out.multisig_setup_status == MULTISIG_STATUS_ACTIVE
    assert "reconfigure_previous_status" not in (out.multisig_setup_meta or {})
    assert out.multisig_setup_meta.get("actors") == [SUB_VALID_TRON]
