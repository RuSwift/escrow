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


# Валидные форматы: TRON — T + 34 base58; Ethereum — 0x + 40 hex
WALLET_TRON = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
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
async def test_create_user_invalid_tron_address_raises(wallet_user_service):
    """create_user с невалидным TRON-адресом поднимает ValueError."""
    with pytest.raises(ValueError, match="Invalid TRON address"):
        await wallet_user_service.create_user(
            "0x1234567890123456789012345678901234567890", "tron", "alice"
        )
    with pytest.raises(ValueError, match="Invalid TRON address"):
        await wallet_user_service.create_user(
            "Tshort", "tron", "alice"
        )


@pytest.mark.asyncio
async def test_create_user_invalid_ethereum_address_raises(wallet_user_service):
    """create_user с невалидным Ethereum-адресом поднимает ValueError."""
    with pytest.raises(ValueError, match="Invalid Ethereum address"):
        await wallet_user_service.create_user(
            WALLET_TRON, "ethereum", "bob"
        )
    with pytest.raises(ValueError, match="Invalid Ethereum address"):
        await wallet_user_service.create_user(
            "0xzzzz", "ethereum", "bob"
        )


@pytest.mark.asyncio
async def test_create_user_blockchain_normalized_to_lowercase(wallet_user_service):
    """create_user принимает blockchain в любом регистре (tron/TRON)."""
    out = await wallet_user_service.create_user(
        WALLET_TRON, "TRON", "alice"
    )
    assert out.blockchain == "tron"


# --- add_manager ---


@pytest.mark.asyncio
async def test_add_manager_invalid_address_raises(wallet_user_service):
    """add_manager с невалидным адресом поднимает ValueError (валидация как в create_user)."""
    with pytest.raises(ValueError, match="Invalid TRON address"):
        await wallet_user_service.add_manager(
            "0x1234567890123456789012345678901234567890", "tron", "manager1"
        )
    with pytest.raises(ValueError, match="Invalid Ethereum address"):
        await wallet_user_service.add_manager(
            WALLET_TRON, "ethereum", "manager2"
        )


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


# --- get_by_identifier ---


@pytest.mark.asyncio
async def test_get_by_identifier_by_id_int(wallet_user_service):
    """get_by_identifier с целым id возвращает пользователя."""
    created = await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    found = await wallet_user_service.get_by_identifier(created.id)
    assert found is not None
    assert found.id == created.id
    assert found.nickname == "alice"


@pytest.mark.asyncio
async def test_get_by_identifier_by_id_string(wallet_user_service):
    """get_by_identifier со строкой-числом (id) возвращает пользователя."""
    created = await wallet_user_service.create_user(WALLET_TRON, "tron", "bob")
    found = await wallet_user_service.get_by_identifier(str(created.id))
    assert found is not None
    assert found.id == created.id


@pytest.mark.asyncio
async def test_get_by_identifier_by_did(wallet_user_service):
    """get_by_identifier с DID возвращает пользователя."""
    created = await wallet_user_service.create_user(WALLET_TRON, "tron", "carol")
    found = await wallet_user_service.get_by_identifier(created.did)
    assert found is not None
    assert found.did == created.did
    assert found.nickname == "carol"


@pytest.mark.asyncio
async def test_get_by_identifier_invalid_raises(wallet_user_service):
    """get_by_identifier с невалидной строкой (не число и не did:) поднимает ValueError."""
    with pytest.raises(ValueError, match="identifier must be user id"):
        await wallet_user_service.get_by_identifier("not-a-number-or-did")


@pytest.mark.asyncio
async def test_get_by_identifier_not_found_returns_none(wallet_user_service):
    """get_by_identifier с несуществующим id возвращает None."""
    found = await wallet_user_service.get_by_identifier(999999)
    assert found is None


# --- list_users_for_admin ---


@pytest.mark.asyncio
async def test_list_users_for_admin_empty_returns_empty_list_and_zero(
    wallet_user_service,
):
    """Без пользователей list_users_for_admin возвращает ([], 0)."""
    users, total = await wallet_user_service.list_users_for_admin(
        page=1, page_size=20
    )
    assert users == []
    assert total == 0


@pytest.mark.asyncio
async def test_list_users_for_admin_returns_all_with_pagination(
    wallet_user_service,
):
    """list_users_for_admin возвращает список и total с пагинацией."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    await wallet_user_service.create_user(WALLET_ETH, "ethereum", "bob")
    users, total = await wallet_user_service.list_users_for_admin(
        page=1, page_size=20
    )
    assert len(users) == 2
    assert total == 2
    nicknames = {u.nickname for u in users}
    assert nicknames == {"alice", "bob"}


@pytest.mark.asyncio
async def test_list_users_for_admin_page_size_limits_results(
    wallet_user_service,
):
    """list_users_for_admin с page_size=1 возвращает одну запись и total=2."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    await wallet_user_service.create_user(WALLET_ETH, "ethereum", "bob")
    users, total = await wallet_user_service.list_users_for_admin(
        page=1, page_size=1
    )
    assert len(users) == 1
    assert total == 2


@pytest.mark.asyncio
async def test_list_users_for_admin_search_by_nickname(wallet_user_service):
    """list_users_for_admin с search по никнейму фильтрует."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    await wallet_user_service.create_user(WALLET_ETH, "ethereum", "bob")
    users, total = await wallet_user_service.list_users_for_admin(
        search="ali", page=1, page_size=20
    )
    assert len(users) == 1
    assert total == 1
    assert users[0].nickname == "alice"


@pytest.mark.asyncio
async def test_list_users_for_admin_search_by_wallet_address(
    wallet_user_service,
):
    """list_users_for_admin с search по адресу кошелька фильтрует."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    users, total = await wallet_user_service.list_users_for_admin(
        search=WALLET_TRON[:10], page=1, page_size=20
    )
    assert len(users) == 1
    assert total == 1
    assert users[0].wallet_address == WALLET_TRON


@pytest.mark.asyncio
async def test_list_users_for_admin_blockchain_filter(wallet_user_service):
    """list_users_for_admin с blockchain возвращает только этот блокчейн."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    await wallet_user_service.create_user(WALLET_ETH, "ethereum", "bob")
    users, total = await wallet_user_service.list_users_for_admin(
        blockchain="ethereum", page=1, page_size=20
    )
    assert len(users) == 1
    assert total == 1
    assert users[0].blockchain == "ethereum"
    assert users[0].nickname == "bob"


# --- update_user_admin ---


@pytest.mark.asyncio
async def test_update_user_admin_nickname_success(wallet_user_service):
    """update_user_admin обновляет nickname и возвращает пользователя."""
    created = await wallet_user_service.create_user(
        WALLET_TRON, "tron", "alice"
    )
    updated = await wallet_user_service.update_user_admin(
        created.id, nickname="alice_v2"
    )
    assert updated is not None
    assert updated.nickname == "alice_v2"


@pytest.mark.asyncio
async def test_update_user_admin_is_verified_and_access(wallet_user_service):
    """update_user_admin обновляет is_verified и access_to_admin_panel."""
    created = await wallet_user_service.create_user(
        WALLET_TRON, "tron", "alice"
    )
    updated = await wallet_user_service.update_user_admin(
        created.id,
        is_verified=True,
        access_to_admin_panel=True,
    )
    assert updated is not None
    assert updated.is_verified is True
    assert updated.access_to_admin_panel is True


@pytest.mark.asyncio
async def test_update_user_admin_empty_nickname_raises(wallet_user_service):
    """update_user_admin с пустым nickname поднимает ValueError."""
    created = await wallet_user_service.create_user(
        WALLET_TRON, "tron", "alice"
    )
    with pytest.raises(ValueError, match="Nickname cannot be empty"):
        await wallet_user_service.update_user_admin(
            created.id, nickname="   "
        )


@pytest.mark.asyncio
async def test_update_user_admin_nickname_taken_raises(wallet_user_service):
    """update_user_admin на занятый другим пользователем никнейм поднимает ValueError."""
    await wallet_user_service.create_user(WALLET_TRON, "tron", "alice")
    created2 = await wallet_user_service.create_user(
        WALLET_ETH, "ethereum", "bob"
    )
    with pytest.raises(ValueError, match="already taken"):
        await wallet_user_service.update_user_admin(
            created2.id, nickname="alice"
        )


@pytest.mark.asyncio
async def test_update_user_admin_no_fields_returns_current(wallet_user_service):
    """update_user_admin без полей возвращает текущего пользователя (без изменений)."""
    created = await wallet_user_service.create_user(
        WALLET_TRON, "tron", "alice"
    )
    updated = await wallet_user_service.update_user_admin(created.id)
    assert updated is not None
    assert updated.nickname == "alice"


# --- delete_user ---


@pytest.mark.asyncio
async def test_delete_user_success(wallet_user_service):
    """delete_user удаляет пользователя и возвращает True."""
    created = await wallet_user_service.create_user(
        WALLET_TRON, "tron", "alice"
    )
    deleted = await wallet_user_service.delete_user(created.id)
    assert deleted is True
    assert await wallet_user_service.get_by_id(created.id) is None


@pytest.mark.asyncio
async def test_delete_user_not_found_returns_false(wallet_user_service):
    """delete_user для несуществующего id возвращает False."""
    deleted = await wallet_user_service.delete_user(999999)
    assert deleted is False
