import pytest
from redis.asyncio import Redis

from services.balances import TRON_NATIVE_TRX_CACHE_KEY, BalancesService


WALLET_OWNER = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
WALLET_SUB_VALID_TRON = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"


@pytest.fixture
def balances_service(test_db, test_redis: Redis, test_settings) -> BalancesService:
    return BalancesService(session=test_db, redis=test_redis, settings=test_settings)


def _contracts_from_settings(test_settings) -> list[str]:
    return [t.contract_address for t in test_settings.collateral_stablecoin.tokens]


@pytest.mark.asyncio
async def test_list_tron_trc20_balances_raw_caches_result(
    balances_service: BalancesService,
    test_redis: Redis,
    test_settings,
    monkeypatch: pytest.MonkeyPatch,
):
    calls = 0

    contracts = _contracts_from_settings(test_settings)
    contracts_hash = balances_service._contracts_hash(contracts)

    async def fake_trigger(
        self: BalancesService,
        *,
        owner_wallet_address: str,
        contract_address: str,
        tron_api_key: str | None,
        session,
    ) -> int:
        nonlocal calls
        calls += 1
        return 1_000_000 if contract_address == contracts[0] else 2_000_000

    monkeypatch.setattr(
        BalancesService,
        "_trigger_constant_balance_of",
        fake_trigger,
        raising=True,
    )

    tron_api_key = "test-tron-api-key"
    wallets = [WALLET_OWNER]

    out1 = await balances_service.list_tron_trc20_balances_raw(
        wallets,
        contracts,
        tron_api_key=tron_api_key,
    )
    assert set(out1.keys()) == set(wallets)
    assert calls == len(contracts) * len(wallets)
    assert out1[WALLET_OWNER][contracts[0]] == 1_000_000
    assert out1[WALLET_OWNER][contracts[1]] == 2_000_000

    # Второй вызов должен пойти из Redis
    out2 = await balances_service.list_tron_trc20_balances_raw(
        wallets,
        contracts,
        tron_api_key=tron_api_key,
    )
    assert out2 == out1
    assert calls == len(contracts) * len(wallets)

    key = balances_service._cache_key(
        wallet_address=WALLET_OWNER, contracts_hash=contracts_hash
    )
    ttl = await test_redis.ttl(key)
    assert ttl is not None
    assert 0 < ttl <= 60


@pytest.mark.asyncio
async def test_fallback_to_db_on_tron_error(
    balances_service: BalancesService,
    monkeypatch: pytest.MonkeyPatch,
    test_db,
    test_redis: Redis,
    test_settings,
):
    contracts = _contracts_from_settings(test_settings)
    wallets = [WALLET_OWNER]

    # Pre-fill DB with some known balances.
    balances_raw = {contracts[0]: 111, contracts[1]: 222}
    await balances_service._upsert_balances_to_db_raw(
        wallet_address=WALLET_OWNER, balances_raw=balances_raw
    )

    calls = 0

    async def fake_trigger_fail(
        self: BalancesService,
        *,
        owner_wallet_address: str,
        contract_address: str,
        tron_api_key: str | None,
        session,
    ) -> int:
        nonlocal calls
        calls += 1
        raise RuntimeError("TronGrid is down")

    monkeypatch.setattr(
        BalancesService,
        "_trigger_constant_balance_of",
        fake_trigger_fail,
        raising=True,
    )

    out = await balances_service.list_tron_trc20_balances_raw(
        wallets,
        contracts,
        tron_api_key="test-tron-api-key",
        refresh_cache=True,
    )

    # На первой ошибке TronGrid мы делаем "последнюю попытку" из БД и прекращаем
    # дальнейшие запросы по остальным контрактам.
    assert calls == 1
    assert out[WALLET_OWNER][contracts[0]] == 111
    assert out[WALLET_OWNER][contracts[1]] == 222


@pytest.mark.asyncio
async def test_list_tron_trc20_balances_raw_invalid_address_raises(
    balances_service: BalancesService,
):
    with pytest.raises(ValueError):
        await balances_service.list_tron_trc20_balances_raw(
            ["not-a-tron-address"],
            ["TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"],
            tron_api_key="test-tron-api-key",
        )


@pytest.mark.asyncio
async def test_list_tron_trc20_balances_raw_without_api_key_still_calls_tron(
    balances_service: BalancesService,
    monkeypatch: pytest.MonkeyPatch,
    test_settings,
):
    """Без ключа TronGrid всё равно вызывается; в хук передаётся None (без заголовка)."""

    def resolve_no_key(self, tron_api_key):
        return None

    monkeypatch.setattr(BalancesService, "_resolve_tron_api_key", resolve_no_key)

    contracts = _contracts_from_settings(test_settings)
    wallets = [WALLET_OWNER]
    calls = 0

    async def fake_trigger(
        self: BalancesService,
        *,
        owner_wallet_address: str,
        contract_address: str,
        tron_api_key: str | None,
        session,
    ) -> int:
        nonlocal calls
        calls += 1
        assert tron_api_key is None
        return 777

    monkeypatch.setattr(
        BalancesService,
        "_trigger_constant_balance_of",
        fake_trigger,
        raising=True,
    )

    out = await balances_service.list_tron_trc20_balances_raw(
        wallets,
        contracts,
        tron_api_key=None,
        refresh_cache=True,
    )
    assert calls == len(contracts) * len(wallets)
    assert all(v == 777 for v in out[WALLET_OWNER].values())


@pytest.mark.asyncio
async def test_list_tron_native_trx_balances_raw_caches(
    balances_service: BalancesService,
    test_redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
):
    calls = 0

    async def fake_getaccount(
        self: BalancesService,
        *,
        owner_wallet_address: str,
        tron_api_key: str | None,
        session,
    ) -> int:
        nonlocal calls
        calls += 1
        assert owner_wallet_address == WALLET_OWNER
        return 12_345_678

    monkeypatch.setattr(
        BalancesService,
        "_tron_getaccount_balance_sun",
        fake_getaccount,
        raising=True,
    )

    wallets = [WALLET_OWNER]
    out1 = await balances_service.list_tron_native_trx_balances_raw(
        wallets,
        tron_api_key="k",
    )
    assert out1[WALLET_OWNER] == 12_345_678
    assert calls == 1

    out2 = await balances_service.list_tron_native_trx_balances_raw(
        wallets,
        tron_api_key="k",
    )
    assert out2 == out1
    assert calls == 1

    rkey = balances_service._cache_key_native_trx(wallet_address=WALLET_OWNER)
    ttl = await test_redis.ttl(rkey)
    assert ttl is not None
    assert 0 < ttl <= 60


@pytest.mark.asyncio
async def test_list_tron_native_trx_balances_raw_db_fallback(
    balances_service: BalancesService,
    monkeypatch: pytest.MonkeyPatch,
    test_db,
    test_redis: Redis,
):
    await balances_service._upsert_balances_to_db_raw(
        wallet_address=WALLET_OWNER,
        balances_raw={TRON_NATIVE_TRX_CACHE_KEY: 999_000_000},
    )

    async def fail_getaccount(self, **kwargs):
        raise RuntimeError("down")

    monkeypatch.setattr(
        BalancesService,
        "_tron_getaccount_balance_sun",
        fail_getaccount,
        raising=True,
    )

    out = await balances_service.list_tron_native_trx_balances_raw(
        [WALLET_OWNER],
        tron_api_key="k",
        refresh_cache=True,
    )
    assert out[WALLET_OWNER] == 999_000_000

