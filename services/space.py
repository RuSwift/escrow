"""
Сервис для логики спейсов: роли (owner/operator/reader) и управление участниками.
Не утяжеляет WalletUserService.
"""
import re
from typing import List

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
    WalletUserRepository,
    WalletUserSubResource,
)
from settings import Settings

from services.tron_auth import TronAuth


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


__all__ = [
    "SpaceService",
    "validate_wallet_address",
]
