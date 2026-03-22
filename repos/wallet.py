"""
Репозиторий кошельков (Wallet). CRUD для кошельков с role=None (операционные)
и role in (external, multisig) — реквизиты onRamp/offRamp.
По аналогии с garantex services/wallet.py + db.models.Wallet.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Self

from pydantic import Field, model_validator
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import Wallet
from repos.base import BaseRepository
from settings import Settings

logger = logging.getLogger(__name__)

_EXCHANGE_ROLES = ("external", "multisig")
ExchangeRole = Literal["external", "multisig"]


def _mnemonic_non_empty(value: Optional[str]) -> bool:
    return value is not None and bool(str(value).strip())


class WalletResource(BaseResource):
    """Resource-схемы для операций с кошельками (Wallet)."""

    class Create(BaseResource.Create):
        name: str = Field(..., max_length=255, description="Wallet name")
        role: Optional[str] = Field(
            None,
            max_length=255,
            description="Wallet role; None = operational",
        )
        encrypted_mnemonic: Optional[str] = Field(
            None,
            description="Encrypted mnemonic phrase",
        )
        tron_address: str = Field(..., max_length=34, description="TRON address")
        ethereum_address: str = Field(..., max_length=42, description="Ethereum address")
        owner_did: Optional[str] = Field(None, max_length=255, description="Owner node DID")

        @model_validator(mode="after")
        def validate_encrypted_mnemonic_for_role(self) -> Self:
            if self.role == "external":
                return self
            if not _mnemonic_non_empty(self.encrypted_mnemonic):
                raise ValueError(
                    "encrypted_mnemonic is required unless role is 'external'",
                )
            return self

    class Patch(BaseResource.Patch):
        name: Optional[str] = Field(None, max_length=255)
        role: Optional[str] = Field(None, max_length=255)
        encrypted_mnemonic: Optional[str] = Field(
            None,
            description="Encrypted mnemonic phrase",
        )
        tron_address: Optional[str] = Field(None, max_length=34)
        ethereum_address: Optional[str] = Field(None, max_length=42)
        owner_did: Optional[str] = Field(None, max_length=255)

        @model_validator(mode="after")
        def validate_encrypted_mnemonic_when_set(self) -> Self:
            if "encrypted_mnemonic" not in self.model_fields_set:
                return self
            if _mnemonic_non_empty(self.encrypted_mnemonic):
                return self
            if self.role != "external":
                raise ValueError(
                    "encrypted_mnemonic can only be empty when role is 'external'; "
                    "include role='external' in the same request.",
                )
            return self

    class Get(BaseResource.Get):
        id: int
        name: str
        tron_address: str
        ethereum_address: str
        owner_did: Optional[str] = None
        account_permissions: Optional[Dict[str, Any]] = None
        created_at: datetime
        updated_at: datetime


class ExchangeWalletResource(BaseResource):
    """Кошелёк с role external | multisig (реквизиты)."""

    class Get(BaseResource.Get):
        id: int
        name: str
        tron_address: str
        ethereum_address: str
        role: str
        owner_did: Optional[str] = None
        account_permissions: Optional[Dict[str, Any]] = None
        created_at: datetime
        updated_at: datetime


def _model_to_get(model: Wallet) -> WalletResource.Get:
    return WalletResource.Get(
        id=model.id,
        name=model.name,
        tron_address=model.tron_address,
        ethereum_address=model.ethereum_address,
        owner_did=getattr(model, "owner_did", None),
        account_permissions=model.account_permissions,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _model_to_exchange_get(model: Wallet) -> ExchangeWalletResource.Get:
    return ExchangeWalletResource.Get(
        id=model.id,
        name=model.name,
        tron_address=model.tron_address,
        ethereum_address=model.ethereum_address,
        role=model.role or "",
        owner_did=getattr(model, "owner_did", None),
        account_permissions=model.account_permissions,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class WalletRepository(BaseRepository):
    """
    Репозиторий кошельков: операционные (role is None) и реквизиты (external, multisig).
    """

    def _exchange_scope(self, owner_did: str):
        return (Wallet.owner_did == owner_did) & (Wallet.role.in_(_EXCHANGE_ROLES))

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
        """Создать кошелёк; role из data (None = операционный)."""
        model = Wallet(
            name=data.name,
            encrypted_mnemonic=data.encrypted_mnemonic,
            tron_address=data.tron_address,
            ethereum_address=data.ethereum_address,
            role=data.role,
            owner_did=data.owner_did,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _model_to_get(model)

    async def create_exchange_wallet(
        self,
        data: WalletResource.Create,
        owner_did: str,
    ) -> ExchangeWalletResource.Get:
        """Создать реквизит (external | multisig)."""
        if data.role not in _EXCHANGE_ROLES:
            raise ValueError("role must be 'external' or 'multisig'")
        merged = data.model_copy(update={"owner_did": owner_did})
        model = Wallet(
            name=merged.name,
            encrypted_mnemonic=merged.encrypted_mnemonic,
            tron_address=merged.tron_address,
            ethereum_address=merged.ethereum_address,
            role=merged.role,
            owner_did=merged.owner_did,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _model_to_exchange_get(model)

    async def list_exchange_wallets(
        self,
        owner_did: str,
        role: Optional[ExchangeRole] = None,
    ) -> List[ExchangeWalletResource.Get]:
        stmt = select(Wallet).where(self._exchange_scope(owner_did))
        if role is not None:
            stmt = stmt.where(Wallet.role == role)
        stmt = stmt.order_by(Wallet.created_at.desc())
        result = await self._session.execute(stmt)
        return [_model_to_exchange_get(m) for m in result.scalars().all()]

    async def get_exchange_wallet(
        self,
        wallet_id: int,
        owner_did: str,
    ) -> Optional[ExchangeWalletResource.Get]:
        stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .where(self._exchange_scope(owner_did))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_exchange_get(model) if model else None

    async def patch_exchange_wallet(
        self,
        wallet_id: int,
        owner_did: str,
        data: WalletResource.Patch,
    ) -> Optional[ExchangeWalletResource.Get]:
        payload = data.model_dump(exclude_unset=True)
        if not payload:
            return await self.get_exchange_wallet(wallet_id, owner_did)
        stmt = (
            update(Wallet)
            .where(Wallet.id == wallet_id)
            .where(self._exchange_scope(owner_did))
            .values(**payload)
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            return None
        await self._session.flush()
        return await self.get_exchange_wallet(wallet_id, owner_did)

    async def delete_exchange_wallet(self, wallet_id: int, owner_did: str) -> bool:
        stmt = (
            delete(Wallet)
            .where(Wallet.id == wallet_id)
            .where(self._exchange_scope(owner_did))
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def exists_exchange_wallet_with_addresses(
        self,
        owner_did: str,
        tron_address: str,
        ethereum_address: str,
        role: Optional[ExchangeRole] = None,
    ) -> bool:
        stmt = (
            select(Wallet.id)
            .where(self._exchange_scope(owner_did))
            .where(
                (Wallet.tron_address == tron_address)
                | (Wallet.ethereum_address == ethereum_address)
            )
        )
        if role is not None:
            stmt = stmt.where(Wallet.role == role)
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

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

    async def exists_operation_wallet_with_name(self, name: str) -> bool:
        """Проверка: есть ли уже кошелёк с таким именем (среди role=None)."""
        stmt = (
            select(Wallet.id)
            .where(Wallet.role.is_(None))
            .where(Wallet.name == name.strip())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exists_operation_wallet_with_addresses(
        self,
        tron_address: str,
        ethereum_address: str,
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
