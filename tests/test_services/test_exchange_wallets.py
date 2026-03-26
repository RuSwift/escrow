"""Тесты ExchangeWalletService.create_wallet (Ramp POST)."""
import pytest

from db.models import WalletUserSubRole
from repos.wallet_user import WalletUserSubResource
from services.exchange_wallets import ExchangeWalletService
from services.multisig_wallet.constants import (
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_PENDING_CONFIG,
)
from services.wallet_user import WalletUserService


SPACE_NAME = "exch_wallet_test_space"
OWNER_WALLET = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
SUB_VALID_TRON = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"
CUSTOM_VALID_TRON = "TYDkyTwMF7ti5R8VstRruqz4N9mGne2CdF"


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
    exchange_space_owner_sub, exchange_wallet_service
):
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="multisig",
        blockchain="tron",
        name="Msig A",
    )
    assert row.role == "multisig"
    assert row.tron_address.startswith("T")
    assert row.ethereum_address and row.ethereum_address.startswith("0x")
    assert row.multisig_setup_status == MULTISIG_STATUS_PENDING_CONFIG
    assert row.multisig_setup_meta is not None
    assert row.multisig_setup_meta.get("min_trx_sun")


@pytest.mark.asyncio
async def test_create_external_custom_tron_only(
    exchange_space_owner_sub, exchange_wallet_service
):
    row = await exchange_wallet_service.create_wallet(
        SPACE_NAME,
        OWNER_WALLET,
        role="external",
        blockchain="tron",
        name="Bank ext",
        tron_address=CUSTOM_VALID_TRON,
    )
    assert row.role == "external"
    assert row.tron_address == CUSTOM_VALID_TRON
    assert row.ethereum_address is None


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
    updated = await exchange_wallet_service.patch_multisig_setup(
        SPACE_NAME,
        OWNER_WALLET,
        row.id,
        multisig_actors=[tr],
        multisig_threshold_n=1,
        multisig_threshold_m=1,
    )
    assert updated is not None
    assert updated.multisig_setup_status == MULTISIG_STATUS_AWAITING_FUNDING
    assert updated.multisig_setup_meta.get("actors") == [tr]
