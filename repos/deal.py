"""Репозиторий сделок (deal) для Simple-заявок и общего доступа."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Deal
from repos.base import BaseRepository
from settings import Settings


class DealRepository(BaseRepository):
    """CRUD по таблице deal."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session=session, redis=redis, settings=settings)

    async def insert_simple_application(
        self,
        *,
        uid: str,
        sender_did: str,
        receiver_did: str,
        arbiter_did: str,
        label: str,
        description: Optional[str],
        amount: Optional[Decimal],
        requisites: Dict[str, Any],
        status: str = "wait_deposit",
    ) -> Deal:
        row = Deal(
            uid=uid,
            sender_did=sender_did,
            receiver_did=receiver_did,
            arbiter_did=arbiter_did,
            label=label,
            description=description,
            amount=amount,
            requisites=requisites,
            status=status,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    def _simple_sender_filters(
        self, sender_did: str, q: Optional[str]
    ) -> List[Any]:
        base: List[Any] = [
            Deal.sender_did == sender_did,
            Deal.requisites.contains({"simple_application": True}),
        ]
        if q and (needle := q.strip()):
            pat = f"%{needle}%"
            base.append(
                or_(
                    Deal.label.ilike(pat),
                    Deal.description.ilike(pat),
                    Deal.status.ilike(pat),
                    func.cast(Deal.requisites, String).ilike(pat),
                )
            )
        return base

    async def list_simple_applications_for_sender(
        self,
        sender_did: str,
        *,
        page: int,
        page_size: int,
        q: Optional[str],
    ) -> Tuple[List[Deal], int]:
        offset = max(0, (page - 1) * page_size)
        filters = self._simple_sender_filters(sender_did, q)

        count_stmt = select(func.count()).select_from(Deal).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one() or 0)

        list_stmt = (
            select(Deal)
            .where(*filters)
            .order_by(Deal.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self._session.execute(list_stmt)).scalars().all()
        return list(rows), total
