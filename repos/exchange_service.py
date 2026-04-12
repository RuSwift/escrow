"""Репозиторий конфигураций обмена (exchange_services) и сетки комиссий."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models import ExchangeService, ExchangeServiceFeeTier
from repos.base import BaseRepository
from settings import Settings


def _strip_space(s: str | None) -> str:
    return (s or "").strip()


class ExchangeServiceRepository(BaseRepository):
    """CRUD exchange_services + fee tiers в разрезе ``space``."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session, redis, settings)

    async def list_for_space(
        self,
        space: str,
        *,
        include_deleted: bool = False,
    ) -> list[ExchangeService]:
        sp = _strip_space(space)
        if not sp:
            return []
        stmt = select(ExchangeService).where(ExchangeService.space == sp)
        if not include_deleted:
            stmt = stmt.where(ExchangeService.is_deleted.is_(False))
        stmt = stmt.order_by(
            ExchangeService.service_type.asc(),
            ExchangeService.fiat_currency_code.asc(),
            ExchangeService.id.asc(),
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def get_by_id(
        self,
        service_id: int,
        space: str,
        *,
        include_deleted: bool = False,
    ) -> Optional[ExchangeService]:
        sp = _strip_space(space)
        stmt = select(ExchangeService).where(
            ExchangeService.id == service_id,
            ExchangeService.space == sp,
        )
        if not include_deleted:
            stmt = stmt.where(ExchangeService.is_deleted.is_(False))
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_titles_for_space_wallet(
        self,
        space: str,
        wallet_id: int,
    ) -> list[str]:
        """Заголовки неудалённых направлений, привязанных к корп. кошельку."""
        sp = _strip_space(space)
        if not sp or wallet_id <= 0:
            return []
        stmt = (
            select(ExchangeService.title)
            .where(
                ExchangeService.space == sp,
                ExchangeService.space_wallet_id == wallet_id,
                ExchangeService.is_deleted.is_(False),
            )
            .order_by(ExchangeService.title.asc())
        )
        res = await self._session.execute(stmt)
        rows = res.scalars().all()
        out: list[str] = []
        for t in rows:
            s = (t or "").strip()
            if s:
                out.append(s)
        return out

    async def list_fee_tiers(
        self, exchange_service_id: int
    ) -> list[ExchangeServiceFeeTier]:
        stmt = (
            select(ExchangeServiceFeeTier)
            .where(
                ExchangeServiceFeeTier.exchange_service_id == exchange_service_id,
            )
            .order_by(
                ExchangeServiceFeeTier.sort_order.asc(),
                ExchangeServiceFeeTier.id.asc(),
            )
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def replace_fee_tiers(
        self,
        exchange_service_id: int,
        tiers: list[dict[str, Any]],
    ) -> None:
        await self._session.execute(
            delete(ExchangeServiceFeeTier).where(
                ExchangeServiceFeeTier.exchange_service_id == exchange_service_id
            )
        )
        for i, t in enumerate(tiers):
            row = ExchangeServiceFeeTier(
                exchange_service_id=exchange_service_id,
                fiat_min=t["fiat_min"],
                fiat_max=t["fiat_max"],
                fee_percent=t["fee_percent"],
                sort_order=int(t.get("sort_order", i)),
            )
            self._session.add(row)
        await self._session.flush()

    async def create(
        self,
        *,
        space: str,
        row_fields: dict[str, Any],
        fee_tiers: Optional[list[dict[str, Any]]] = None,
    ) -> ExchangeService:
        sp = _strip_space(space)
        row = ExchangeService(space=sp, **row_fields)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        if fee_tiers:
            await self.replace_fee_tiers(row.id, fee_tiers)
        await self._session.refresh(row)
        return row

    async def update(
        self,
        service_id: int,
        space: str,
        *,
        fields: dict[str, Any],
        fee_tiers: Optional[list[dict[str, Any]]] = None,
        replace_tiers: bool = False,
    ) -> Optional[ExchangeService]:
        row = await self.get_by_id(service_id, space, include_deleted=True)
        if row is None or row.is_deleted:
            return None
        for k, v in fields.items():
            setattr(row, k, v)
        await self._session.flush()
        if replace_tiers:
            await self.replace_fee_tiers(service_id, fee_tiers or [])
        await self._session.refresh(row)
        return row

    async def soft_delete(self, service_id: int, space: str) -> bool:
        sp = _strip_space(space)
        stmt = (
            update(ExchangeService)
            .where(
                ExchangeService.id == service_id,
                ExchangeService.space == sp,
                ExchangeService.is_deleted.is_(False),
            )
            .values(is_deleted=True, is_active=False)
        )
        res = await self._session.execute(stmt)
        return res.rowcount > 0
