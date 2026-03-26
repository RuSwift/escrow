"""
Репозиторий кошельков (Wallet). CRUD для кошельков с role=None (операционные)
и role in (external, multisig) — реквизиты onRamp/offRamp.
По аналогии с garantex services/wallet.py + db.models.Wallet.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Self

from pydantic import Field, model_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import Wallet
from repos.base import BaseRepository
from services.multisig_wallet.constants import MULTISIG_STATUS_PENDING_CONFIG
from services.multisig_wallet.meta import default_meta_dict
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
        tron_address: Optional[str] = Field(
            None,
            max_length=34,
            description="TRON address; optional for external if ethereum is set; empty for multisig",
        )
        ethereum_address: Optional[str] = Field(
            None,
            max_length=42,
            description="Ethereum address; optional for external (TRC20-only); empty for multisig",
        )
        owner_did: Optional[str] = Field(None, max_length=255, description="Owner node DID")

        @model_validator(mode="after")
        def validate_wallet_create(self) -> Self:
            t = (self.tron_address or "").strip()
            e = (self.ethereum_address or "").strip()

            if self.role == "external":
                if not t and not e:
                    raise ValueError(
                        "external wallet requires at least one of tron_address or "
                        "ethereum_address",
                    )
                return self

            if self.role == "multisig":
                if t or e:
                    raise ValueError(
                        "multisig wallet requires empty tron_address and ethereum_address",
                    )
                if not _mnemonic_non_empty(self.encrypted_mnemonic):
                    raise ValueError("encrypted_mnemonic is required for multisig")
                return self

            if not _mnemonic_non_empty(self.encrypted_mnemonic):
                raise ValueError("encrypted_mnemonic is required")
            if not t:
                raise ValueError("tron_address is required")
            if not e:
                raise ValueError("ethereum_address is required")
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
        tron_address: Optional[str] = None
        ethereum_address: Optional[str] = None
        owner_did: Optional[str] = None
        account_permissions: Optional[Dict[str, Any]] = None
        created_at: datetime
        updated_at: datetime


class ExchangeWalletResource(BaseResource):
    """Кошелёк с role external | multisig (реквизиты)."""

    class Get(BaseResource.Get):
        id: int
        name: str
        tron_address: Optional[str] = None
        ethereum_address: Optional[str] = None
        role: str
        owner_did: Optional[str] = None
        account_permissions: Optional[Dict[str, Any]] = None
        created_at: datetime
        updated_at: datetime
        multisig_setup_status: Optional[str] = None
        multisig_setup_meta: Optional[Dict[str, Any]] = None


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


def _multisig_fields(model: Wallet) -> Dict[str, Any]:
    return {
        "multisig_setup_status": getattr(model, "multisig_setup_status", None),
        "multisig_setup_meta": getattr(model, "multisig_setup_meta", None),
    }


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
        **_multisig_fields(model),
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
        t = (data.tron_address or "").strip() or None
        e = (data.ethereum_address or "").strip() or None
        model = Wallet(
            name=data.name,
            encrypted_mnemonic=data.encrypted_mnemonic,
            tron_address=t,
            ethereum_address=e,
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
        if merged.role == "multisig":
            if not _mnemonic_non_empty(merged.encrypted_mnemonic):
                raise ValueError("encrypted_mnemonic is required for multisig")
            plain = self.decrypt_data(merged.encrypted_mnemonic)
            from services.wallet import WalletService

            addrs = WalletService._addresses_from_mnemonic(plain)
            tron_s = addrs["tron_address"]
            eth_s = addrs["ethereum_address"]
        else:
            tron_s = (merged.tron_address or "").strip() or None
            eth_s = (merged.ethereum_address or "").strip() or None
        ms_status = None
        ms_meta = None
        if merged.role == "multisig":
            ms_status = MULTISIG_STATUS_PENDING_CONFIG
            ms_meta = default_meta_dict()
        model = Wallet(
            name=merged.name,
            encrypted_mnemonic=merged.encrypted_mnemonic,
            tron_address=tron_s,
            ethereum_address=eth_s,
            role=merged.role,
            owner_did=merged.owner_did,
            multisig_setup_status=ms_status,
            multisig_setup_meta=ms_meta,
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

    async def get_exchange_wallet_model(
        self,
        wallet_id: int,
        owner_did: str,
    ) -> Optional[Wallet]:
        stmt = (
            select(Wallet)
            .where(Wallet.id == wallet_id)
            .where(self._exchange_scope(owner_did))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

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

    async def exists_exchange_wallet_with_name(
        self,
        owner_did: str,
        name: str,
        exclude_wallet_id: Optional[int] = None,
    ) -> bool:
        stmt = (
            select(Wallet.id)
            .where(self._exchange_scope(owner_did))
            .where(Wallet.name == name.strip())
        )
        if exclude_wallet_id is not None:
            stmt = stmt.where(Wallet.id != exclude_wallet_id)
        stmt = stmt.limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exists_exchange_wallet_with_tron(
        self,
        owner_did: str,
        tron_address: str,
    ) -> bool:
        stmt = (
            select(Wallet.id)
            .where(self._exchange_scope(owner_did))
            .where(Wallet.tron_address == tron_address.strip())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exchange_wallet_has_address(
        self,
        owner_did: str,
        *,
        address: str,
        chain: str,
    ) -> bool:
        """Проверка: address на указанной сети совпадает с реквизитом (external|multisig) владельца."""
        addr = (address or "").strip()
        if not addr:
            return False
        scope = self._exchange_scope(owner_did)
        if chain == "TRON":
            stmt = (
                select(Wallet.id)
                .where(scope)
                .where(Wallet.tron_address == addr)
                .limit(1)
            )
        elif chain == "ETH":
            stmt = (
                select(Wallet.id)
                .where(scope)
                .where(Wallet.ethereum_address.isnot(None))
                .where(func.lower(Wallet.ethereum_address) == addr.lower())
                .limit(1)
            )
        else:
            return False
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
