"""
Tests for AdminRepository (admin user) and AdminTronAddressRepository (TRON addresses).
"""
import pytest

from db.models import AdminUser, AdminTronAddress
from repos.admin import AdminRepository, AdminTronAddressRepository, ADMIN_USER_ID


@pytest.fixture
def admin_repo(test_db, test_redis, test_settings) -> AdminRepository:
    return AdminRepository(
        session=test_db,
        redis=test_redis,
        settings=test_settings,
    )


@pytest.fixture
def tron_repo(test_db, test_redis, test_settings) -> AdminTronAddressRepository:
    return AdminTronAddressRepository(
        session=test_db,
        redis=test_redis,
        settings=test_settings,
    )


# --- AdminUser ---


@pytest.mark.asyncio
async def test_get_empty(admin_repo):
    """get() returns None when no admin row."""
    assert await admin_repo.get() is None


@pytest.mark.asyncio
async def test_create_admin(admin_repo):
    """create() creates admin row (id=1)."""
    admin = await admin_repo.create()
    assert isinstance(admin, AdminUser)
    assert admin.id == ADMIN_USER_ID
    assert admin.username is None
    assert admin.password_hash is None


@pytest.mark.asyncio
async def test_get_after_create(admin_repo):
    """get() returns admin after create()."""
    await admin_repo.create()
    admin = await admin_repo.get()
    assert admin is not None
    assert admin.id == ADMIN_USER_ID


@pytest.mark.asyncio
async def test_patch_admin(admin_repo):
    """patch() updates admin credentials."""
    await admin_repo.create()
    await admin_repo.patch(username="admin", password_hash="hashed")
    admin = await admin_repo.get()
    assert admin is not None
    assert admin.username == "admin"
    assert admin.password_hash == "hashed"


@pytest.mark.asyncio
async def test_delete_admin(admin_repo):
    """delete() removes admin row."""
    await admin_repo.create()
    await admin_repo.delete()
    assert await admin_repo.get() is None


# --- AdminTronAddressRepository ---

# 34 chars, valid base58 (T + 33 chars from base58 alphabet)
TRON_ADDR = "T" + "1" * 33


@pytest.mark.asyncio
async def test_list_empty(tron_repo):
    """list() returns [] when no addresses."""
    assert await tron_repo.list() == []
    assert await tron_repo.list(active_only=False) == []


@pytest.mark.asyncio
async def test_create_tron(tron_repo):
    """create(tron_address, ...) creates TRON address record."""
    addr = await tron_repo.create(tron_address=TRON_ADDR, label="Test")
    assert isinstance(addr, AdminTronAddress)
    assert addr.tron_address == TRON_ADDR
    assert addr.label == "Test"
    assert addr.is_active is True


@pytest.mark.asyncio
async def test_get_by_id(tron_repo):
    """get(id) returns record by id."""
    addr = await tron_repo.create(tron_address=TRON_ADDR)
    assert addr.id
    found = await tron_repo.get(addr.id)
    assert found is not None
    assert found.id == addr.id
    assert found.tron_address == TRON_ADDR


@pytest.mark.asyncio
async def test_get_by_id_missing(tron_repo):
    """get(id) returns None for missing id."""
    assert await tron_repo.get(999) is None


@pytest.mark.asyncio
async def test_get_by_address(tron_repo):
    """get_by_address returns record by tron_address."""
    await tron_repo.create(tron_address=TRON_ADDR)
    found = await tron_repo.get_by_address(TRON_ADDR)
    assert found is not None
    assert found.tron_address == TRON_ADDR


@pytest.mark.asyncio
async def test_get_by_address_missing(tron_repo):
    """get_by_address returns None for unknown address."""
    assert await tron_repo.get_by_address(TRON_ADDR) is None


@pytest.mark.asyncio
async def test_list_after_create(tron_repo):
    """list() returns created addresses ordered by created_at desc."""
    await tron_repo.create(tron_address=TRON_ADDR, label="A")
    addrs = await tron_repo.list()
    assert len(addrs) == 1
    assert addrs[0].tron_address == TRON_ADDR


@pytest.mark.asyncio
async def test_patch_tron(tron_repo):
    """patch(id, **values) updates TRON address."""
    addr = await tron_repo.create(tron_address=TRON_ADDR, label="Old")
    await tron_repo.patch(addr.id, label="New", is_active=False)
    await tron_repo._session.refresh(addr)
    assert addr.label == "New"
    assert addr.is_active is False


@pytest.mark.asyncio
async def test_delete_tron(tron_repo):
    """delete(id) removes TRON address."""
    addr = await tron_repo.create(tron_address=TRON_ADDR)
    await tron_repo.delete(addr.id)
    assert await tron_repo.get(addr.id) is None


@pytest.mark.asyncio
async def test_delete_all(tron_repo):
    """delete_all() removes all TRON addresses."""
    await tron_repo.create(tron_address=TRON_ADDR)
    await tron_repo.create(tron_address="T" + "2" * 33)  # 34 chars base58
    await tron_repo.delete_all()
    assert await tron_repo.list() == []
