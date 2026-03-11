"""
Тесты ArbiterService (бизнес-логика: создание из мнемоники, переключение активного, удаление).
"""
import pytest

from services.arbiter import ArbiterService


VALID_MNEMONIC = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


@pytest.fixture
def arbiter_service(test_db, test_redis, test_settings) -> ArbiterService:
    """ArbiterService с тестовой сессией, Redis и настройками."""
    return ArbiterService(
        session=test_db, redis=test_redis, settings=test_settings
    )


# --- is_arbiter_initialized ---


@pytest.mark.asyncio
async def test_is_arbiter_initialized_empty(arbiter_service):
    """Без активного арбитра is_arbiter_initialized возвращает False."""
    assert await arbiter_service.is_arbiter_initialized() is False


@pytest.mark.asyncio
async def test_is_arbiter_initialized_after_create(arbiter_service):
    """После создания активного арбитра is_arbiter_initialized возвращает True."""
    await arbiter_service.create_arbiter_address("Root", VALID_MNEMONIC)
    assert await arbiter_service.is_arbiter_initialized() is True


# --- list_arbiter_addresses ---


@pytest.mark.asyncio
async def test_list_arbiter_addresses_empty(arbiter_service):
    """Без записей list_arbiter_addresses возвращает пустой список."""
    items = await arbiter_service.list_arbiter_addresses()
    assert items == []


@pytest.mark.asyncio
async def test_list_arbiter_addresses_after_create(arbiter_service):
    """После create list возвращает созданный адрес с is_active=True."""
    created = await arbiter_service.create_arbiter_address("A", VALID_MNEMONIC)
    items = await arbiter_service.list_arbiter_addresses()
    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].name == "A"
    assert items[0].is_active is True


# --- get_arbiter_address ---


@pytest.mark.asyncio
async def test_get_arbiter_address_not_found(arbiter_service):
    """get_arbiter_address с несуществующим id возвращает None."""
    assert await arbiter_service.get_arbiter_address(99999) is None


@pytest.mark.asyncio
async def test_get_arbiter_address_after_create(arbiter_service):
    """get_arbiter_address возвращает созданный адрес."""
    created = await arbiter_service.create_arbiter_address("A", VALID_MNEMONIC)
    found = await arbiter_service.get_arbiter_address(created.id)
    assert found is not None
    assert found.id == created.id
    assert found.name == "A"


# --- create_arbiter_address ---


@pytest.mark.asyncio
async def test_create_arbiter_address_success(arbiter_service):
    """create_arbiter_address создаёт адрес с is_active=True."""
    out = await arbiter_service.create_arbiter_address("Root", VALID_MNEMONIC)
    assert out.id >= 1
    assert out.name == "Root"
    assert out.tron_address
    assert out.tron_address.startswith("T")
    assert out.ethereum_address
    assert out.ethereum_address.startswith("0x")
    assert out.is_active is True


@pytest.mark.asyncio
async def test_create_arbiter_address_demotes_current_active(arbiter_service):
    """При создании второго арбитра первый переводится в резерв."""
    first = await arbiter_service.create_arbiter_address("First", VALID_MNEMONIC)
    other_mnemonic = "legal winner thank year wave sausage worth useful legal winner thank yellow"
    second = await arbiter_service.create_arbiter_address("Second", other_mnemonic)
    items = await arbiter_service.list_arbiter_addresses()
    assert len(items) == 2
    by_id = {a.id: a for a in items}
    assert by_id[first.id].is_active is False
    assert by_id[second.id].is_active is True


@pytest.mark.asyncio
async def test_create_arbiter_address_duplicate_addresses_raises(arbiter_service):
    """Повторное создание с той же мнемоникой (те же адреса) поднимает ValueError."""
    await arbiter_service.create_arbiter_address("First", VALID_MNEMONIC)
    with pytest.raises(ValueError, match="addresses already exist"):
        await arbiter_service.create_arbiter_address("Second", VALID_MNEMONIC)


@pytest.mark.asyncio
async def test_create_arbiter_address_empty_name_raises(arbiter_service):
    """Пустое имя поднимает ValueError."""
    with pytest.raises(ValueError, match="name is required"):
        await arbiter_service.create_arbiter_address("", VALID_MNEMONIC)
    with pytest.raises(ValueError, match="name is required"):
        await arbiter_service.create_arbiter_address("   ", VALID_MNEMONIC)


@pytest.mark.asyncio
async def test_create_arbiter_address_empty_mnemonic_raises(arbiter_service):
    """Пустая мнемоника поднимает ValueError."""
    with pytest.raises(ValueError, match="Mnemonic phrase is required"):
        await arbiter_service.create_arbiter_address("W", "")
    with pytest.raises(ValueError, match="Mnemonic phrase is required"):
        await arbiter_service.create_arbiter_address("W", "   ")


@pytest.mark.asyncio
async def test_create_arbiter_address_invalid_mnemonic_raises(arbiter_service):
    """Невалидная мнемоника поднимает ValueError."""
    with pytest.raises(ValueError, match="Invalid mnemonic"):
        await arbiter_service.create_arbiter_address("W", "not valid mnemonic words here")


# --- update_arbiter_name ---


@pytest.mark.asyncio
async def test_update_arbiter_name_success(arbiter_service):
    """update_arbiter_name обновляет имя и возвращает Get."""
    created = await arbiter_service.create_arbiter_address("Old", VALID_MNEMONIC)
    updated = await arbiter_service.update_arbiter_name(created.id, "New")
    assert updated is not None
    assert updated.name == "New"
    assert updated.id == created.id


@pytest.mark.asyncio
async def test_update_arbiter_name_not_found_returns_none(arbiter_service):
    """update_arbiter_name с несуществующим id возвращает None."""
    assert await arbiter_service.update_arbiter_name(99999, "Any") is None


@pytest.mark.asyncio
async def test_update_arbiter_name_empty_raises(arbiter_service):
    """Пустое имя поднимает ValueError."""
    created = await arbiter_service.create_arbiter_address("A", VALID_MNEMONIC)
    with pytest.raises(ValueError, match="name is required"):
        await arbiter_service.update_arbiter_name(created.id, "   ")


# --- switch_active_arbiter ---


@pytest.mark.asyncio
async def test_switch_active_arbiter_success(arbiter_service):
    """switch_active_arbiter переводит резервный в активный, активный в резервный."""
    first = await arbiter_service.create_arbiter_address("First", VALID_MNEMONIC)
    other_mnemonic = "legal winner thank year wave sausage worth useful legal winner thank yellow"
    second = await arbiter_service.create_arbiter_address("Second", other_mnemonic)
    # second is now active, first is backup
    out = await arbiter_service.switch_active_arbiter(first.id)
    assert out is not None
    assert out.id == first.id
    assert out.is_active is True
    items = await arbiter_service.list_arbiter_addresses()
    by_id = {a.id: a for a in items}
    assert by_id[first.id].is_active is True
    assert by_id[second.id].is_active is False


@pytest.mark.asyncio
async def test_switch_active_arbiter_not_found_raises(arbiter_service):
    """switch_active_arbiter с несуществующим id поднимает ValueError."""
    await arbiter_service.create_arbiter_address("Only", VALID_MNEMONIC)
    with pytest.raises(ValueError, match="not found"):
        await arbiter_service.switch_active_arbiter(99999)


@pytest.mark.asyncio
async def test_switch_active_arbiter_already_active_raises(arbiter_service):
    """switch_active_arbiter для уже активного поднимает ValueError."""
    created = await arbiter_service.create_arbiter_address("Active", VALID_MNEMONIC)
    with pytest.raises(ValueError, match="already active"):
        await arbiter_service.switch_active_arbiter(created.id)


# --- delete_arbiter_address ---


@pytest.mark.asyncio
async def test_delete_arbiter_address_backup_success(arbiter_service):
    """delete_arbiter_address удаляет резервный адрес и возвращает True."""
    first = await arbiter_service.create_arbiter_address("Active", VALID_MNEMONIC)
    other_mnemonic = "legal winner thank year wave sausage worth useful legal winner thank yellow"
    second = await arbiter_service.create_arbiter_address("Backup", other_mnemonic)
    # second is active, first is backup; switch so first is active, second is backup
    await arbiter_service.switch_active_arbiter(first.id)
    deleted = await arbiter_service.delete_arbiter_address(second.id)
    assert deleted is True
    assert await arbiter_service.get_arbiter_address(second.id) is None


@pytest.mark.asyncio
async def test_delete_arbiter_address_active_raises(arbiter_service):
    """Удаление активного арбитра поднимает ValueError."""
    created = await arbiter_service.create_arbiter_address("Active", VALID_MNEMONIC)
    with pytest.raises(ValueError, match="Cannot delete active"):
        await arbiter_service.delete_arbiter_address(created.id)


@pytest.mark.asyncio
async def test_delete_arbiter_address_not_found_returns_false(arbiter_service):
    """delete_arbiter_address с несуществующим id возвращает False."""
    assert await arbiter_service.delete_arbiter_address(99999) is False
