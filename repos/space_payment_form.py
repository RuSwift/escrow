"""Переопределения форм реквизитов по payment_code в разрезе space."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models import SpacePaymentFormOverride
from repos.base import BaseRepository
from settings import Settings


def _strip_space(s: str | None) -> str:
    return (s or "").strip()


def _strip_payment_code(s: str | None) -> str:
    return (s or "").strip()


class SpacePaymentFormOverrideRepository(BaseRepository):
    """CRUD для ``space_payment_form_overrides``."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session, redis, settings)

    async def get(
        self, space: str, payment_code: str
    ) -> Optional[SpacePaymentFormOverride]:
        sp = _strip_space(space)
        pc = _strip_payment_code(payment_code)
        if not sp or not pc:
            return None
        stmt = select(SpacePaymentFormOverride).where(
            SpacePaymentFormOverride.space == sp,
            SpacePaymentFormOverride.payment_code == pc,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_for_space(self, space: str) -> list[SpacePaymentFormOverride]:
        sp = _strip_space(space)
        if not sp:
            return []
        stmt = (
            select(SpacePaymentFormOverride)
            .where(SpacePaymentFormOverride.space == sp)
            .order_by(
                SpacePaymentFormOverride.payment_code.asc(),
                SpacePaymentFormOverride.id.asc(),
            )
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def upsert(
        self,
        space: str,
        payment_code: str,
        *,
        form: dict,
    ) -> SpacePaymentFormOverride:
        sp = _strip_space(space)
        pc = _strip_payment_code(payment_code)
        row = await self.get(sp, pc)
        if row is None:
            row = SpacePaymentFormOverride(space=sp, payment_code=pc, form=form)
            self._session.add(row)
        else:
            row.form = form
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def delete(self, space: str, payment_code: str) -> bool:
        sp = _strip_space(space)
        pc = _strip_payment_code(payment_code)
        if not sp or not pc:
            return False
        stmt = delete(SpacePaymentFormOverride).where(
            SpacePaymentFormOverride.space == sp,
            SpacePaymentFormOverride.payment_code == pc,
        )
        res = await self._session.execute(stmt)
        return res.rowcount > 0
