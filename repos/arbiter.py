"""
Репозиторий адресов арбитра (Wallet с role in arbiter, arbiter-backup).
Resource использует is_active; в БД хранится role. Маппинг в репозитории.
"""
import logging
from datetime import datetime
from typing import List, Optional, Self

from pydantic import Field, model_validator
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import Wallet
from repos.base import BaseRepository
from settings import Settings

logger = logging.getLogger(__name__)

_ARBITER_ROLES = ("arbiter", "arbiter-backup")


def _role_to_is_active(role: Optional[str]) -> bool:
    """Маппинг role → is_active: arbiter → True, иначе False."""
    return role == "arbiter"


def _is_active_to_role(is_active: bool) -> str:
    """Маппинг is_active → role."""
    return "arbiter" if is_active else "arbiter-backup"


class ArbiterResource(BaseResource):
    """Resource для адресов арбитра. Поле role в ресурсе заменено на is_active."""

    class Create(BaseResource.Create):
        name: str = Field(..., max_length=255, description="Arbiter address name")
        encrypted_mnemonic: Optional[str] = Field(None, description="Encrypted mnemonic")
        tron_address: str = Field(..., max_length=34, description="TRON address")
        ethereum_address: str = Field(..., max_length=42, description="Ethereum address")
        is_active: bool = Field(..., description="True = active arbiter, False = backup")
        owner_did: Optional[str] = Field(None, max_length=255, description="Owner node DID")

        @model_validator(mode="after")
        def encrypted_mnemonic_non_empty(self) -> Self:
            if self.encrypted_mnemonic is None or not str(self.encrypted_mnemonic).strip():
                raise ValueError("encrypted_mnemonic is required")
            return self

    class Get(BaseResource.Get):
        id: int
        name: str
        tron_address: str
        ethereum_address: str
        is_active: bool
        created_at: datetime
        updated_at: datetime

    class Patch(BaseResource.Patch):
        name: Optional[str] = Field(None, max_length=255)
        is_active: Optional[bool] = None


def _model_to_get(model: Wallet) -> ArbiterResource.Get:
    """Wallet (role arbiter/arbiter-backup) → Get с is_active."""
    return ArbiterResource.Get(
        id=model.id,
        name=model.name,
        tron_address=model.tron_address,
        ethereum_address=model.ethereum_address,
        is_active=_role_to_is_active(model.role),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class ArbiterRepository(BaseRepository):
    """CRUD для кошельков арбитра (Wallet с role in arbiter, arbiter-backup)."""

    def _arbiter_role_filter(self):
        return Wallet.role.in_(_ARBITER_ROLES)

    async def list(self) -> List[ArbiterResource.Get]:
        """Список всех адресов арбитра (активные и резервные)."""
        stmt = (
            select(Wallet)
            .where(self._arbiter_role_filter())
            .order_by(Wallet.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_model_to_get(m) for m in result.scalars().all()]

    async def get(self, id: int) -> Optional[ArbiterResource.Get]:
        """Один адрес арбитра по id."""
        stmt = (
            select(Wallet)
            .where(Wallet.id == id)
            .where(self._arbiter_role_filter())
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_get(model) if model else None

    async def get_active(self) -> Optional[ArbiterResource.Get]:
        """Активный арбитр (role='arbiter'), один. Для проверки инициализации."""
        stmt = (
            select(Wallet)
            .where(Wallet.role == "arbiter")
            .order_by(Wallet.id.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_get(model) if model else None

    async def ensure_single_active(self) -> bool:
        """
        Если в БД несколько записей с role='arbiter', оставить активным только одну (с минимальным id).
        Остальные перевести в arbiter-backup. Возвращает True, если были изменения.
        """
        stmt = (
            select(Wallet.id)
            .where(Wallet.role == "arbiter")
            .order_by(Wallet.id.asc())
        )
        result = await self._session.execute(stmt)
        ids = [row[0] for row in result.all()]
        if len(ids) <= 1:
            return False
        # Оставляем активным ids[0], остальные — резерв
        stmt_update = (
            update(Wallet)
            .where(Wallet.id.in_(ids[1:]))
            .where(Wallet.role == "arbiter")
            .values(role="arbiter-backup")
        )
        await self._session.execute(stmt_update)
        await self._session.flush()
        logger.info(
            "Normalized arbiter: kept id=%s active, demoted ids=%s",
            ids[0],
            ids[1:],
        )
        return True

    async def create(self, data: ArbiterResource.Create) -> ArbiterResource.Get:
        """Создать запись арбитра. role выставляется из data.is_active."""
        role = _is_active_to_role(data.is_active)
        model = Wallet(
            name=data.name,
            encrypted_mnemonic=data.encrypted_mnemonic,
            tron_address=data.tron_address,
            ethereum_address=data.ethereum_address,
            role=role,
            owner_did=data.owner_did,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _model_to_get(model)

    async def patch(self, id: int, data: ArbiterResource.Patch) -> Optional[ArbiterResource.Get]:
        """Обновить name и/или is_active. Фильтр по id и role in arbiter/arbiter-backup."""
        values = {}
        if data.name is not None:
            values["name"] = data.name
        if data.is_active is not None:
            values["role"] = _is_active_to_role(data.is_active)
        if not values:
            return await self.get(id)
        stmt = (
            update(Wallet)
            .where(Wallet.id == id)
            .where(self._arbiter_role_filter())
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return await self.get(id)

    async def delete(self, id: int) -> bool:
        """Удалить запись. Строго по id и role in ('arbiter', 'arbiter-backup')."""
        stmt = (
            delete(Wallet)
            .where(Wallet.id == id)
            .where(self._arbiter_role_filter())
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def exists_with_addresses(
        self, tron_address: str, ethereum_address: str
    ) -> bool:
        """Есть ли уже арбитр с таким tron или ethereum адресом."""
        stmt = (
            select(Wallet.id)
            .where(self._arbiter_role_filter())
            .where(
                (Wallet.tron_address == tron_address)
                | (Wallet.ethereum_address == ethereum_address)
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
