import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import Field
from sqlalchemy import func, or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from core.entities import BaseResource
from db.models import WalletUser, WalletUserSub, WalletUserSubRole
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
        did: Optional[str] = Field(default=None, description="DID (e.g. did:tron:nickname); if set, used instead of auto-generation")

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


def _roles_str_to_enum(roles_raw: Optional[List[str]]) -> List[WalletUserSubRole]:
    """Map DB role strings to enum list; skip invalid values."""
    if not roles_raw:
        return []
    result: List[WalletUserSubRole] = []
    for r in roles_raw:
        try:
            result.append(WalletUserSubRole(r))
        except ValueError:
            continue
    return result


class WalletUserSubResource(BaseResource):
    """Resource-схемы для субаккаунтов менеджера (WalletUserSub)."""

    class Create(BaseResource.Create):
        wallet_address: str = Field(..., max_length=255, description="Sub-account wallet address")
        blockchain: str = Field(..., max_length=20, description="Blockchain: tron, ethereum, etc.")
        nickname: Optional[str] = Field(default=None, max_length=100, description="Display name for sub-account")
        roles: Optional[List[WalletUserSubRole]] = Field(default=None, description="Roles: owner, operator, reader; default reader")
        is_blocked: Optional[bool] = Field(default=None, description="Whether the sub-account is blocked")

    class Patch(BaseResource.Patch):
        nickname: Optional[str] = Field(default=None, max_length=100)
        roles: Optional[List[WalletUserSubRole]] = Field(default=None, description="Roles: owner, operator, reader")
        is_blocked: Optional[bool] = Field(default=None, description="Whether the sub-account is blocked")

    class Get(BaseResource.Get):
        id: int
        wallet_user_id: int
        wallet_address: str
        blockchain: str
        nickname: Optional[str] = None
        roles: List[WalletUserSubRole]
        is_verified: bool
        is_blocked: bool
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


def _sub_model_to_get(model: WalletUserSub) -> WalletUserSubResource.Get:
    """Преобразует модель WalletUserSub в WalletUserSubResource.Get."""
    return WalletUserSubResource.Get(
        id=model.id,
        wallet_user_id=model.wallet_user_id,
        wallet_address=model.wallet_address,
        blockchain=model.blockchain,
        nickname=model.nickname,
        roles=_roles_str_to_enum(model.roles),
        is_verified=model.is_verified,
        is_blocked=model.is_blocked,
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

    async def list(
        self,
        offset: int,
        limit: int,
        *,
        search: Optional[str] = None,
        blockchain: Optional[str] = None,
    ) -> tuple[List[WalletUserResource.Get], int]:
        """
        Список с пагинацией. search — по wallet_address, nickname или id (простой LIKE/ILIKE).
        blockchain — точное совпадение. Возвращает (список, total).
        """
        stmt = select(WalletUser)
        count_stmt = select(func.count(WalletUser.id))
        if search and search.strip():
            term = f"%{search.strip()}%"
            cond = or_(
                WalletUser.wallet_address.ilike(term),
                WalletUser.nickname.ilike(term),
            )
            try:
                sid = int(search.strip())
                cond = or_(cond, WalletUser.id == sid)
            except ValueError:
                pass
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        if blockchain and blockchain.strip():
            bc = blockchain.strip().lower()
            stmt = stmt.where(WalletUser.blockchain == bc)
            count_stmt = count_stmt.where(WalletUser.blockchain == bc)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0
        stmt = stmt.order_by(WalletUser.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [_model_to_get(m) for m in rows], total

    async def create(self, data: WalletUserResource.Create) -> WalletUserResource.Get:
        """Create: создаёт пользователя. DID из data.did или генерируется при вставке (event listener)."""
        model = WalletUser(
            wallet_address=data.wallet_address,
            blockchain=data.blockchain,
            nickname=data.nickname,
            avatar=data.avatar,
            access_to_admin_panel=data.access_to_admin_panel,
            is_verified=data.is_verified,
            did=data.did,
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

    async def get_spaces_for_address(
        self, wallet_address: str, blockchain: str = "tron"
    ) -> List[str]:
        """
        Список space (nickname), в которых участвует адрес: свой WalletUser.nickname
        и nicknames родительских WalletUser для WalletUserSub с этим адресом.
        Порядок: сначала основной аккаунт, затем субаккаунты (родители).
        """
        seen: set = set()
        result_list: List[str] = []
        # 1) Main: WalletUser.nickname где wallet_address совпадает
        stmt_main = select(WalletUser.nickname).where(
            WalletUser.wallet_address == wallet_address
        )
        r_main = await self._session.execute(stmt_main)
        for (nick,) in r_main.all():
            if nick and nick not in seen:
                seen.add(nick)
                result_list.append(nick)
        # 2) Subs: родительские WalletUser.nickname по WalletUserSub
        stmt_subs = (
            select(WalletUser.nickname)
            .select_from(WalletUserSub)
            .join(WalletUser, WalletUserSub.wallet_user_id == WalletUser.id)
            .where(
                WalletUserSub.wallet_address == wallet_address,
                WalletUserSub.blockchain == blockchain,
            )
        )
        r_subs = await self._session.execute(stmt_subs)
        for (nick,) in r_subs.all():
            if nick and nick not in seen:
                seen.add(nick)
                result_list.append(nick)
        return result_list

    # --- Субаккаунты (WalletUserSub) ---

    async def list_subs(self, wallet_user_id: int) -> List[WalletUserSubResource.Get]:
        """Список субаккаунтов для родителя (менеджера) wallet_user_id."""
        stmt = (
            select(WalletUserSub)
            .where(WalletUserSub.wallet_user_id == wallet_user_id)
            .order_by(WalletUserSub.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [_sub_model_to_get(m) for m in result.scalars().all()]

    async def get_sub(
        self, wallet_user_id: int, sub_id: int
    ) -> Optional[WalletUserSubResource.Get]:
        """Субаккаунт по id, только если он принадлежит данному wallet_user_id."""
        stmt = select(WalletUserSub).where(
            WalletUserSub.id == sub_id,
            WalletUserSub.wallet_user_id == wallet_user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _sub_model_to_get(model) if model else None

    async def get_sub_by_address(
        self, wallet_user_id: int, wallet_address: str, blockchain: str
    ) -> Optional[WalletUserSubResource.Get]:
        """Субаккаунт по адресу и сети в рамках одного родителя."""
        stmt = select(WalletUserSub).where(
            WalletUserSub.wallet_user_id == wallet_user_id,
            WalletUserSub.wallet_address == wallet_address,
            WalletUserSub.blockchain == blockchain,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _sub_model_to_get(model) if model else None

    async def add_sub(
        self, wallet_user_id: int, data: WalletUserSubResource.Create
    ) -> WalletUserSubResource.Get:
        """Добавить субаккаунт родителю. При дубликате (wallet_address+blockchain) — исключение на уровне БД. Default roles = [reader]."""
        roles_raw = data.roles or [WalletUserSubRole.reader]
        roles_db = [r.value for r in roles_raw]
        is_blocked = getattr(data, "is_blocked", None)
        if is_blocked is None:
            is_blocked = False
        model = WalletUserSub(
            wallet_user_id=wallet_user_id,
            wallet_address=data.wallet_address,
            blockchain=data.blockchain,
            nickname=data.nickname,
            roles=roles_db,
            is_verified=False,
            is_blocked=is_blocked,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _sub_model_to_get(model)

    async def patch_sub(
        self,
        wallet_user_id: int,
        sub_id: int,
        data: WalletUserSubResource.Patch,
    ) -> Optional[WalletUserSubResource.Get]:
        """Частичное обновление субаккаунта (nickname, roles, is_blocked). Возвращает None, если суб не найден или не принадлежит родителю."""
        payload = data.model_dump(exclude_unset=True)
        allowed = {"nickname", "roles", "is_blocked"}
        values: dict = {}
        for k, v in payload.items():
            if k not in allowed:
                continue
            if k == "roles" and v is not None:
                # Normalize: unique enum values as strings
                seen: set = set()
                roles_db = []
                for r in v:
                    val = r.value if isinstance(r, WalletUserSubRole) else r
                    if val in ("owner", "operator", "reader") and val not in seen:
                        seen.add(val)
                        roles_db.append(val)
                values["roles"] = roles_db
            else:
                values[k] = v
        if not values:
            return await self.get_sub(wallet_user_id, sub_id)
        stmt = (
            update(WalletUserSub)
            .where(
                WalletUserSub.id == sub_id,
                WalletUserSub.wallet_user_id == wallet_user_id,
            )
            .values(**values)
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            return None
        return await self.get_sub(wallet_user_id, sub_id)

    async def delete_sub(self, wallet_user_id: int, sub_id: int) -> bool:
        """Удалить субаккаунт. True, если запись удалена и принадлежала данному wallet_user_id."""
        stmt = delete(WalletUserSub).where(
            WalletUserSub.id == sub_id,
            WalletUserSub.wallet_user_id == wallet_user_id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
