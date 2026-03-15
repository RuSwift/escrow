"""
Тесты SpaceService: get_space_role, list_subs_for_space, add_sub_for_space, patch_sub_for_space, delete_sub_for_space.
"""
from unittest.mock import patch

import pytest

from db.models import WalletUserSubRole
from repos.wallet_user import (
    WalletUserRepository,
    WalletUserResource,
    WalletUserSubResource,
)
from services.space import (
    DuplicateParticipant,
    InvalidWalletAddress,
    MissingNickname,
    SpacePermissionDenied,
    SpaceService,
)


# Валидные TRON-адреса (34 символа, T + base58)
WALLET_OWNER = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
WALLET_SUB1 = "TSub123456789012345678901234567890AB"
WALLET_SUB2 = "TSub2123456789012345678901234567890AB"
SPACE_NAME = "test_space"


@pytest.fixture
def space_service(test_db, test_redis, test_settings) -> SpaceService:
    return SpaceService(session=test_db, redis=test_redis, settings=test_settings)


@pytest.fixture
def wallet_user_repo(test_db, test_redis, test_settings) -> WalletUserRepository:
    return WalletUserRepository(
        session=test_db, redis=test_redis, settings=test_settings
    )


@pytest.fixture
async def space_with_owner_and_sub(space_service, wallet_user_repo):
    """Создаёт space (owner WalletUser) и одного участника (WalletUserSub с roles=[operator])."""
    from services.wallet_user import WalletUserService
    wu_service = WalletUserService(
        session=space_service._session,
        redis=space_service._redis,
        settings=space_service._settings,
    )
    owner = await wu_service.create_user(WALLET_OWNER, "tron", SPACE_NAME)
    sub = await wallet_user_repo.add_sub(
        owner.id,
        WalletUserSubResource.Create(
            wallet_address=WALLET_SUB1,
            blockchain="tron",
            nickname="sub_one",
            roles=[WalletUserSubRole.operator],
        ),
    )
    await space_service._session.commit()
    return {"owner": owner, "sub": sub}


# --- get_space_role ---


@pytest.mark.asyncio
async def test_get_space_role_owner(space_service, wallet_user_repo):
    """Владелец спейса (WalletUser с nickname=space) получает роль owner."""
    from services.wallet_user import WalletUserService
    wu = WalletUserService(
        session=space_service._session,
        redis=space_service._redis,
        settings=space_service._settings,
    )
    await wu.create_user(WALLET_OWNER, "tron", SPACE_NAME)
    role = await space_service.get_space_role(SPACE_NAME, WALLET_OWNER, "tron")
    assert role == WalletUserSubRole.owner


@pytest.mark.asyncio
async def test_get_space_role_sub_operator(space_with_owner_and_sub, space_service):
    """Участник с roles=[operator] получает роль operator."""
    role = await space_service.get_space_role(SPACE_NAME, WALLET_SUB1, "tron")
    assert role == WalletUserSubRole.operator


@pytest.mark.asyncio
async def test_get_space_role_sub_reader_default(space_service, wallet_user_repo):
    """Участник без ролей (или только reader) получает роль reader."""
    from services.wallet_user import WalletUserService
    wu = WalletUserService(
        session=space_service._session,
        redis=space_service._redis,
        settings=space_service._settings,
    )
    owner = await wu.create_user(WALLET_OWNER, "tron", SPACE_NAME)
    await wallet_user_repo.add_sub(
        owner.id,
        WalletUserSubResource.Create(
            wallet_address=WALLET_SUB1,
            blockchain="tron",
            nickname="sub_reader",
            roles=[WalletUserSubRole.reader],
        ),
    )
    await space_service._session.commit()
    role = await space_service.get_space_role(SPACE_NAME, WALLET_SUB1, "tron")
    assert role == WalletUserSubRole.reader


# --- list_subs_for_space (only owner) ---


@pytest.mark.asyncio
async def test_list_subs_for_space_owner_success(space_with_owner_and_sub, space_service):
    """Owner может получить список участников."""
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    assert len(subs) == 1
    assert subs[0].wallet_address == WALLET_SUB1
    assert subs[0].roles == [WalletUserSubRole.operator]


@pytest.mark.asyncio
async def test_list_subs_for_space_non_owner_raises(space_with_owner_and_sub, space_service):
    """Не-owner (operator/reader) получает SpacePermissionDenied."""
    with pytest.raises(SpacePermissionDenied):
        await space_service.list_subs_for_space(SPACE_NAME, WALLET_SUB1)


# --- add_sub_for_space (only owner) ---


@pytest.mark.asyncio
@patch("services.space.validate_wallet_address", return_value=True)
async def test_add_sub_for_space_owner_success(mock_validate, space_with_owner_and_sub, space_service):
    """Owner может добавить участника (валидация адреса замокана для тестовых адресов)."""
    added = await space_service.add_sub_for_space(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserSubResource.Create(
            wallet_address=WALLET_SUB2,
            blockchain="tron",
            nickname="sub_two",
            roles=[WalletUserSubRole.reader],
        ),
    )
    assert added.wallet_address == WALLET_SUB2
    assert added.roles == [WalletUserSubRole.reader]
    mock_validate.assert_called_once_with("tron", WALLET_SUB2)
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    assert len(subs) == 2


@pytest.mark.asyncio
async def test_add_sub_for_space_non_owner_raises(space_with_owner_and_sub, space_service):
    """Не-owner не может добавить участника."""
    with pytest.raises(SpacePermissionDenied):
        await space_service.add_sub_for_space(
            SPACE_NAME,
            WALLET_SUB1,
            WalletUserSubResource.Create(
                wallet_address=WALLET_SUB2,
                blockchain="tron",
                nickname="sub_two",
            ),
        )


@pytest.mark.asyncio
async def test_add_sub_for_space_invalid_address_raises(space_with_owner_and_sub, space_service):
    """При невалидном адресе выбрасывается InvalidWalletAddress."""
    with pytest.raises(InvalidWalletAddress):
        await space_service.add_sub_for_space(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserSubResource.Create(
                wallet_address="invalid",
                blockchain="tron",
                nickname="bad",
            ),
        )


@pytest.mark.asyncio
@patch("services.space.validate_wallet_address", return_value=True)
async def test_add_sub_for_space_missing_nickname_raises(mock_validate, space_with_owner_and_sub, space_service):
    """Добавление участника без nickname выбрасывает MissingNickname."""
    with pytest.raises(MissingNickname):
        await space_service.add_sub_for_space(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserSubResource.Create(
                wallet_address=WALLET_SUB2,
                blockchain="tron",
                nickname=None,
            ),
        )
    with pytest.raises(MissingNickname):
        await space_service.add_sub_for_space(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserSubResource.Create(
                wallet_address=WALLET_SUB2,
                blockchain="tron",
                nickname="   ",
            ),
        )


@pytest.mark.asyncio
@patch("services.space.validate_wallet_address", return_value=True)
async def test_add_sub_for_space_duplicate_address_blockchain_raises(mock_validate, space_with_owner_and_sub, space_service):
    """Добавление участника с тем же адресом и сетью выбрасывает DuplicateParticipant."""
    with pytest.raises(DuplicateParticipant):
        await space_service.add_sub_for_space(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserSubResource.Create(
                wallet_address=WALLET_SUB1,
                blockchain="tron",
                nickname="another_nick",
                roles=[WalletUserSubRole.reader],
            ),
        )


# --- patch_sub_for_space (only owner) ---


@pytest.mark.asyncio
async def test_patch_sub_for_space_owner_success(space_with_owner_and_sub, space_service):
    """Owner может обновить участника (nickname, roles)."""
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    sub_id = subs[0].id
    patched = await space_service.patch_sub_for_space(
        SPACE_NAME,
        WALLET_OWNER,
        sub_id,
        WalletUserSubResource.Patch(nickname="sub_updated", roles=[WalletUserSubRole.reader]),
    )
    assert patched is not None
    assert patched.nickname == "sub_updated"
    assert patched.roles == [WalletUserSubRole.reader]


@pytest.mark.asyncio
async def test_patch_sub_for_space_non_owner_raises(space_with_owner_and_sub, space_service):
    """Не-owner не может обновить участника."""
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    sub_id = subs[0].id
    with pytest.raises(SpacePermissionDenied):
        await space_service.patch_sub_for_space(
            SPACE_NAME,
            WALLET_SUB1,
            sub_id,
            WalletUserSubResource.Patch(nickname="hacked"),
        )


@pytest.mark.asyncio
async def test_patch_sub_for_space_empty_nickname_raises(space_with_owner_and_sub, space_service):
    """Обновление nickname на пустую строку выбрасывает MissingNickname."""
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    sub_id = subs[0].id
    with pytest.raises(MissingNickname):
        await space_service.patch_sub_for_space(
            SPACE_NAME,
            WALLET_OWNER,
            sub_id,
            WalletUserSubResource.Patch(nickname=""),
        )
    with pytest.raises(MissingNickname):
        await space_service.patch_sub_for_space(
            SPACE_NAME,
            WALLET_OWNER,
            sub_id,
            WalletUserSubResource.Patch(nickname="   "),
        )


# --- delete_sub_for_space (only owner) ---


@pytest.mark.asyncio
async def test_delete_sub_for_space_owner_success(space_with_owner_and_sub, space_service):
    """Owner может удалить участника."""
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    sub_id = subs[0].id
    deleted = await space_service.delete_sub_for_space(SPACE_NAME, WALLET_OWNER, sub_id)
    assert deleted is True
    subs_after = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    assert len(subs_after) == 0


@pytest.mark.asyncio
async def test_delete_sub_for_space_non_owner_raises(space_with_owner_and_sub, space_service):
    """Не-owner не может удалить участника."""
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    sub_id = subs[0].id
    with pytest.raises(SpacePermissionDenied):
        await space_service.delete_sub_for_space(SPACE_NAME, WALLET_SUB1, sub_id)
