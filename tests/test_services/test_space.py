"""
Тесты SpaceService: get_space_role, list_subs_for_space, add_sub_for_space,
patch_sub_for_space, delete_sub_for_space.
"""
from unittest.mock import patch

import pytest

from core.exceptions import (
    DuplicateParticipant,
    InvalidWalletAddress,
    MissingNickname,
    SpacePermissionDenied,
)
from db.models import WalletUserSubRole
from repos.wallet_user import (
    WalletUserProfileSchema,
    WalletUserRepository,
    WalletUserResource,
    WalletUserSubResource,
)
from services.space import PROFILE_ICON_MAX_BASE64_LEN, SpaceService


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


@pytest.mark.asyncio
async def test_get_space_role_sub_with_owner_in_roles(space_service, wallet_user_repo):
    """Суб с ролью owner в наборе ролей получает итоговую роль owner."""
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
            nickname="co_owner",
            roles=[WalletUserSubRole.owner, WalletUserSubRole.reader],
        ),
    )
    await space_service._session.commit()
    role = await space_service.get_space_role(SPACE_NAME, WALLET_SUB1, "tron")
    assert role == WalletUserSubRole.owner


# --- list_subs_for_space (owner or operator) ---


@pytest.mark.asyncio
async def test_list_subs_for_space_owner_success(space_with_owner_and_sub, space_service):
    """Owner может получить список участников."""
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_OWNER)
    assert len(subs) == 1
    assert subs[0].wallet_address == WALLET_SUB1
    assert subs[0].roles == [WalletUserSubRole.operator]


@pytest.mark.asyncio
async def test_list_subs_for_space_operator_success(space_with_owner_and_sub, space_service):
    """Operator может читать список участников."""
    subs = await space_service.list_subs_for_space(SPACE_NAME, WALLET_SUB1)
    assert len(subs) == 1
    assert subs[0].wallet_address == WALLET_SUB1


@pytest.mark.asyncio
async def test_signatory_tron_labels_owner_and_sub(space_with_owner_and_sub, space_service):
    """Подписи к TRON: суб с ником + владелец, если адрес не пересёкся."""
    rows = await space_service.signatory_tron_labels(SPACE_NAME, WALLET_OWNER)
    by_a = {r["tron_address"]: r["nickname"] for r in rows}
    assert by_a[WALLET_SUB1] == "sub_one"
    assert by_a[WALLET_OWNER] == SPACE_NAME


@pytest.mark.asyncio
async def test_signatory_tron_labels_operator_ok(space_with_owner_and_sub, space_service):
    """Operator может запросить те же подписи."""
    rows = await space_service.signatory_tron_labels(SPACE_NAME, WALLET_SUB1)
    by_a = {r["tron_address"]: r["nickname"] for r in rows}
    assert by_a[WALLET_SUB1] == "sub_one"
    assert WALLET_OWNER in by_a


@pytest.mark.asyncio
async def test_list_subs_for_space_reader_raises(space_service, wallet_user_repo):
    """Reader не может получить список участников."""
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


# --- get_space_profile (only owner) ---


@pytest.mark.asyncio
async def test_get_space_profile_owner_returns_none_when_empty(space_with_owner_and_sub, space_service):
    """Owner получает None когда профиль не заполнен."""
    profile = await space_service.get_space_profile(SPACE_NAME, WALLET_OWNER)
    assert profile is None


@pytest.mark.asyncio
async def test_get_space_profile_non_owner_raises(space_with_owner_and_sub, space_service):
    """Не-owner при get_space_profile получает SpacePermissionDenied."""
    with pytest.raises(SpacePermissionDenied):
        await space_service.get_space_profile(SPACE_NAME, WALLET_SUB1)


@pytest.mark.asyncio
async def test_get_space_profile_owner_returns_saved_profile(space_with_owner_and_sub, space_service):
    """Owner получает сохранённый профиль после update_space_profile."""
    await space_service.update_space_profile(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserProfileSchema(description="My space", icon="data:image/png;base64,iVBORw0KGgo="),
    )
    profile = await space_service.get_space_profile(SPACE_NAME, WALLET_OWNER)
    assert profile is not None
    assert profile.get("description") == "My space"
    assert profile.get("icon") == "data:image/png;base64,iVBORw0KGgo="


# --- update_space_profile (only owner, icon limit) ---


@pytest.mark.asyncio
async def test_update_space_profile_non_owner_raises(space_with_owner_and_sub, space_service):
    """Не-owner при update_space_profile получает SpacePermissionDenied."""
    with pytest.raises(SpacePermissionDenied):
        await space_service.update_space_profile(
            SPACE_NAME,
            WALLET_SUB1,
            WalletUserProfileSchema(description="x"),
        )


@pytest.mark.asyncio
async def test_update_space_profile_icon_too_large_raises(space_with_owner_and_sub, space_service):
    """update_space_profile с иконкой больше 512 КБ выбрасывает ValueError."""
    big_icon = "x" * (PROFILE_ICON_MAX_BASE64_LEN + 1)
    with pytest.raises(ValueError, match="512 KB"):
        await space_service.update_space_profile(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserProfileSchema(icon=big_icon),
        )


@pytest.mark.asyncio
async def test_update_space_profile_icon_within_limit_succeeds(space_with_owner_and_sub, space_service):
    """Иконка в лимите сохраняется успешно."""
    small_icon = "data:image/png;base64," + "A" * 100
    result = await space_service.update_space_profile(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserProfileSchema(icon=small_icon),
    )
    assert result.get("icon") == small_icon


@pytest.mark.asyncio
async def test_space_profile_company_name_roundtrip(space_with_owner_and_sub, space_service):
    """company_name сохраняется и возвращается в get_space_profile."""
    await space_service.update_space_profile(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserProfileSchema(company_name="ООО Ромашка"),
    )
    profile = await space_service.get_space_profile(SPACE_NAME, WALLET_OWNER)
    assert profile.get("company_name") == "ООО Ромашка"


@pytest.mark.asyncio
async def test_get_space_company_name_for_display(space_with_owner_and_sub, space_service):
    """company_name для шапки читается по nickname спейса без проверки owner."""
    assert await space_service.get_space_company_name_for_display(SPACE_NAME) is None
    assert await space_service.get_space_company_name_for_display("nonexistent_space_xyz") is None
    await space_service.update_space_profile(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserProfileSchema(company_name="ООО Ромашка"),
    )
    assert await space_service.get_space_company_name_for_display(SPACE_NAME) == "ООО Ромашка"


@pytest.mark.asyncio
async def test_space_profile_only_description(space_with_owner_and_sub, space_service):
    """Профиль только с description корректно сохраняется и читается."""
    await space_service.update_space_profile(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserProfileSchema(description="Desc only"),
    )
    profile = await space_service.get_space_profile(SPACE_NAME, WALLET_OWNER)
    assert profile == {
        "description": "Desc only",
        "company_name": None,
        "icon": None,
        "language": None,
    }


@pytest.mark.asyncio
async def test_update_space_profile_language_from_accept_when_omitted(
    space_with_owner_and_sub, space_service
):
    """Если language не в теле запроса, подставляется accept_language (ru|en)."""
    await space_service.update_space_profile(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserProfileSchema(description="x"),
        accept_language="en",
    )
    profile = await space_service.get_space_profile(SPACE_NAME, WALLET_OWNER)
    assert profile.get("description") == "x"
    assert profile.get("language") == "en"


@pytest.mark.asyncio
async def test_update_space_profile_explicit_language_overrides_accept(
    space_with_owner_and_sub, space_service
):
    await space_service.update_space_profile(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserProfileSchema(description="y", language="ru"),
        accept_language="en",
    )
    profile = await space_service.get_space_profile(SPACE_NAME, WALLET_OWNER)
    assert profile.get("language") == "ru"


@pytest.mark.asyncio
async def test_space_profile_get_space_profile_filled(space_with_owner_and_sub, space_service):
    """get_space_profile_filled возвращает True при заполненном профиле."""
    assert space_service.get_space_profile_filled(None) is False
    assert space_service.get_space_profile_filled({}) is False
    assert space_service.get_space_profile_filled({"description": "x"}) is True
    assert space_service.get_space_profile_filled({"icon": "data:image/png;base64,x"}) is True
    assert space_service.get_space_profile_filled({"description": "", "icon": None}) is False
    assert space_service.get_space_profile_filled({"company_name": "Acme"}) is True
    assert space_service.get_space_profile_filled({"description": "", "company_name": "", "icon": None}) is False


# --- Валидация description (XSS, инъекции) ---


@pytest.mark.asyncio
async def test_update_space_profile_rejects_script_in_company_name(space_with_owner_and_sub, space_service):
    """update_space_profile отклоняет company_name с тегом script."""
    with pytest.raises(ValueError, match="script|HTML"):
        await space_service.update_space_profile(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserProfileSchema(company_name="Hello <script>alert(1)</script>"),
        )


@pytest.mark.asyncio
async def test_update_space_profile_rejects_script_in_description(space_with_owner_and_sub, space_service):
    """update_space_profile отклоняет description с тегом script."""
    with pytest.raises(ValueError, match="script|HTML"):
        await space_service.update_space_profile(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserProfileSchema(description="Hello <script>alert(1)</script>"),
        )


@pytest.mark.asyncio
async def test_update_space_profile_rejects_javascript_in_description(space_with_owner_and_sub, space_service):
    """update_space_profile отклоняет description с javascript:."""
    with pytest.raises(ValueError, match="script|event"):
        await space_service.update_space_profile(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserProfileSchema(description="Link javascript:alert(1)"),
        )


@pytest.mark.asyncio
async def test_update_space_profile_rejects_control_chars_in_description(space_with_owner_and_sub, space_service):
    """update_space_profile отклоняет description с управляющими символами."""
    with pytest.raises(ValueError, match="control"):
        await space_service.update_space_profile(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserProfileSchema(description="Text with null\x00byte"),
        )


@pytest.mark.asyncio
async def test_update_space_profile_rejects_html_tags_in_description(space_with_owner_and_sub, space_service):
    """update_space_profile отклоняет description с угловыми скобками (HTML)."""
    with pytest.raises(ValueError, match="HTML"):
        await space_service.update_space_profile(
            SPACE_NAME,
            WALLET_OWNER,
            WalletUserProfileSchema(description="Safe <b>not allowed</b>"),
        )


@pytest.mark.asyncio
async def test_update_space_profile_accepts_safe_description(space_with_owner_and_sub, space_service):
    """update_space_profile принимает безопасный текст в description."""
    result = await space_service.update_space_profile(
        SPACE_NAME,
        WALLET_OWNER,
        WalletUserProfileSchema(description="Обычное описание спейса: буквы, цифры 123, пунктуация."),
    )
    assert result.get("description") == "Обычное описание спейса: буквы, цифры 123, пунктуация."
