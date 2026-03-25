"""POST /v1/spaces/{space}/balances."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db.models import Wallet, WalletUser
from services.balances import BalancesService
from web.endpoints.dependencies import (
    ResolvedSettings,
    get_balances_service,
    get_db,
    get_redis,
    get_required_wallet_address_for_space,
    get_settings,
)
from web.main import create_app

SPACE = "balspace"
OWNER_DID = "did:peer:owner-bal-test"
ACTOR_TRON = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
RAMP_TRON = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"
OTHER_TRON = "TJRabQmJZyN9iKh3PVfGYq3D9v9gS1deCW"
RAMP_ETH = "0x2222222222222222222222222222222222222222"


@pytest_asyncio.fixture
async def seeded_space_balances(test_db):
    test_db.add(
        WalletUser(
            wallet_address=ACTOR_TRON,
            blockchain="tron",
            did=OWNER_DID,
            nickname=SPACE,
        )
    )
    test_db.add(
        Wallet(
            name="ramp-ext",
            role="external",
            tron_address=RAMP_TRON,
            ethereum_address=None,
            owner_did=OWNER_DID,
            encrypted_mnemonic=None,
        )
    )
    test_db.add(
        Wallet(
            name="ramp-eth",
            role="external",
            tron_address=None,
            ethereum_address=RAMP_ETH,
            owner_did=OWNER_DID,
            encrypted_mnemonic=None,
        )
    )
    await test_db.commit()


@pytest_asyncio.fixture
async def main_app_space_balances(test_db, test_redis, test_settings, seeded_space_balances):
    app = create_app()

    mock_balances = MagicMock(spec=BalancesService)

    async def fake_list(
        wallet_addresses: list,
        contract_addresses: list,
        *,
        tron_api_key=None,
        refresh_cache: bool = False,
    ):
        tag = 1 if refresh_cache else 0
        return {
            a: {c: 100 + tag for c in contract_addresses}
            for a in wallet_addresses
        }

    mock_balances.list_tron_trc20_balances_raw = AsyncMock(side_effect=fake_list)

    async def fake_native(
        wallet_addresses: list,
        *,
        tron_api_key=None,
        refresh_cache: bool = False,
    ):
        tag = 1 if refresh_cache else 0
        return {a: 5_000_000 + tag for a in wallet_addresses}

    mock_balances.list_tron_native_trx_balances_raw = AsyncMock(side_effect=fake_native)

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        return ResolvedSettings(
            settings=test_settings,
            has_key=True,
            is_admin_configured=True,
            is_node_initialized=True,
        )

    async def override_wallet_address():
        return ACTOR_TRON

    def override_balances():
        return mock_balances

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_required_wallet_address_for_space] = (
        override_wallet_address
    )
    app.dependency_overrides[get_balances_service] = override_balances

    yield app, mock_balances
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_space_balances_success(main_app_space_balances, test_settings):
    app, mock_balances = main_app_space_balances
    contracts = [t.contract_address for t in test_settings.collateral_stablecoin.tokens]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/v1/spaces/{SPACE}/balances",
            json={
                "items": [
                    {
                        "address": RAMP_TRON,
                        "blockchain": "TRON",
                        "force_update": False,
                    }
                ]
            },
        )
    assert r.status_code == 200
    data = r.json()["items"]
    assert len(data) == 1
    assert data[0]["address"] == RAMP_TRON
    assert data[0]["blockchain"] == "TRON"
    assert data[0]["error"] is None
    for c in contracts:
        assert data[0]["balances_raw"][c] == "100"
    assert data[0]["native_balances"]["TRX"] == "5000000"
    mock_balances.list_tron_trc20_balances_raw.assert_awaited_once()
    mock_balances.list_tron_native_trx_balances_raw.assert_awaited_once()
    call_kw = mock_balances.list_tron_trc20_balances_raw.await_args
    assert call_kw.kwargs["refresh_cache"] is False
    assert mock_balances.list_tron_native_trx_balances_raw.await_args.kwargs["refresh_cache"] is False


@pytest.mark.asyncio
async def test_space_balances_force_update(main_app_space_balances, test_settings):
    app, mock_balances = main_app_space_balances
    contracts = [t.contract_address for t in test_settings.collateral_stablecoin.tokens]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/v1/spaces/{SPACE}/balances",
            json={
                "items": [
                    {"address": RAMP_TRON, "blockchain": "tron", "force_update": True}
                ]
            },
        )
    assert r.status_code == 200
    assert r.json()["items"][0]["balances_raw"][contracts[0]] == "101"
    assert r.json()["items"][0]["native_balances"]["TRX"] == "5000001"
    mock_balances.list_tron_trc20_balances_raw.assert_awaited_once()
    assert mock_balances.list_tron_trc20_balances_raw.await_args.kwargs["refresh_cache"] is True
    mock_balances.list_tron_native_trx_balances_raw.assert_awaited_once()
    assert mock_balances.list_tron_native_trx_balances_raw.await_args.kwargs["refresh_cache"] is True


@pytest.mark.asyncio
async def test_space_balances_eth_placeholder(main_app_space_balances):
    app, _mock_balances = main_app_space_balances
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/v1/spaces/{SPACE}/balances",
            json={
                "items": [
                    {
                        "address": RAMP_ETH,
                        "blockchain": "ETH",
                        "force_update": False,
                    }
                ]
            },
        )
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["blockchain"] == "ETH"
    assert item["balances_raw"] == {}
    assert item["native_balances"] == {}
    assert item["error"] == "eth_balances_not_implemented"


@pytest.mark.asyncio
async def test_space_balances_not_ramp_address(main_app_space_balances):
    app, _mock_balances = main_app_space_balances
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/v1/spaces/{SPACE}/balances",
            json={
                "items": [
                    {"address": OTHER_TRON, "blockchain": "TRON", "force_update": False}
                ]
            },
        )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "address_not_in_space_wallets"


@pytest.mark.asyncio
async def test_space_balances_no_space_access(
    test_db, test_redis, test_settings, seeded_space_balances
):
    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        return ResolvedSettings(
            settings=test_settings,
            has_key=True,
            is_admin_configured=True,
            is_node_initialized=True,
        )

    async def override_wallet_address():
        return OTHER_TRON

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_required_wallet_address_for_space] = (
        override_wallet_address
    )

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/spaces/{SPACE}/balances",
                json={
                    "items": [
                        {"address": RAMP_TRON, "blockchain": "TRON", "force_update": False}
                    ]
                },
            )
        assert r.status_code == 403
        assert r.json()["detail"] == "No access to this space"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_space_balances_unauthorized(test_db, test_redis, test_settings):
    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        return ResolvedSettings(
            settings=test_settings,
            has_key=True,
            is_admin_configured=True,
            is_node_initialized=True,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/v1/spaces/{SPACE}/balances",
                json={
                    "items": [
                        {"address": RAMP_TRON, "blockchain": "TRON", "force_update": False}
                    ]
                },
            )
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()
