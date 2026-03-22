"""
Тесты ArbiterRepository и ArbiterResource (CRUD по Wallet с role arbiter/arbiter-backup).
"""
import pytest
from pydantic import ValidationError

from db.models import Wallet
from repos.arbiter import (
    ArbiterResource,
    ArbiterRepository,
)


@pytest.fixture
def arbiter_repo(test_db, test_redis, test_settings) -> ArbiterRepository:
    """ArbiterRepository с тестовой сессией и настройками."""
    return ArbiterRepository(
        session=test_db, redis=test_redis, settings=test_settings
    )


# --- ArbiterResource.Create ---


def test_arbiter_resource_create_required_fields():
    """Create принимает name, encrypted_mnemonic, tron_address, ethereum_address, is_active."""
    data = ArbiterResource.Create(
        name="Root",
        encrypted_mnemonic="enc",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        is_active=True,
    )
    assert data.name == "Root"
    assert data.is_active is True


def test_arbiter_resource_create_empty_mnemonic_raises():
    """Create с пустым encrypted_mnemonic — ValidationError."""
    with pytest.raises(ValidationError):
        ArbiterResource.Create(
            name="X",
            encrypted_mnemonic="  ",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=True,
        )


def test_arbiter_resource_create_is_active_false():
    """Create с is_active=False маппится в role=arbiter-backup при записи."""
    data = ArbiterResource.Create(
        name="Backup",
        encrypted_mnemonic="enc",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        is_active=False,
    )
    assert data.is_active is False


# --- list ---


@pytest.mark.asyncio
async def test_list_empty(arbiter_repo):
    """Без записей list возвращает пустой список."""
    items = await arbiter_repo.list()
    assert items == []


@pytest.mark.asyncio
async def test_list_after_create(arbiter_repo):
    """list возвращает созданные записи с is_active по маппингу role."""
    created = await arbiter_repo.create(
        ArbiterResource.Create(
            name="Active",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=True,
        )
    )
    items = await arbiter_repo.list()
    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].name == "Active"
    assert items[0].is_active is True


@pytest.mark.asyncio
async def test_list_ignores_operation_wallets(arbiter_repo, test_db):
    """list не возвращает кошельки с role=None (операционные)."""
    op_wallet = Wallet(
        name="Ops",
        encrypted_mnemonic="enc",
        tron_address="TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ9eRt",
        ethereum_address="0x1234567890123456789012345678901234567890",
        role=None,
    )
    test_db.add(op_wallet)
    await test_db.flush()
    items = await arbiter_repo.list()
    assert len(items) == 0


# --- get ---


@pytest.mark.asyncio
async def test_get_not_found(arbiter_repo):
    """get с несуществующим id возвращает None."""
    assert await arbiter_repo.get(99999) is None


@pytest.mark.asyncio
async def test_get_returns_created(arbiter_repo):
    """get возвращает созданную запись с is_active."""
    created = await arbiter_repo.create(
        ArbiterResource.Create(
            name="A",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=False,
        )
    )
    found = await arbiter_repo.get(created.id)
    assert found is not None
    assert found.id == created.id
    assert found.is_active is False


# --- get_active ---


@pytest.mark.asyncio
async def test_get_active_empty(arbiter_repo):
    """get_active без записей с role=arbiter возвращает None."""
    await arbiter_repo.create(
        ArbiterResource.Create(
            name="Backup",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=False,
        )
    )
    assert await arbiter_repo.get_active() is None


@pytest.mark.asyncio
async def test_get_active_returns_active(arbiter_repo):
    """get_active возвращает запись с role=arbiter (is_active=True)."""
    created = await arbiter_repo.create(
        ArbiterResource.Create(
            name="Active",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=True,
        )
    )
    active = await arbiter_repo.get_active()
    assert active is not None
    assert active.id == created.id
    assert active.is_active is True


# --- create ---


@pytest.mark.asyncio
async def test_create_returns_get_with_id(arbiter_repo):
    """create сохраняет и возвращает Get с id и is_active."""
    out = await arbiter_repo.create(
        ArbiterResource.Create(
            name="New",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=True,
        )
    )
    assert out.id >= 1
    assert out.name == "New"
    assert out.is_active is True
    assert out.created_at is not None
    assert out.updated_at is not None


# --- patch ---


@pytest.mark.asyncio
async def test_patch_name_success(arbiter_repo):
    """patch обновляет name и возвращает Get."""
    created = await arbiter_repo.create(
        ArbiterResource.Create(
            name="Old",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=True,
        )
    )
    updated = await arbiter_repo.patch(
        created.id, ArbiterResource.Patch(name="New")
    )
    assert updated is not None
    assert updated.name == "New"
    assert updated.id == created.id


@pytest.mark.asyncio
async def test_patch_is_active_switches_role(arbiter_repo):
    """patch(is_active=False) переводит role в arbiter-backup."""
    created = await arbiter_repo.create(
        ArbiterResource.Create(
            name="A",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=True,
        )
    )
    updated = await arbiter_repo.patch(
        created.id, ArbiterResource.Patch(is_active=False)
    )
    assert updated is not None
    assert updated.is_active is False
    active = await arbiter_repo.get_active()
    assert active is None


@pytest.mark.asyncio
async def test_patch_not_found_returns_none(arbiter_repo):
    """patch с id не из арбитров возвращает None."""
    result = await arbiter_repo.patch(
        99999, ArbiterResource.Patch(name="X")
    )
    assert result is None


# --- delete ---


@pytest.mark.asyncio
async def test_delete_success(arbiter_repo):
    """delete удаляет запись и возвращает True."""
    created = await arbiter_repo.create(
        ArbiterResource.Create(
            name="ToDelete",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=False,
        )
    )
    deleted = await arbiter_repo.delete(created.id)
    assert deleted is True
    assert await arbiter_repo.get(created.id) is None


@pytest.mark.asyncio
async def test_delete_not_found_returns_false(arbiter_repo):
    """delete с несуществующим id возвращает False."""
    assert await arbiter_repo.delete(99999) is False


@pytest.mark.asyncio
async def test_delete_ignores_operation_wallet(arbiter_repo, test_db):
    """delete не удаляет кошелёк с role=None (только arbiter/arbiter-backup)."""
    op_wallet = Wallet(
        name="Ops",
        encrypted_mnemonic="enc",
        tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
        role=None,
    )
    test_db.add(op_wallet)
    await test_db.flush()
    deleted = await arbiter_repo.delete(op_wallet.id)
    assert deleted is False
    await test_db.refresh(op_wallet)
    assert op_wallet.id is not None


# --- exists_with_addresses ---


@pytest.mark.asyncio
async def test_exists_with_addresses_empty(arbiter_repo):
    """Без арбитров exists_with_addresses возвращает False."""
    assert await arbiter_repo.exists_with_addresses(
        "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        "0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
    ) is False


@pytest.mark.asyncio
async def test_exists_with_addresses_after_create(arbiter_repo):
    """После create с данными адресами exists возвращает True."""
    await arbiter_repo.create(
        ArbiterResource.Create(
            name="W",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=True,
        )
    )
    assert await arbiter_repo.exists_with_addresses(
        "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
        "0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
    ) is True


@pytest.mark.asyncio
async def test_exists_with_addresses_other_returns_false(arbiter_repo):
    """exists с другими адресами возвращает False."""
    await arbiter_repo.create(
        ArbiterResource.Create(
            name="W",
            encrypted_mnemonic="enc",
            tron_address="TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH",
            ethereum_address="0x9858EfFD232B4033E47d90003D41EC34EcaEda94",
            is_active=True,
        )
    )
    assert await arbiter_repo.exists_with_addresses(
        "TLrJJKGK4aNTq5A6bM7nQ8sV2wXyZ9eRt",
        "0x1234567890123456789012345678901234567890",
    ) is False
