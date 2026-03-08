"""
Тесты WalletService на реальной БД и Redis (fixtures из tests/conftest.py).
"""
import pytest

from services.wallet import WalletService


# Валидная мнемоника (BIP39), одна и та же для детерминированных адресов в тестах
VALID_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


@pytest.fixture
def wallet_service(test_db, test_redis, test_settings) -> WalletService:
    """WalletService с тестовой сессией, Redis и настройками."""
    return WalletService(
        session=test_db, redis=test_redis, settings=test_settings
    )


# --- create_wallet ---


@pytest.mark.asyncio
async def test_create_wallet_success(wallet_service):
    """create_wallet создаёт кошелёк и возвращает Get с id, name, адресами."""
    out = await wallet_service.create_wallet("Main Wallet", VALID_MNEMONIC)
    assert out.id >= 1
    assert out.name == "Main Wallet"
    assert out.tron_address
    assert len(out.tron_address) == 34
    assert out.tron_address.startswith("T")
    assert out.ethereum_address
    assert len(out.ethereum_address) == 42
    assert out.ethereum_address.startswith("0x")
    assert out.created_at is not None
    assert out.updated_at is not None


@pytest.mark.asyncio
async def test_create_wallet_name_stripped(wallet_service):
    """create_wallet обрезает пробелы в имени."""
    out = await wallet_service.create_wallet("  Ops  ", VALID_MNEMONIC)
    assert out.name == "Ops"


@pytest.mark.asyncio
async def test_create_wallet_invalid_mnemonic_raises(wallet_service):
    """Невалидная мнемоника поднимает ValueError."""
    with pytest.raises(ValueError, match="Invalid mnemonic phrase"):
        await wallet_service.create_wallet("W", "not a valid mnemonic phrase")


@pytest.mark.asyncio
async def test_create_wallet_duplicate_addresses_raises(wallet_service):
    """Повторное создание с той же мнемоникой (те же адреса) поднимает ValueError."""
    await wallet_service.create_wallet("First", VALID_MNEMONIC)
    with pytest.raises(ValueError, match="Wallet with these addresses already exists"):
        await wallet_service.create_wallet("Second", VALID_MNEMONIC)


# --- get_wallets ---


@pytest.mark.asyncio
async def test_get_wallets_empty(wallet_service):
    """Без кошельков get_wallets возвращает пустой список."""
    wallets = await wallet_service.get_wallets()
    assert wallets == []


@pytest.mark.asyncio
async def test_get_wallets_after_create(wallet_service):
    """После create_wallet get_wallets возвращает список с одним элементом."""
    created = await wallet_service.create_wallet("W1", VALID_MNEMONIC)
    wallets = await wallet_service.get_wallets()
    assert len(wallets) == 1
    assert wallets[0].id == created.id
    assert wallets[0].name == created.name


# --- get_wallet ---


@pytest.mark.asyncio
async def test_get_wallet_not_found_returns_none(wallet_service):
    """get_wallet с несуществующим id возвращает None."""
    assert await wallet_service.get_wallet(99999) is None


@pytest.mark.asyncio
async def test_get_wallet_after_create(wallet_service):
    """get_wallet возвращает созданный кошелёк по id."""
    created = await wallet_service.create_wallet("W1", VALID_MNEMONIC)
    found = await wallet_service.get_wallet(created.id)
    assert found is not None
    assert found.id == created.id
    assert found.name == created.name
    assert found.tron_address == created.tron_address


# --- update_wallet_name ---


@pytest.mark.asyncio
async def test_update_wallet_name_success(wallet_service):
    """update_wallet_name обновляет имя и возвращает обновлённый Get."""
    created = await wallet_service.create_wallet("Old Name", VALID_MNEMONIC)
    updated = await wallet_service.update_wallet_name(created.id, "New Name")
    assert updated is not None
    assert updated.id == created.id
    assert updated.name == "New Name"
    found = await wallet_service.get_wallet(created.id)
    assert found.name == "New Name"


@pytest.mark.asyncio
async def test_update_wallet_name_not_found_returns_none(wallet_service):
    """update_wallet_name с несуществующим id возвращает None."""
    updated = await wallet_service.update_wallet_name(99999, "Any")
    assert updated is None


@pytest.mark.asyncio
async def test_update_wallet_name_strips_whitespace(wallet_service):
    """update_wallet_name обрезает пробелы в имени."""
    created = await wallet_service.create_wallet("W", VALID_MNEMONIC)
    updated = await wallet_service.update_wallet_name(created.id, "  Trimmed  ")
    assert updated is not None
    assert updated.name == "Trimmed"


# --- delete_wallet ---


@pytest.mark.asyncio
async def test_delete_wallet_success(wallet_service):
    """delete_wallet удаляет кошелёк и возвращает True."""
    created = await wallet_service.create_wallet("To Delete", VALID_MNEMONIC)
    deleted = await wallet_service.delete_wallet(created.id)
    assert deleted is True
    assert await wallet_service.get_wallet(created.id) is None
    assert len(await wallet_service.get_wallets()) == 0


@pytest.mark.asyncio
async def test_delete_wallet_not_found_returns_false(wallet_service):
    """delete_wallet с несуществующим id возвращает False."""
    deleted = await wallet_service.delete_wallet(99999)
    assert deleted is False


@pytest.mark.asyncio
async def test_delete_wallet_idempotent_second_call_returns_false(wallet_service):
    """Повторный delete_wallet того же id возвращает False (уже удалён)."""
    created = await wallet_service.create_wallet("W", VALID_MNEMONIC)
    first = await wallet_service.delete_wallet(created.id)
    second = await wallet_service.delete_wallet(created.id)
    assert first is True
    assert second is False
