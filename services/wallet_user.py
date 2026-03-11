"""
Сервис для управления профилями пользователей кошелька (WalletUser).
Ориентир: https://github.com/RuSwift/garantex/blob/main/services/wallet_user.py
"""
import logging
from typing import List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from repos.wallet_user import WalletUserRepository, WalletUserResource
from services.tron_auth import TronAuth
from settings import Settings

logger = logging.getLogger(__name__)

ALLOWED_BLOCKCHAINS = ("tron", "ethereum")
AVATAR_MAX_BASE64_LEN = 1_500_000  # ~1MB base64


def _validate_ethereum_address(address: str) -> bool:
    """Проверка формата Ethereum-адреса: 0x + 40 hex-символов."""
    s = (address or "").strip()
    if len(s) != 42 or not s.startswith("0x"):
        return False
    return all(c in "0123456789abcdefABCDEF" for c in s[2:])


def _validate_wallet_address(wallet_address: str, blockchain: str) -> None:
    """
    Проверяет формат адреса кошелька для указанного блокчейна.
    Raises ValueError при невалидном формате.
    """
    addr = (wallet_address or "").strip()
    if not addr:
        raise ValueError("Wallet address cannot be empty")
    if blockchain == "tron":
        if not TronAuth.validate_tron_address(addr):
            raise ValueError(
                "Invalid TRON address format (expected: T + 34 base58 characters)"
            )
    elif blockchain == "ethereum":
        if not _validate_ethereum_address(addr):
            raise ValueError(
                "Invalid Ethereum address format (expected: 0x + 40 hex characters)"
            )


class WalletUserService:
    """Сервис для управления профилями пользователей кошелька."""

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

    async def get_by_wallet_address(
        self, wallet_address: str
    ) -> Optional[WalletUserResource.Get]:
        """
        Возвращает пользователя по адресу кошелька или None.
        """
        return await self._repo.get_by_wallet_address(wallet_address)

    async def get_by_nickname(
        self, nickname: str
    ) -> Optional[WalletUserResource.Get]:
        """
        Возвращает пользователя по никнейму или None.
        """
        return await self._repo.get_by_nickname(nickname)

    async def get_by_id(self, user_id: int) -> Optional[WalletUserResource.Get]:
        """Возвращает пользователя по id или None."""
        return await self._repo.get(user_id)

    async def list_managers(self) -> List[WalletUserResource.Get]:
        """Список пользователей с доступом в админку (менеджеры)."""
        return await self._repo.list_users(access_to_admin_panel=True)

    async def list_users_for_admin(
        self,
        *,
        search: Optional[str] = None,
        blockchain: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[WalletUserResource.Get], int]:
        """Список пользователей для админки с пагинацией и фильтрами. Возвращает (list, total)."""
        offset = (page - 1) * page_size
        return await self._repo.list(
            offset=offset,
            limit=page_size,
            search=search if (search and search.strip()) else None,
            blockchain=blockchain if (blockchain and blockchain.strip()) else None,
        )

    async def update_user_admin(
        self,
        user_id: int,
        *,
        nickname: Optional[str] = None,
        is_verified: Optional[bool] = None,
        access_to_admin_panel: Optional[bool] = None,
    ) -> Optional[WalletUserResource.Get]:
        """Обновить пользователя по id (админ): nickname, is_verified, access_to_admin_panel."""
        patch_data = {}
        if nickname is not None:
            nickname_clean = (nickname or "").strip()
            if not nickname_clean:
                raise ValueError("Nickname cannot be empty")
            if len(nickname_clean) > 100:
                raise ValueError("Nickname cannot exceed 100 characters")
            existing = await self._repo.get_by_nickname(nickname_clean)
            if existing and existing.id != user_id:
                raise ValueError(f"Nickname '{nickname_clean}' is already taken")
            patch_data["nickname"] = nickname_clean
        if is_verified is not None:
            patch_data["is_verified"] = is_verified
        if access_to_admin_panel is not None:
            patch_data["access_to_admin_panel"] = access_to_admin_panel
        if not patch_data:
            return await self._repo.get(user_id)
        updated = await self._repo.patch(user_id, WalletUserResource.Patch(**patch_data))
        if updated:
            await self._session.commit()
        return updated

    async def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя по id. Возвращает True, если удалён."""
        deleted = await self._repo.delete(user_id)
        if deleted:
            await self._session.commit()
            logger.info("Wallet user deleted: id=%d", user_id)
        return deleted

    async def get_by_identifier(
        self, identifier: str | int
    ) -> Optional[WalletUserResource.Get]:
        """
        Возвращает пользователя по идентификатору: id (int или строка-число) или DID (строка, начинается с 'did:').
        Иначе — ValueError.
        """
        if isinstance(identifier, int):
            return await self._repo.get(identifier)
        if isinstance(identifier, str) and identifier.strip().startswith("did:"):
            return await self._repo.get_by_did(identifier.strip())
        try:
            user_id = int(identifier)
            return await self._repo.get(user_id)
        except (TypeError, ValueError):
            raise ValueError(
                "identifier must be user id (integer) or DID (string starting with 'did:')"
            )

    async def create_user(
        self,
        wallet_address: str,
        blockchain: str,
        nickname: str,
        *,
        avatar: Optional[str] = None,
        access_to_admin_panel: bool = False,
        is_verified: bool = False,
    ) -> WalletUserResource.Get:
        """
        Создаёт нового пользователя кошелька.

        Raises:
            ValueError: если пользователь с таким адресом уже есть или не пройдена валидация.
        """
        existing = await self._repo.get_by_wallet_address(wallet_address)
        if existing:
            raise ValueError(
                f"User with wallet address '{wallet_address}' already exists"
            )

        nickname_clean = nickname.strip() if nickname else ""
        if not nickname_clean:
            raise ValueError("Nickname cannot be empty")
        if len(nickname_clean) > 100:
            raise ValueError("Nickname cannot exceed 100 characters")

        blockchain_lower = (blockchain or "").strip().lower()
        if not blockchain_lower or blockchain_lower not in ALLOWED_BLOCKCHAINS:
            raise ValueError(
                "Invalid blockchain type; allowed: tron, ethereum, bitcoin"
            )

        _validate_wallet_address(wallet_address, blockchain_lower)

        data = WalletUserResource.Create(
            wallet_address=wallet_address.strip(),
            blockchain=blockchain_lower,
            nickname=nickname_clean,
            avatar=avatar,
            access_to_admin_panel=access_to_admin_panel,
            is_verified=is_verified,
        )
        created = await self._repo.create(data)
        await self._session.commit()
        return created

    async def update_nickname(
        self,
        wallet_address: str,
        new_nickname: str,
    ) -> WalletUserResource.Get:
        """
        Обновляет никнейм пользователя по адресу кошелька.

        Raises:
            ValueError: если пользователь не найден или валидация не пройдена.
        """
        user = await self._repo.get_by_wallet_address(wallet_address)
        if not user:
            raise ValueError("User not found")

        nickname_clean = new_nickname.strip() if new_nickname else ""
        if not nickname_clean:
            raise ValueError("Nickname cannot be empty")
        if len(nickname_clean) > 100:
            raise ValueError("Nickname cannot exceed 100 characters")

        existing = await self._repo.get_by_nickname(nickname_clean)
        if existing and existing.wallet_address != wallet_address:
            raise ValueError(f"Nickname '{new_nickname}' is already taken by another user")

        updated = await self._repo.patch(
            user.id, WalletUserResource.Patch(nickname=nickname_clean)
        )
        if not updated:
            raise ValueError("User not found")
        await self._session.commit()
        return updated

    async def update_profile(
        self,
        wallet_address: str,
        *,
        nickname: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> WalletUserResource.Get:
        """
        Обновляет профиль (никнейм и/или аватар) по адресу кошелька.
        Пустая строка avatar очищает аватар.

        Raises:
            ValueError: если пользователь не найден, валидация не пройдена
                       или не передано ни одного поля для обновления.
        """
        user = await self._repo.get_by_wallet_address(wallet_address)
        if not user:
            raise ValueError("User not found")

        patch_data: dict = {}

        if nickname is not None and nickname.strip():
            nickname_clean = nickname.strip()
            if len(nickname_clean) > 100:
                raise ValueError("Nickname cannot exceed 100 characters")
            existing = await self._repo.get_by_nickname(nickname_clean)
            if existing and existing.wallet_address != wallet_address:
                raise ValueError(f"Nickname '{nickname}' is already taken")
            patch_data["nickname"] = nickname_clean

        if avatar is not None:
            if avatar == "":
                patch_data["avatar"] = None
            else:
                if not avatar.startswith("data:image/"):
                    raise ValueError(
                        "Avatar must be in base64 format starting with 'data:image/'"
                    )
                if len(avatar) > AVATAR_MAX_BASE64_LEN:
                    raise ValueError("Avatar size is too large (max 1MB)")
                patch_data["avatar"] = avatar

        if not patch_data:
            raise ValueError(
                "At least one field (nickname or avatar) must be provided"
            )

        updated = await self._repo.patch(
            user.id, WalletUserResource.Patch(**patch_data)
        )
        if not updated:
            raise ValueError("User not found")
        await self._session.commit()
        return updated

    async def update_admin_access(
        self, user_id: int, access_to_admin_panel: bool
    ) -> Optional[WalletUserResource.Get]:
        """
        Обновить доступ в админ-панель по id пользователя (для админа ноды).
        Возвращает обновлённого пользователя или None.
        """
        updated = await self._repo.patch(
            user_id,
            WalletUserResource.Patch(access_to_admin_panel=access_to_admin_panel),
        )
        if updated:
            await self._session.commit()
        return updated

    async def add_manager(
        self,
        wallet_address: str,
        blockchain: str,
        nickname: str,
    ) -> WalletUserResource.Get:
        """
        Добавить менеджера: выдать доступ в админку.
        Если пользователь с таким адресом уже есть — только включаем access_to_admin_panel.
        Иначе создаём нового WalletUser с access_to_admin_panel=True.

        Raises:
            ValueError: при невалидных данных или занятом никнейме.
        """
        existing = await self._repo.get_by_wallet_address(wallet_address.strip())
        if existing:
            updated = await self.update_admin_access(existing.id, True)
            return updated
        return await self.create_user(
            wallet_address,
            blockchain,
            nickname,
            access_to_admin_panel=True,
        )


__all__ = ["WalletUserService"]
