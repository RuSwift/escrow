"""Репозиторий Deal — чтение по uid для Simple resolve."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Deal
from repos.base import BaseRepository
from settings import Settings


class DealRepository(BaseRepository):
    """Чтение сделок; Simple-заявки в PaymentRequestRepository."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session=session, redis=redis, settings=settings)

    async def create_from_simple_payment_request(
        self,
        *,
        sender_did: str,
        receiver_did: str,
        arbiter_did: str,
        label: str,
        signers: Optional[Dict[str, Any]] = None,
    ) -> Deal:
        """Минимальная сделка после подтверждения владельцем Simple-заявки."""
        uid = uuid.uuid4().hex
        deal = Deal(
            uid=uid,
            sender_did=(sender_did or "").strip(),
            receiver_did=(receiver_did or "").strip(),
            arbiter_did=(arbiter_did or "").strip(),
            label=(label or "").strip() or "—",
            status="wait_deposit",
            signers=signers if signers else None,
        )
        self._session.add(deal)
        await self._session.flush()
        await self._session.refresh(deal)
        return deal

    async def get_by_uid(self, uid: str) -> Optional[Deal]:
        """Сделка по публичному uid (уникальная ссылка)."""
        u = (uid or "").strip()
        if not u:
            return None
        stmt = select(Deal).where(Deal.uid == u)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()
