"""
Репозиторий кошельков (Wallet). CRUD для кошельков с role=None (операционные).
По аналогии с garantex services/wallet.py + db.models.Wallet.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import Wallet
from repos.base import BaseRepository
from settings import Settings

logger = logging.getLogger(__name__)


class WalletResource(BaseResource):
    """Resource-схемы для операций с кошельками (Wallet)."""

    class Create(BaseResource.Create):
        name: str = Field(..., max_length=255, description="Wallet name")
        encrypted_mnemonic: str = Field(..., description="Encrypted mnemonic phrase")
        tron_address: str = Field(..., max_length=34, description="TRON address")
        ethereum_address: str = Field(..., max_length=42, description="Ethereum address")

    class Get(BaseResource.Get):
        id: int
        name: str
        tron_address: str
        ethereum_address: str
        account_permissions: Optional[Dict[str, Any]] = None
        created_at: datetime
        updated_at: datetime


def _model_to_get(model: Wallet) -> WalletResource.Get:
    return WalletResource.Get(
        id=model.id,
        name=model.name,
        tron_address=model.tron_address,
        ethereum_address=model.ethereum_address,
        account_permissions=model.account_permissions,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class WalletRepository(BaseRepository):
    """
    Репозиторий кошельков. Только кошельки с role=None (для операций).
    """

    async def list_operation_wallets(self) -> List[WalletResource.Get]:
        """Список кошельков для операций (role is None)."""
        stmt = (
            select(Wallet)
            .where(Wallet.role.is_(None))
            .order_by(Wallet.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_model_to_get(m) for m in result.scalars().all()]

    async def get_operation_wallet(self, wallet_id: int) -> Optional[WalletResource.Get]:
        """Кошелёк по id (только с role=None)."""
        stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .where(Wallet.role.is_(None))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_get(model) if model else None

    async def create(self, data: WalletResource.Create) -> WalletResource.Get:
        """Создать кошелёк (role=None)."""
        model = Wallet(
            name=data.name,
            encrypted_mnemonic=data.encrypted_mnemonic,
            tron_address=data.tron_address,
            ethereum_address=data.ethereum_address,
            role=None,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _model_to_get(model)

    async def update_name(self, wallet_id: int, name: str) -> Optional[WalletResource.Get]:
        """Обновить имя кошелька (только с role=None)."""
        stmt = (
            update(Wallet)
            .where(Wallet.id == wallet_id)
            .where(Wallet.role.is_(None))
            .values(name=name)
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            return None
        await self._session.flush()
        return await self.get_operation_wallet(wallet_id)

    async def delete_operation_wallet(self, wallet_id: int) -> bool:
        """Удалить кошелёк (только с role=None)."""
        stmt = (
            delete(Wallet)
            .where(Wallet.id == wallet_id)
            .where(Wallet.role.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def exists_operation_wallet_with_addresses(
        self, tron_address: str, ethereum_address: str
    ) -> bool:
        """Проверка: есть ли уже кошелёк с такими адресами (среди role=None)."""
        stmt = (
            select(Wallet.id)
            .where(Wallet.role.is_(None))
            .where(
                (Wallet.tron_address == tron_address)
                | (Wallet.ethereum_address == ethereum_address)
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
