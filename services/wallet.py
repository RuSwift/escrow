"""
Wallet service: создание кошельков из мнемоники, CRUD (только role=None).
По аналогии с https://github.com/RuSwift/garantex/blob/main/services/wallet.py
"""
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from didcomm.crypto import EthCrypto, EthKeyPair
from repos.node import NodeRepository
from repos.wallet import WalletResource, WalletRepository
from services.tron.utils import keypair_from_mnemonic
from settings import Settings

logger = logging.getLogger(__name__)


class WalletService:
    """Сервис управления кошельками (операционные, role=None)."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ):
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = WalletRepository(session=session, redis=redis, settings=settings)

    @staticmethod
    def _addresses_from_mnemonic(mnemonic: str) -> dict:
        """Генерирует tron_address и ethereum_address из мнемоники. Raises ValueError при невалидной мнемонике."""
        if not EthCrypto.validate_mnemonic(mnemonic):
            raise ValueError("Invalid mnemonic phrase")
        tron_address, _ = keypair_from_mnemonic(mnemonic, account_index=0)
        eth_keypair = EthKeyPair.from_mnemonic(mnemonic)
        ethereum_address = eth_keypair.address
        return {"tron_address": tron_address, "ethereum_address": ethereum_address}

    async def create_wallet(self, name: str, mnemonic: str) -> WalletResource.Get:
        """Создать кошелёк. Шифрует мнемонику, проверяет дубликаты имени и адресов."""
        name_stripped = name.strip()
        if not name_stripped:
            raise ValueError("Wallet name is required")
        mnemonic_normalized = " ".join((mnemonic or "").split())
        if not mnemonic_normalized:
            raise ValueError("Mnemonic phrase is required")
        name_exists = await self._repo.exists_operation_wallet_with_name(name_stripped)
        if name_exists:
            raise ValueError("Wallet with this name already exists")
        addresses = self._addresses_from_mnemonic(mnemonic_normalized)
        exists = await self._repo.exists_operation_wallet_with_addresses(
            addresses["tron_address"],
            addresses["ethereum_address"],
        )
        if exists:
            raise ValueError("Wallet with these addresses already exists")
        node_repo = NodeRepository(session=self._session, redis=self._redis, settings=self._settings)
        node = await node_repo.get()
        owner_did = node.did if node else None
        encrypted = self._repo.encrypt_data(mnemonic_normalized)
        created = await self._repo.create(
            WalletResource.Create(
                name=name_stripped,
                encrypted_mnemonic=encrypted,
                tron_address=addresses["tron_address"],
                ethereum_address=addresses["ethereum_address"],
                owner_did=owner_did,
            )
        )
        await self._session.commit()
        return created

    async def get_wallets(self) -> List[WalletResource.Get]:
        """Список всех операционных кошельков (role=None)."""
        return await self._repo.list_operation_wallets()

    async def get_wallet(self, wallet_id: int) -> Optional[WalletResource.Get]:
        """Кошелёк по id (только с role=None)."""
        return await self._repo.get_operation_wallet(wallet_id)

    async def update_wallet_name(
        self, wallet_id: int, name: str
    ) -> Optional[WalletResource.Get]:
        """Обновить имя кошелька."""
        updated = await self._repo.update_name(wallet_id, name.strip())
        if updated:
            await self._session.commit()
        return updated

    async def delete_wallet(self, wallet_id: int) -> bool:
        """Удалить кошелёк (только с role=None)."""
        deleted = await self._repo.delete_operation_wallet(wallet_id)
        if deleted:
            await self._session.commit()
        return deleted
