"""
Сервис для логики спейсов: роли (owner/operator/reader) и управление участниками.
Не утяжеляет WalletUserService.
"""
import re
from typing import Any, Dict, List, Optional, Union

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

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
from settings import Settings

from services.tron_auth import TronAuth

PROFILE_ICON_MAX_BASE64_LEN = 524288  # 512 KB

# Паттерны, запрещённые в description (XSS, инъекции). Проверка без учёта регистра.
_PROFILE_DESCRIPTION_FORBIDDEN = (
    "<script",
    "</script",
    "<iframe",
    "<object",
    "<embed",
    "javascript:",
    "vbscript:",
    "data:text/html",
    "onerror=",
    "onload=",
    "onclick=",
    "onmouseover=",
    "onfocus=",
    "expression(",
)
# Управляющие символы, кроме перевода строки и табуляции
_PROFILE_DESCRIPTION_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _validate_profile_description(description: Optional[str]) -> None:
    """
    Проверяет description на вредоносные символы и типичные эксплойты инъекций (XSS, HTML).
    При обнаружении опасного содержимого выбрасывает ValueError.
    """
    if not description or not description.strip():
        return
    text = description
    if _PROFILE_DESCRIPTION_CONTROL_CHARS.search(text):
        raise ValueError("Profile description must not contain control characters")
    if "<" in text or ">" in text:
        raise ValueError("Profile description must not contain HTML tags")
    lower = text.lower()
    for forbidden in _PROFILE_DESCRIPTION_FORBIDDEN:
        if forbidden in lower:
            raise ValueError(
                "Profile description must not contain script or event handler content"
            )


def validate_wallet_address(blockchain: str, wallet_address: str) -> bool:
    """
    Проверяет формат адреса для заданного блокчейна.
    tron: T + 34 base58; ethereum: 0x + 40 hex. Остальные — False.
    """
    if not blockchain or not wallet_address:
        return False
    addr = (wallet_address or "").strip()
    chain = (blockchain or "").lower()
    if chain == "tron":
        return TronAuth.validate_tron_address(addr)
    if chain == "ethereum":
        return bool(re.match(r"^0x[0-9a-fA-F]{40}$", addr))
    return False


def _primary_role_from_sub_roles(roles: List[WalletUserSubRole]) -> WalletUserSubRole:
    """Главная роль из списка: owner > operator > reader."""
    if WalletUserSubRole.owner in roles:
        return WalletUserSubRole.owner
    if WalletUserSubRole.operator in roles:
        return WalletUserSubRole.operator
    return WalletUserSubRole.reader


class SpaceService:
    """Сервис для спейсов: определение роли в спейсе и управление участниками (только owner)."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ):
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = WalletUserRepository(
            session=session, redis=redis, settings=settings
        )

    async def get_space_role(
        self,
        space: str,
        wallet_address: str,
        blockchain: str = "tron",
    ) -> WalletUserSubRole:
        """
        Возвращает роль пользователя в спейсе: owner (WalletUser с nickname=space),
        иначе роль из WalletUserSub (owner/operator/reader), по умолчанию reader.
        """
        owner = await self._repo.get_by_nickname(space)
        if not owner:
            return WalletUserSubRole.reader
        if owner.wallet_address == wallet_address:
            return WalletUserSubRole.owner
        sub = await self._repo.get_sub_by_address(
            owner.id, wallet_address, blockchain
        )
        if not sub:
            return WalletUserSubRole.reader
        return _primary_role_from_sub_roles(sub.roles)

    async def _ensure_owner_and_owner_id(
        self, space: str, actor_wallet_address: str
    ) -> int:
        """Проверяет, что actor — owner спейса; возвращает wallet_user_id владельца. Иначе SpacePermissionDenied."""
        role = await self.get_space_role(space, actor_wallet_address, "tron")
        if role != WalletUserSubRole.owner:
            raise SpacePermissionDenied(
                "Only space owner can perform this action"
            )
        owner = await self._repo.get_by_nickname(space)
        if not owner:
            raise SpacePermissionDenied("Space not found")
        return owner.id

    async def list_subs_for_space(
        self, space: str, actor_wallet_address: str
    ) -> List[WalletUserSubResource.Get]:
        """Список участников спейса. Только owner."""
        wallet_user_id = await self._ensure_owner_and_owner_id(
            space, actor_wallet_address
        )
        return await self._repo.list_subs(wallet_user_id)

    async def add_sub_for_space(
        self,
        space: str,
        actor_wallet_address: str,
        data: WalletUserSubResource.Create,
    ) -> WalletUserSubResource.Get:
        """Добавить участника в спейс. Только owner. Валидирует nickname, blockchain+address, запрет дублей адрес+сеть."""
        wallet_user_id = await self._ensure_owner_and_owner_id(
            space, actor_wallet_address
        )
        nickname = (data.nickname or "").strip()
        if not nickname:
            raise MissingNickname("Participant nickname is required")
        wallet_address = (data.wallet_address or "").strip()
        blockchain = (data.blockchain or "").strip()
        if not validate_wallet_address(blockchain, wallet_address):
            raise InvalidWalletAddress(
                f"Invalid wallet address for blockchain {data.blockchain}"
            )
        existing = await self._repo.get_sub_by_address(
            wallet_user_id, wallet_address, blockchain
        )
        if existing:
            raise DuplicateParticipant(
                "A participant with this wallet address and network already exists in the space"
            )
        create_data = WalletUserSubResource.Create(
            wallet_address=wallet_address,
            blockchain=blockchain,
            nickname=nickname,
            roles=data.roles,
            is_blocked=data.is_blocked,
        )
        added = await self._repo.add_sub(wallet_user_id, create_data)
        await self._session.commit()
        return added

    async def patch_sub_for_space(
        self,
        space: str,
        actor_wallet_address: str,
        sub_id: int,
        data: WalletUserSubResource.Patch,
    ) -> WalletUserSubResource.Get | None:
        """Обновить участника (nickname, roles). Только owner. Nickname при обновлении не может быть пустым."""
        wallet_user_id = await self._ensure_owner_and_owner_id(
            space, actor_wallet_address
        )
        payload = data.model_dump(exclude_unset=True)
        if "nickname" in payload:
            if payload["nickname"] is None or not str(payload["nickname"]).strip():
                raise MissingNickname("Participant nickname cannot be empty")
        updated = await self._repo.patch_sub(wallet_user_id, sub_id, data)
        if updated:
            await self._session.commit()
        return updated

    async def delete_sub_for_space(
        self,
        space: str,
        actor_wallet_address: str,
        sub_id: int,
    ) -> bool:
        """Удалить участника из спейса. Только owner."""
        wallet_user_id = await self._ensure_owner_and_owner_id(
            space, actor_wallet_address
        )
        deleted = await self._repo.delete_sub(wallet_user_id, sub_id)
        if deleted:
            await self._session.commit()
        return deleted

    async def get_space_profile(
        self, space: str, actor_wallet_address: str
    ) -> Optional[Dict[str, Any]]:
        """Профиль спейса (description, icon). Только owner. Возвращает dict или None."""
        await self._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner = await self._repo.get_by_nickname(space)
        if not owner or not owner.profile:
            return None
        return owner.profile.model_dump()

    async def update_space_profile(
        self,
        space: str,
        actor_wallet_address: str,
        data: Union[WalletUserProfileSchema, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Обновить профиль спейса. Только owner. Лимит иконки 512 КБ."""
        owner_id = await self._ensure_owner_and_owner_id(space, actor_wallet_address)
        if isinstance(data, dict):
            profile = WalletUserProfileSchema(**data)
        else:
            profile = data
        if profile.icon is not None and len(profile.icon) > PROFILE_ICON_MAX_BASE64_LEN:
            raise ValueError("Profile icon size is too large (max 512 KB)")
        _validate_profile_description(profile.description)
        patch_data = WalletUserResource.Patch(profile=profile)
        updated = await self._repo.patch(owner_id, patch_data)
        if updated:
            await self._session.commit()
        out = await self.get_space_profile(space, actor_wallet_address)
        return out if out is not None else {}

    def get_space_profile_filled(
        self, profile: Optional[Dict[str, Any]]
    ) -> bool:
        """True если профиль заполнен (есть description или icon)."""
        if not profile:
            return False
        return bool(profile.get("description") or profile.get("icon"))


__all__ = [
    "SpaceService",
    "validate_wallet_address",
]
