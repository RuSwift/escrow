import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import WalletUser
from repos.base import BaseRepository
from settings import Settings

logger = logging.getLogger(__name__)


class WalletUserResource(BaseResource):
    """Resource-схемы для операций с пользователями кошелька (WalletUser)."""

    class Create(BaseResource.Create):
        wallet_address: str = Field(..., max_length=255, description="Wallet address (TRON/ETH/etc.)")
        blockchain: str = Field(..., max_length=20, description="Blockchain type: tron, ethereum, bitcoin, etc.")
        nickname: str = Field(..., max_length=100, description="User display name (unique)")
        avatar: Optional[str] = Field(default=None, description="User avatar in base64 format")
        access_to_admin_panel: bool = Field(default=False, description="Access to admin panel")
        is_verified: bool = Field(default=False, description="Whether the user is verified")

    class Patch(BaseResource.Patch):
        nickname: Optional[str] = Field(default=None, max_length=100)
        avatar: Optional[str] = Field(default=None)
        access_to_admin_panel: Optional[bool] = None
        is_verified: Optional[bool] = None
        balance_usdt: Optional[Decimal] = None

    class Get(BaseResource.Get):
        id: int
        wallet_address: str
        blockchain: str
        did: str
        nickname: str
        avatar: Optional[str] = None
        access_to_admin_panel: bool
        is_verified: bool
        balance_usdt: Decimal
        created_at: datetime
        updated_at: datetime


def _model_to_get(model: WalletUser) -> WalletUserResource.Get:
    """Преобразует модель WalletUser в WalletUserResource.Get."""
    return WalletUserResource.Get(
        id=model.id,
        wallet_address=model.wallet_address,
        blockchain=model.blockchain,
        did=model.did,
        nickname=model.nickname,
        avatar=model.avatar,
        access_to_admin_panel=model.access_to_admin_panel,
        is_verified=model.is_verified,
        balance_usdt=model.balance_usdt,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class WalletUserRepository(BaseRepository):
    """
    Репозиторий для пользователей кошелька (WalletUser). CRUD и выборки по естественным ключам.
    """

    async def get(self, user_id: int) -> Optional[WalletUserResource.Get]:
        """Read: возвращает пользователя по id или None."""
        stmt = select(WalletUser).where(WalletUser.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_get(model) if model else None

    async def get_by_wallet_address(
        self, wallet_address: str
    ) -> Optional[WalletUserResource.Get]:
        """Возвращает пользователя по адресу кошелька или None (для проверки существования и поиска по wallet)."""
        stmt = select(WalletUser).where(WalletUser.wallet_address == wallet_address)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_get(model) if model else None

    async def get_by_nickname(self, nickname: str) -> Optional[WalletUserResource.Get]:
        """Возвращает пользователя по никнейму или None (для проверки занятости никнейма)."""
        stmt = select(WalletUser).where(WalletUser.nickname == nickname)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_get(model) if model else None

    async def get_by_did(self, did: str) -> Optional[WalletUserResource.Get]:
        """Возвращает пользователя по DID или None."""
        stmt = select(WalletUser).where(WalletUser.did == did)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_get(model) if model else None

    async def list_users(
        self, *, access_to_admin_panel: Optional[bool] = None
    ) -> List[WalletUserResource.Get]:
        """Список пользователей, опционально с фильтром по доступу в админку."""
        stmt = select(WalletUser).order_by(WalletUser.created_at.desc())
        if access_to_admin_panel is not None:
            stmt = stmt.where(WalletUser.access_to_admin_panel == access_to_admin_panel)
        result = await self._session.execute(stmt)
        return [_model_to_get(m) for m in result.scalars().all()]

    async def create(self, data: WalletUserResource.Create) -> WalletUserResource.Get:
        """Create: создаёт пользователя. DID генерируется при вставке (event listener)."""
        model = WalletUser(
            wallet_address=data.wallet_address,
            blockchain=data.blockchain,
            nickname=data.nickname,
            avatar=data.avatar,
            access_to_admin_panel=data.access_to_admin_panel,
            is_verified=data.is_verified,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _model_to_get(model)

    async def patch(
        self, user_id: int, data: WalletUserResource.Patch
    ) -> Optional[WalletUserResource.Get]:
        """Update: частичное обновление по id (только переданные поля)."""
        payload = data.model_dump(exclude_unset=True)
        allowed = {"nickname", "avatar", "access_to_admin_panel", "is_verified", "balance_usdt"}
        values = {k: v for k, v in payload.items() if k in allowed}
        if not values:
            return await self.get(user_id)
        stmt = update(WalletUser).where(WalletUser.id == user_id).values(**values)
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            return None
        return await self.get(user_id)

    async def delete(self, user_id: int) -> bool:
        """Delete: удаляет пользователя по id. Возвращает True, если запись была удалена."""
        stmt = delete(WalletUser).where(WalletUser.id == user_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
