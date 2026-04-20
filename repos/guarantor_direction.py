"""
Репозиторий гаранта: направления (guarantor_directions) и профиль условий 1:1 (guarantor_profiles).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models import GuarantorDirection, GuarantorProfile
from repos.base import BaseRepository
from settings import Settings

logger = logging.getLogger(__name__)


def _strip(s: str | None) -> str:
    return (s or "").strip()


def _optional_text(s: str | None) -> str | None:
    if s is None:
        return None
    t = s.strip()
    return t if t else None


class GuarantorDirectionRepository(BaseRepository):
    """Направления гаранта по ``space`` и профиль ``(wallet_user_id, space)``."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session, redis, settings)

    async def list_for_space(self, space: str) -> list[GuarantorDirection]:
        sp = _strip(space)
        stmt = (
            select(GuarantorDirection)
            .where(GuarantorDirection.space == sp)
            .order_by(GuarantorDirection.sort_order.asc(), GuarantorDirection.id.asc())
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def get_by_id(self, direction_id: int, space: str) -> Optional[GuarantorDirection]:
        sp = _strip(space)
        stmt = select(GuarantorDirection).where(
            GuarantorDirection.id == direction_id,
            GuarantorDirection.space == sp,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def create(
        self,
        space: str,
        *,
        currency_code: str,
        payment_code: str,
        payment_name: str | None = None,
        conditions_text: str | None = None,
        commission_percent: Decimal | None = None,
        sort_order: int = 0,
    ) -> GuarantorDirection:
        row = GuarantorDirection(
            space=_strip(space),
            currency_code=_strip(currency_code),
            payment_code=_strip(payment_code),
            payment_name=_optional_text(payment_name),
            conditions_text=_optional_text(conditions_text),
            commission_percent=commission_percent,
            sort_order=sort_order,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def update(
        self,
        direction_id: int,
        space: str,
        *,
        currency_code: str | None = None,
        payment_code: str | None = None,
        payment_name: str | None = None,
        conditions_text: Any = ...,
        commission_percent: Any = ...,
        sort_order: int | None = None,
    ) -> Optional[GuarantorDirection]:
        """
        Частичное обновление. ``conditions_text`` / ``commission_percent``:
        передайте ``None`` чтобы обнулить; используйте ``...`` (пропуск) чтобы не менять поле.
        """
        row = await self.get_by_id(direction_id, space)
        if row is None:
            return None
        if currency_code is not None:
            row.currency_code = _strip(currency_code)
        if payment_code is not None:
            row.payment_code = _strip(payment_code)
        if payment_name is not None:
            row.payment_name = _strip(payment_name) if payment_name else None
        if conditions_text is not ...:
            row.conditions_text = conditions_text
        if commission_percent is not ...:
            row.commission_percent = commission_percent
        if sort_order is not None:
            row.sort_order = sort_order
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete(self, direction_id: int, space: str) -> bool:
        sp = _strip(space)
        stmt = delete(GuarantorDirection).where(
            GuarantorDirection.id == direction_id,
            GuarantorDirection.space == sp,
        )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0

    async def get_profile(
        self,
        wallet_user_id: int,
        space: str,
    ) -> Optional[GuarantorProfile]:
        """Одна строка профиля гаранта на пару пользователь + space или ``None``."""
        sp = _strip(space)
        stmt = select(GuarantorProfile).where(
            GuarantorProfile.wallet_user_id == wallet_user_id,
            GuarantorProfile.space == sp,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_profile_by_arbiter_public_slug(
        self, slug: str
    ) -> Optional[GuarantorProfile]:
        """Профиль по публичному slug (уже lower-case)."""
        s = _strip(slug).lower()
        if not s:
            return None
        stmt = select(GuarantorProfile).where(GuarantorProfile.arbiter_public_slug == s)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def upsert_profile(
        self,
        wallet_user_id: int,
        space: str,
        *,
        commission_percent: Any = ...,
        conditions_text: Any = ...,
        arbiter_public_slug: Any = ...,
    ) -> GuarantorProfile:
        """
        Создаёт или обновляет профиль гаранта. Поля с ``...`` не меняют существующее значение;
        при создании для них подставляется ``None``.
        """
        row = await self.get_profile(wallet_user_id, space)
        sp = _strip(space)
        if row is None:
            comm_new = commission_percent if commission_percent is not ... else None
            cond_new: str | None = None
            if conditions_text is not ...:
                cond_new = _optional_text(conditions_text)
            slug_new: str | None = None
            if arbiter_public_slug is not ...:
                slug_new = arbiter_public_slug
            row = GuarantorProfile(
                wallet_user_id=wallet_user_id,
                space=sp,
                commission_percent=comm_new,
                conditions_text=cond_new,
                arbiter_public_slug=slug_new,
            )
            self._session.add(row)
            await self._session.flush()
            await self._session.refresh(row)
            return row
        if commission_percent is not ...:
            row.commission_percent = commission_percent
        if conditions_text is not ...:
            row.conditions_text = (
                _optional_text(conditions_text) if conditions_text is not None else None
            )
        if arbiter_public_slug is not ...:
            row.arbiter_public_slug = arbiter_public_slug
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete_profile(self, wallet_user_id: int, space: str) -> bool:
        """Удаляет профиль гаранта для пары пользователь + space."""
        sp = _strip(space)
        stmt = delete(GuarantorProfile).where(
            GuarantorProfile.wallet_user_id == wallet_user_id,
            GuarantorProfile.space == sp,
        )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0
