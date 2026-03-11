"""
Сервис управления адресами арбитра (бизнес-логика).
Ориентир: garantex services/arbiter/service.py.
"""
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from repos.arbiter import ArbiterResource, ArbiterRepository
from repos.node import NodeRepository
from services.wallet import WalletService
from settings import Settings

logger = logging.getLogger(__name__)


class ArbiterService:
    """Сервис адресов арбитра: создание из мнемоники, переключение активного, удаление."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ):
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = ArbiterRepository(
            session=session, redis=redis, settings=settings
        )

    async def is_arbiter_initialized(self) -> bool:
        """Есть ли хотя бы один активный арбитр (is_active=True)."""
        return await self._repo.get_active() is not None

    async def list_arbiter_addresses(self) -> List[ArbiterResource.Get]:
        """Список всех адресов арбитра. Перед выдачей нормализует состояние (не более одного активного)."""
        changed = await self._repo.ensure_single_active()
        if changed:
            await self._session.commit()
        return await self._repo.list()

    async def get_arbiter_address(
        self, wallet_id: int
    ) -> Optional[ArbiterResource.Get]:
        """Адрес арбитра по id."""
        return await self._repo.get(wallet_id)

    async def create_arbiter_address(
        self, name: str, mnemonic: str
    ) -> ArbiterResource.Get:
        """
        Создать адрес арбитра из мнемоники.
        Текущий активный (если есть) переводится в резервный. Новый создаётся как активный.
        """
        name_stripped = (name or "").strip()
        if not name_stripped:
            raise ValueError("Arbiter address name is required")
        mnemonic_normalized = " ".join((mnemonic or "").split())
        if not mnemonic_normalized:
            raise ValueError("Mnemonic phrase is required")

        addresses = WalletService._addresses_from_mnemonic(mnemonic_normalized)
        exists = await self._repo.exists_with_addresses(
            addresses["tron_address"],
            addresses["ethereum_address"],
        )
        if exists:
            raise ValueError(
                "Arbiter with these addresses already exists. "
                f"TRON: {addresses['tron_address']}, "
                f"Ethereum: {addresses['ethereum_address']}"
            )

        active = await self._repo.get_active()
        if active:
            await self._repo.patch(
                active.id,
                ArbiterResource.Patch(is_active=False),
            )
            await self._session.flush()

        node_repo = NodeRepository(
            session=self._session,
            redis=self._redis,
            settings=self._settings,
        )
        node = await node_repo.get()
        owner_did = node.did if node else None

        encrypted = self._repo.encrypt_data(mnemonic_normalized)
        created = await self._repo.create(
            ArbiterResource.Create(
                name=name_stripped,
                encrypted_mnemonic=encrypted,
                tron_address=addresses["tron_address"],
                ethereum_address=addresses["ethereum_address"],
                is_active=True,
                owner_did=owner_did,
            )
        )
        await self._session.commit()
        logger.info(
            "Arbiter address created: id=%d, name=%s, tron=%s, eth=%s",
            created.id,
            created.name,
            created.tron_address,
            created.ethereum_address,
        )
        return created

    async def update_arbiter_name(
        self, wallet_id: int, name: str
    ) -> Optional[ArbiterResource.Get]:
        """Обновить имя адреса арбитра."""
        name_stripped = (name or "").strip()
        if not name_stripped:
            raise ValueError("Arbiter address name is required")
        updated = await self._repo.patch(
            wallet_id,
            ArbiterResource.Patch(name=name_stripped),
        )
        if updated:
            await self._session.commit()
        return updated

    async def switch_active_arbiter(
        self, wallet_id: int
    ) -> ArbiterResource.Get:
        """
        Сделать указанный резервный адрес активным; текущий активный становится резервным.
        """
        to_activate = await self._repo.get(wallet_id)
        if not to_activate:
            raise ValueError("Arbiter address not found")
        if to_activate.is_active:
            raise ValueError("Address is already active")

        active = await self._repo.get_active()
        if not active:
            raise ValueError("No active arbiter to switch from")

        await self._repo.patch(active.id, ArbiterResource.Patch(is_active=False))
        await self._repo.patch(wallet_id, ArbiterResource.Patch(is_active=True))
        await self._session.commit()

        updated = await self._repo.get(wallet_id)
        assert updated is not None
        logger.info(
            "Switched active arbiter: old_active_id=%d, new_active_id=%d",
            active.id,
            wallet_id,
        )
        return updated

    async def delete_arbiter_address(self, wallet_id: int) -> bool:
        """Удалить адрес арбитра. Нельзя удалить активный (сначала переключить)."""
        item = await self._repo.get(wallet_id)
        if not item:
            return False
        if item.is_active:
            raise ValueError(
                "Cannot delete active arbiter address. Activate another address first."
            )
        deleted = await self._repo.delete(wallet_id)
        if deleted:
            await self._session.commit()
            logger.info("Arbiter address deleted: id=%d", wallet_id)
        return deleted
