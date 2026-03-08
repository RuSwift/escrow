"""
Tests for AdminService: password hashing, TRON validation, CRUD and business logic.
"""
import pytest

from db.models import AdminUser, AdminTronAddress
from services.admin import AdminService

# 34 chars, valid base58
TRON_ADDR = "T" + "1" * 33


@pytest.fixture
def admin_service(test_db, test_redis, test_settings) -> AdminService:
    return AdminService(session=test_db, redis=test_redis, settings=test_settings)


# --- Static helpers ---


def test_hash_password():
    """hash_password returns bcrypt hash."""
    h = AdminService.hash_password("secret123")
    assert h != "secret123"
    assert h.startswith("$2")


def test_verify_password():
    """verify_password validates against hash."""
    h = AdminService.hash_password("secret123")
    assert AdminService.verify_password("secret123", h) is True
    assert AdminService.verify_password("wrong", h) is False


def test_validate_tron_address():
    """validate_tron_address accepts T + 34 base58."""
    assert AdminService.validate_tron_address(TRON_ADDR) is True
    assert AdminService.validate_tron_address("") is False
    assert AdminService.validate_tron_address("0x123") is False
    assert AdminService.validate_tron_address("T" + "1" * 33) is True


# --- Admin ---


@pytest.mark.asyncio
async def test_get_admin_empty(admin_service):
    """get_admin returns None when no admin row."""
    assert await admin_service.get_admin() is None


@pytest.mark.asyncio
async def test_ensure_admin_exists_creates(admin_service):
    """ensure_admin_exists creates admin and commits."""
    admin = await admin_service.ensure_admin_exists()
    assert admin is not None
    assert admin.id == 1


@pytest.mark.asyncio
async def test_is_admin_configured_false_when_empty(admin_service):
    """is_admin_configured is False when no password and no TRON."""
    await admin_service.ensure_admin_exists()
    assert await admin_service.is_admin_configured() is False


@pytest.mark.asyncio
async def test_is_admin_configured_true_after_password(admin_service):
    """is_admin_configured is True after set_password."""
    await admin_service.set_password("admin", "password123")
    assert await admin_service.is_admin_configured() is True


@pytest.mark.asyncio
async def test_is_admin_configured_true_after_tron(admin_service):
    """is_admin_configured is True after add_tron_address."""
    await admin_service.ensure_admin_exists()
    await admin_service.add_tron_address(TRON_ADDR)
    assert await admin_service.is_admin_configured() is True


# --- Password ---


@pytest.mark.asyncio
async def test_set_password_success(admin_service):
    """set_password sets username and hash."""
    admin = await admin_service.set_password("admin", "password123")
    assert admin.username == "admin"
    assert admin.password_hash is not None


@pytest.mark.asyncio
async def test_set_password_validation(admin_service):
    """set_password raises on short username/password."""
    with pytest.raises(ValueError, match="at least 8 characters"):
        await admin_service.set_password("admin", "short")
    with pytest.raises(ValueError, match="at least 3 characters"):
        await admin_service.set_password("ab", "password123")


@pytest.mark.asyncio
async def test_verify_password_auth_ok(admin_service):
    """verify_password_auth returns admin when credentials valid."""
    await admin_service.set_password("admin", "password123")
    admin = await admin_service.verify_password_auth("admin", "password123")
    assert admin is not None
    assert admin.username == "admin"


@pytest.mark.asyncio
async def test_verify_password_auth_wrong(admin_service):
    """verify_password_auth returns None when wrong."""
    await admin_service.set_password("admin", "password123")
    assert await admin_service.verify_password_auth("admin", "wrong") is None
    assert await admin_service.verify_password_auth("other", "password123") is None


@pytest.mark.asyncio
async def test_change_password_success(admin_service):
    """change_password updates hash after verifying old."""
    await admin_service.set_password("admin", "oldpass123")
    await admin_service.change_password("oldpass123", "newpass123")
    assert await admin_service.verify_password_auth("admin", "newpass123") is not None
    assert await admin_service.verify_password_auth("admin", "oldpass123") is None


@pytest.mark.asyncio
async def test_change_password_wrong_old_raises(admin_service):
    """change_password raises when old password wrong."""
    await admin_service.set_password("admin", "pass12345")
    with pytest.raises(ValueError, match="Incorrect current password"):
        await admin_service.change_password("wrong", "newpass123")


@pytest.mark.asyncio
async def test_remove_password_raises_without_tron(admin_service):
    """remove_password raises when no TRON addresses."""
    await admin_service.set_password("admin", "pass12345")
    with pytest.raises(ValueError, match="no TRON addresses"):
        await admin_service.remove_password()


@pytest.mark.asyncio
async def test_remove_password_success(admin_service):
    """remove_password clears username/hash when TRON exists."""
    await admin_service.set_password("admin", "pass12345")
    await admin_service.add_tron_address(TRON_ADDR)
    await admin_service.remove_password()
    admin = await admin_service.get_admin()
    assert admin.username is None
    assert admin.password_hash is None


# --- TRON addresses ---


@pytest.mark.asyncio
async def test_add_tron_address_success(admin_service):
    """add_tron_address creates record."""
    addr = await admin_service.add_tron_address(TRON_ADDR, label="Test")
    assert isinstance(addr, AdminTronAddress)
    assert addr.tron_address == TRON_ADDR
    assert addr.label == "Test"


@pytest.mark.asyncio
async def test_add_tron_address_invalid_raises(admin_service):
    """add_tron_address raises on invalid format."""
    with pytest.raises(ValueError, match="Invalid TRON address"):
        await admin_service.add_tron_address("0x123")


@pytest.mark.asyncio
async def test_add_tron_address_duplicate_raises(admin_service):
    """add_tron_address raises when address already registered."""
    await admin_service.add_tron_address(TRON_ADDR)
    with pytest.raises(ValueError, match="already registered"):
        await admin_service.add_tron_address(TRON_ADDR)


@pytest.mark.asyncio
async def test_get_tron_addresses(admin_service):
    """get_tron_addresses returns list from repo."""
    await admin_service.add_tron_address(TRON_ADDR)
    addrs = await admin_service.get_tron_addresses()
    assert len(addrs) == 1
    assert addrs[0].tron_address == TRON_ADDR


@pytest.mark.asyncio
async def test_update_tron_address(admin_service):
    """update_tron_address updates label."""
    addr = await admin_service.add_tron_address(TRON_ADDR, label="Old")
    updated = await admin_service.update_tron_address(addr.id, new_label="New")
    assert updated.label == "New"


@pytest.mark.asyncio
async def test_toggle_tron_address(admin_service):
    """toggle_tron_address sets is_active."""
    addr = await admin_service.add_tron_address(TRON_ADDR)
    await admin_service.toggle_tron_address(addr.id, False)
    assert await admin_service.verify_tron_auth(TRON_ADDR) is False
    await admin_service.toggle_tron_address(addr.id, True)
    assert await admin_service.verify_tron_auth(TRON_ADDR) is True


@pytest.mark.asyncio
async def test_verify_tron_auth(admin_service):
    """verify_tron_auth returns True for whitelisted active address."""
    await admin_service.add_tron_address(TRON_ADDR)
    assert await admin_service.verify_tron_auth(TRON_ADDR) is True
    assert await admin_service.verify_tron_auth("T" + "2" * 33) is False


@pytest.mark.asyncio
async def test_delete_tron_address_last_raises(admin_service):
    """delete_tron_address raises when deleting last auth method."""
    addr = await admin_service.add_tron_address(TRON_ADDR)
    with pytest.raises(ValueError, match="last authentication method"):
        await admin_service.delete_tron_address(addr.id)


@pytest.mark.asyncio
async def test_delete_tron_address_ok_with_password(admin_service):
    """delete_tron_address succeeds when password is set."""
    await admin_service.set_password("admin", "pass12345")
    addr = await admin_service.add_tron_address(TRON_ADDR)
    await admin_service.delete_tron_address(addr.id)
    assert await admin_service.get_tron_addresses() == []


@pytest.mark.asyncio
async def test_delete_tron_address_ok_with_second_tron(admin_service):
    """delete_tron_address succeeds when another TRON exists."""
    a1 = await admin_service.add_tron_address(TRON_ADDR)
    a2 = await admin_service.add_tron_address("T" + "2" * 33)  # 34 chars base58
    await admin_service.delete_tron_address(a1.id)
    addrs = await admin_service.get_tron_addresses()
    assert len(addrs) == 1
    assert addrs[0].id == a2.id


# --- init_from_env ---


@pytest.mark.asyncio
async def test_init_from_env_not_configured(admin_service, test_settings):
    """init_from_env returns False when admin settings not configured."""
    assert await admin_service.init_from_env(test_settings.admin) is False


@pytest.mark.asyncio
async def test_init_from_env_password(admin_service, test_settings, monkeypatch):
    """init_from_env sets password when method=password."""
    monkeypatch.setenv("ADMIN_METHOD", "password")
    monkeypatch.setenv("ADMIN_USERNAME", "envadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "envpass123")
    from settings import Settings
    settings = Settings()
    result = await admin_service.init_from_env(settings.admin)
    assert result is True
    assert await admin_service.verify_password_auth("envadmin", "envpass123") is not None
