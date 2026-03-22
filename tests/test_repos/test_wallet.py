"""
Тесты WalletRepository и WalletResource на реальной БД.
"""
import pytest
from pydantic import ValidationError

from db.models import Wallet
from repos.wallet import (
    ExchangeWalletResource,
    WalletResource,
    WalletRepository,
    _model_to_get,
)


@pytest.fixture
def wallet_repo(test_db, test_redis, test_settings) -> WalletRepository:
    """WalletRepository с тестовой сессией и настройками."""
    return WalletRepository(
        session=test_db, redis=test_redis, settings=test_settings
    )


# --- WalletResource.Create ---


def test_wallet_resource_create_required_fields():
    """Create принимает name, encrypted_mnemonic, tron_address, ethereum_address."""
    data = WalletResource.Create(
        name="Test Wallet",
        encrypted_mnemonic="base64encrypted",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
    )
    assert data.name == "Test Wallet"
    assert data.tron_address.startswith("T")
    assert data.ethereum_address.startswith("0x")


def test_wallet_resource_create_missing_field_raises():
    """Create без обязательного поля поднимает ValidationError."""
    with pytest.raises(ValidationError):
        WalletResource.Create(
            name="W",
            encrypted_mnemonic="x",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            # ethereum_address missing
        )


def test_wallet_resource_create_external_allows_empty_mnemonic():
    """role=external: encrypted_mnemonic может быть пустым."""
    data = WalletResource.Create(
        name="Ext",
        role="external",
        encrypted_mnemonic=None,
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
    )
    assert data.role == "external"
    assert data.encrypted_mnemonic is None


def test_wallet_resource_create_multisig_requires_mnemonic():
    """role=multisig: без мнемоники — ValidationError."""
    with pytest.raises(ValidationError):
        WalletResource.Create(
            name="Ms",
            role="multisig",
            encrypted_mnemonic=None,
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )


def test_wallet_resource_create_operation_requires_mnemonic():
    """Операционный (role None): мнемоника обязательна."""
    with pytest.raises(ValidationError):
        WalletResource.Create(
            name="Op",
            encrypted_mnemonic=None,
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )


def test_wallet_resource_patch_empty_mnemonic_only_with_external():
    """Patch: пустой encrypted_mnemonic только вместе с role=external."""
    WalletResource.Patch(encrypted_mnemonic=None, role="external")
    with pytest.raises(ValidationError):
        WalletResource.Patch(encrypted_mnemonic=None, role="multisig")


# --- list_operation_wallets ---


@pytest.mark.asyncio
async def test_list_operation_wallets_empty(wallet_repo):
    """Без записей list_operation_wallets возвращает пустой список."""
    wallets = await wallet_repo.list_operation_wallets()
    assert wallets == []


@pytest.mark.asyncio
async def test_list_operation_wallets_only_role_none(wallet_repo, test_db):
    """list_operation_wallets возвращает только кошельки с role=None."""
    # Кошелёк с role=None через репозиторий
    w1 = await wallet_repo.create(
        WalletResource.Create(
            name="Ops",
            encrypted_mnemonic="enc1",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )
    )
    # Кошелёк с role=arbiter напрямую в БД
    model_with_role = Wallet(
        name="Arbiter",
        encrypted_mnemonic="enc2",
        tron_address="TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ9eRt",
        ethereum_address="0x1234567890123456789012345678901234567890",
        role="arbiter",
    )
    test_db.add(model_with_role)
    await test_db.flush()

    wallets = await wallet_repo.list_operation_wallets()
    assert len(wallets) == 1
    assert wallets[0].id == w1.id
    assert wallets[0].name == "Ops"


# --- get_operation_wallet ---


@pytest.mark.asyncio
async def test_get_operation_wallet_not_found(wallet_repo):
    """get_operation_wallet с несуществующим id возвращает None."""
    assert await wallet_repo.get_operation_wallet(99999) is None


@pytest.mark.asyncio
async def test_get_operation_wallet_returns_created(wallet_repo):
    """get_operation_wallet возвращает созданный через create кошелёк."""
    created = await wallet_repo.create(
        WalletResource.Create(
            name="W1",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )
    )
    found = await wallet_repo.get_operation_wallet(created.id)
    assert found is not None
    assert found.id == created.id
    assert found.name == "W1"
    assert found.tron_address == created.tron_address


@pytest.mark.asyncio
async def test_get_operation_wallet_ignores_wallet_with_role(wallet_repo, test_db):
    """get_operation_wallet не возвращает кошелёк с role!=None."""
    model_with_role = Wallet(
        name="Arbiter",
        encrypted_mnemonic="enc",
        tron_address="TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ9eRt",
        ethereum_address="0x1234567890123456789012345678901234567890",
        role="arbiter",
    )
    test_db.add(model_with_role)
    await test_db.flush()
    await test_db.refresh(model_with_role)

    found = await wallet_repo.get_operation_wallet(model_with_role.id)
    assert found is None


# --- create ---


@pytest.mark.asyncio
async def test_create_returns_get_with_id(wallet_repo):
    """create сохраняет кошелёк и возвращает Get с id."""
    out = await wallet_repo.create(
        WalletResource.Create(
            name="New",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )
    )
    assert out.id >= 1
    assert out.name == "New"
    assert out.tron_address == "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
    assert out.ethereum_address == "0x9858EfFD232B4033E47d90003D41EC34EcaEda94"
    assert out.created_at is not None
    assert out.updated_at is not None


# --- update_name ---


@pytest.mark.asyncio
async def test_update_name_success(wallet_repo):
    """update_name обновляет имя и возвращает Get."""
    created = await wallet_repo.create(
        WalletResource.Create(
            name="Old",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )
    )
    updated = await wallet_repo.update_name(created.id, "New")
    assert updated is not None
    assert updated.name == "New"
    assert updated.id == created.id


@pytest.mark.asyncio
async def test_update_name_not_found_returns_none(wallet_repo):
    """update_name с несуществующим id возвращает None."""
    assert await wallet_repo.update_name(99999, "Any") is None


# --- delete_operation_wallet ---


@pytest.mark.asyncio
async def test_delete_operation_wallet_success(wallet_repo):
    """delete_operation_wallet удаляет запись и возвращает True."""
    created = await wallet_repo.create(
        WalletResource.Create(
            name="ToDelete",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )
    )
    deleted = await wallet_repo.delete_operation_wallet(created.id)
    assert deleted is True
    assert await wallet_repo.get_operation_wallet(created.id) is None


@pytest.mark.asyncio
async def test_delete_operation_wallet_not_found_returns_false(wallet_repo):
    """delete_operation_wallet с несуществующим id возвращает False."""
    assert await wallet_repo.delete_operation_wallet(99999) is False


# --- exists_operation_wallet_with_addresses ---


@pytest.mark.asyncio
async def test_exists_operation_wallet_with_addresses_empty(wallet_repo):
    """Без кошельков exists возвращает False."""
    assert await wallet_repo.exists_operation_wallet_with_addresses(
        "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        "0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
    ) is False


@pytest.mark.asyncio
async def test_exists_operation_wallet_with_addresses_after_create(wallet_repo):
    """После create с данными адресами exists возвращает True для этих адресов."""
    await wallet_repo.create(
        WalletResource.Create(
            name="W",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )
    )
    assert await wallet_repo.exists_operation_wallet_with_addresses(
        "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        "0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
    ) is True


@pytest.mark.asyncio
async def test_exists_operation_wallet_with_addresses_other_returns_false(wallet_repo):
    """exists с другими адресами возвращает False."""
    await wallet_repo.create(
        WalletResource.Create(
            name="W",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        )
    )
    assert await wallet_repo.exists_operation_wallet_with_addresses(
        "TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ9eRt",
        "0x1234567890123456789012345678901234567890",
    ) is False


# --- exchange wallets (external / multisig) ---


@pytest.mark.asyncio
async def test_create_exchange_wallet_external_list_get_patch_delete(wallet_repo):
    """create_exchange_wallet, list, get, patch, delete для owner_did."""
    owner = "did:example:exchange_owner"
    created = await wallet_repo.create_exchange_wallet(
        WalletResource.Create(
            name="Bank",
            role="external",
            encrypted_mnemonic=None,
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        ),
        owner_did=owner,
    )
    assert isinstance(created, ExchangeWalletResource.Get)
    assert created.role == "external"

    listed = await wallet_repo.list_exchange_wallets(owner)
    assert len(listed) == 1
    got = await wallet_repo.get_exchange_wallet(created.id, owner)
    assert got is not None
    assert got.name == "Bank"

    patched = await wallet_repo.patch_exchange_wallet(
        created.id,
        owner,
        WalletResource.Patch(name="Bank2"),
    )
    assert patched is not None
    assert patched.name == "Bank2"

    assert await wallet_repo.delete_exchange_wallet(created.id, owner) is True
    assert await wallet_repo.get_exchange_wallet(created.id, owner) is None


@pytest.mark.asyncio
async def test_create_exchange_wallet_wrong_role_raises(wallet_repo):
    """create_exchange_wallet принимает только external | multisig."""
    with pytest.raises(ValueError, match="external"):
        await wallet_repo.create_exchange_wallet(
            WalletResource.Create(
                name="Bad",
                role=None,
                encrypted_mnemonic="enc",
                tron_address="TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ9eRt",
                ethereum_address="0x1234567890123456789012345678901234567890",
            ),
            owner_did="did:x",
        )
