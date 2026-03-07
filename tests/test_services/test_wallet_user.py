"""
Тесты WalletUserService на реальной БД и Redis (fixtures из tests/conftest.py).
"""
import pytest

from services.wallet_user import WalletUserService


@pytest.fixture
def wallet_user_service(test_db, test_redis, test_settings) -> WalletUserService:
    """WalletUserService с тестовой сессией, Redis и настройками."""
    return WalletUserService(
        session=test_db, redis=test_redis, settings=test_settings
    )


WALLET_TRON = "TXyz123456789012345678901234567890AB"
WALLET_ETH = "0x1234567890123456789012345678901234567890"


# --- get_by_wallet_address ---


@pytest.mark.asyncio
async def test_get_by_wallet_address_empty_returns_none(wallet_user_service):
    """Без пользователей get_by_wallet_address возвращает None."""
    assert await wallet_user_service.get_by_wallet_address(WALLET_TRON) is None


@pytest.mark.asyncio
async def test_get_by_wallet_address_after_create_returns_user(
    wallet_user_service,
):
    """После create_user get_by_wallet_address возвращает созданного пользователя."""
    created = await wallet_user_service.create_user(
        WALLET_TRON, "tron", "alice"
    )
    found = await wallet_user_service.get_by_wallet_address(WALLET_TRON)
    assert found is not None
    assert found.id == created.id
    assert found.wallet_address == WALLET_TRON
    assert found.nickname == "alice"


# --- get_by_nickname ---


@pytest.mark.asyncio
async def test_get_by_nickname_empty_returns_none(wallet_user_service):
    """Без пользователей get_by_nickname возвращает None."""
    assert await wallet_user_service.get_by_nickname("alice") is None


@pytest.mark.asyncio
async def test_get_by_nickname_after_create_returns_user(wallet_user_service):
    """После create_user get_by_nickname возвращает пользователя."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "bob")
    found = await wallet_user_service.get_by_nickname("bob")
    assert found is not None
    assert found.nickname == "bob"


# --- get_by_id ---


@pytest.mark.asyncio
async def test_get_by_id_empty_returns_none(wallet_user_service):
    """get_by_id(1) без записей возвращает None."""
    assert await wallet_user_service.get_by_id(1) is None


@pytest.mark.asyncio
async def test_get_by_id_after_create_returns_user(wallet_user_service):
    """После create_user get_by_id возвращает пользователя."""
    created = await wallet_user_service.create_user(
        WALLET_TRON, "tron", "alice"
    )
    found = await wallet_user_service.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


# --- create_user ---


@pytest.mark.asyncio
async def test_create_user_success(wallet_user_service):
    """create_user создаёт пользователя и возвращает Get с id, did, nickname."""
    out = await wallet_user_service.create_user(
        WALLET_TRON, "tron", "alice"
    )
    assert out.id >= 1
    assert out.wallet_address == WALLET_TRON
    assert out.blockchain == "tron"
    assert out.nickname == "alice"
    assert out.did
    assert "ruswift" in out.did or "tron" in out.did.lower()
    assert out.avatar is None
    assert out.access_to_admin_panel is False
    assert out.is_verified is False


@pytest.mark.asyncio
async def test_create_user_with_optional_fields(wallet_user_service):
    """create_user с avatar, access_to_admin_panel, is_verified сохраняет их."""
    out = await wallet_user_service.create_user(
        WALLET_ETH,
        "ethereum",
        "bob",
        avatar="data:image/png;base64,abc",
        access_to_admin_panel=True,
        is_verified=True,
    )
    assert out.avatar == "data:image/png;base64,abc"
    assert out.access_to_admin_panel is True
    assert out.is_verified is True


@pytest.mark.asyncio
async def test_create_user_duplicate_wallet_raises(wallet_user_service):
    """Повторное создание с тем же wallet_address поднимает ValueError."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    with pytest.raises(ValueError, match="already exists"):
        await wallet_user_service.create_user(
            WALLET_TRON, "tron", "alice2"
        )


@pytest.mark.asyncio
async def test_create_user_empty_nickname_raises(wallet_user_service):
    """create_user с пустым nickname поднимает ValueError."""
    with pytest.raises(ValueError, match="Nickname cannot be empty"):
        await wallet_user_service.create_user(
            WALLET_TRON, "tron", "   "
        )


@pytest.mark.asyncio
async def test_create_user_nickname_too_long_raises(wallet_user_service):
    """create_user с nickname длиннее 100 поднимает ValueError."""
    with pytest.raises(ValueError, match="cannot exceed 100"):
        await wallet_user_service.create_user(
            WALLET_TRON, "tron", "a" * 101
        )


@pytest.mark.asyncio
async def test_create_user_invalid_blockchain_raises(wallet_user_service):
    """create_user с недопустимым blockchain поднимает ValueError."""
    with pytest.raises(ValueError, match="Invalid blockchain"):
        await wallet_user_service.create_user(
            WALLET_TRON, "bitcoin", "alice"
        )


@pytest.mark.asyncio
async def test_create_user_blockchain_normalized_to_lowercase(wallet_user_service):
    """create_user принимает blockchain в любом регистре (tron/TRON)."""
    out = await wallet_user_service.create_user(
        WALLET_TRON, "TRON", "alice"
    )
    assert out.blockchain == "tron"


# --- update_nickname ---


@pytest.mark.asyncio
async def test_update_nickname_success(wallet_user_service):
    """update_nickname обновляет никнейм и возвращает обновлённого пользователя."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    updated = await wallet_user_service.update_nickname(
        WALLET_TRON, "alice_new"
    )
    assert updated.nickname == "alice_new"
    assert (await wallet_user_service.get_by_nickname("alice_new")) is not None
    assert (await wallet_user_service.get_by_nickname("alice")) is None


@pytest.mark.asyncio
async def test_update_nickname_user_not_found_raises(wallet_user_service):
    """update_nickname при неизвестном адресе поднимает ValueError."""
    with pytest.raises(ValueError, match="User not found"):
        await wallet_user_service.update_nickname(
            WALLET_TRON, "newnick"
        )


@pytest.mark.asyncio
async def test_update_nickname_empty_raises(wallet_user_service):
    """update_nickname с пустым никнеймом поднимает ValueError."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    with pytest.raises(ValueError, match="Nickname cannot be empty"):
        await wallet_user_service.update_nickname(WALLET_TRON, "   ")


@pytest.mark.asyncio
async def test_update_nickname_taken_by_another_raises(wallet_user_service):
    """update_nickname на уже занятый другим пользователем никнейм поднимает ValueError."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    await wallet_user_service.create_user(WALLET_ETH, "ethereum", "bob")
    with pytest.raises(ValueError, match="already taken"):
        await wallet_user_service.update_nickname(WALLET_TRON, "bob")


@pytest.mark.asyncio
async def test_update_nickname_same_user_ok(wallet_user_service):
    """update_nickname на тот же никнейм (тот же пользователь) допустим."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    updated = await wallet_user_service.update_nickname(WALLET_TRON, "alice")
    assert updated.nickname == "alice"


# --- update_profile ---


@pytest.mark.asyncio
async def test_update_profile_nickname_only(wallet_user_service):
    """update_profile только nickname обновляет никнейм."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    updated = await wallet_user_service.update_profile(
        WALLET_TRON, nickname="alice_v2"
    )
    assert updated.nickname == "alice_v2"


@pytest.mark.asyncio
async def test_update_profile_avatar_only(wallet_user_service):
    """update_profile только avatar обновляет аватар."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    updated = await wallet_user_service.update_profile(
        WALLET_TRON, avatar="data:image/png;base64,xyz"
    )
    assert updated.avatar == "data:image/png;base64,xyz"


@pytest.mark.asyncio
async def test_update_profile_clear_avatar(wallet_user_service):
    """update_profile с avatar='' очищает аватар."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    await wallet_user_service.update_profile(
        WALLET_TRON, avatar="data:image/png;base64,old"
    )
    updated = await wallet_user_service.update_profile(
        WALLET_TRON, avatar=""
    )
    assert updated.avatar is None


@pytest.mark.asyncio
async def test_update_profile_user_not_found_raises(wallet_user_service):
    """update_profile при неизвестном адресе поднимает ValueError."""
    with pytest.raises(ValueError, match="User not found"):
        await wallet_user_service.update_profile(
            WALLET_TRON, nickname="x"
        )


@pytest.mark.asyncio
async def test_update_profile_no_fields_raises(wallet_user_service):
    """update_profile без nickname и avatar поднимает ValueError."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    with pytest.raises(ValueError, match="At least one field"):
        await wallet_user_service.update_profile(WALLET_TRON)


@pytest.mark.asyncio
async def test_update_profile_avatar_wrong_format_raises(wallet_user_service):
    """update_profile с avatar не data:image/ поднимает ValueError."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    with pytest.raises(ValueError, match="data:image/"):
        await wallet_user_service.update_profile(
            WALLET_TRON, avatar="not-base64"
        )


@pytest.mark.asyncio
async def test_update_profile_nickname_taken_raises(wallet_user_service):
    """update_profile на занятый другим пользователем никнейм поднимает ValueError."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    await wallet_user_service.create_user(WALLET_ETH, "ethereum", "bob")
    with pytest.raises(ValueError, match="already taken"):
        await wallet_user_service.update_profile(
            WALLET_TRON, nickname="bob"
        )
