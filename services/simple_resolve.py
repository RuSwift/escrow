"""Разрешение публичного uid для Simple UI: PaymentRequest или Deal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Deal, PaymentRequest
from repos.deal import DealRepository
from repos.payment_request import PaymentRequestRepository
from settings import Settings


@dataclass(frozen=True)
class ResolvedPaymentRequest:
    """Найденная заявка и nickname спейса для PaymentRequestOut."""

    row: PaymentRequest
    space_nickname: str


@dataclass(frozen=True)
class ResolvedDeal:
    """Найденная сделка."""

    row: Deal


ResolveResult = Union[ResolvedPaymentRequest, ResolvedDeal]


class SimpleResolveService:
    """Чтение контекста по ссылке без фильтра владельца заявки / участников сделки."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._pr = PaymentRequestRepository(
            session=session, redis=redis, settings=settings
        )
        self._deal = DealRepository(session=session, redis=redis, settings=settings)

    async def resolve_public_uid(self, public_uid: str) -> Optional[ResolveResult]:
        raw = (public_uid or "").strip()
        if not raw:
            return None

        pr_pair = await self._pr.get_by_uid(raw)
        if pr_pair is not None:
            row, nick = pr_pair
            return ResolvedPaymentRequest(row=row, space_nickname=nick)

        deal_row = await self._deal.get_by_uid(raw)
        if deal_row is not None:
            return ResolvedDeal(row=deal_row)
        return None
