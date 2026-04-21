"""Разрешение публичного uid для Simple UI: PaymentRequest или Deal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Deal, PaymentRequest
from repos.deal import DealRepository
from repos.payment_request import (
    PaymentRequestRepository,
    PaymentRequestResolveSegment,
)
from settings import Settings


@dataclass(frozen=True)
class ResolvedPaymentRequest:
    """Найденная заявка и nickname спейса для PaymentRequestOut."""

    row: PaymentRequest
    space_nickname: str
    segment: PaymentRequestResolveSegment


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

    async def resolve_public_uid(
        self, public_uid: str, arbiter_space_did: str
    ) -> Optional[ResolveResult]:
        """Сегмент пути: hex uid заявки, public_ref заявки или uid сделки; контекст arbiter_space_did."""
        raw = (public_uid or "").strip()
        arb = (arbiter_space_did or "").strip()
        if not raw or not arb:
            return None

        pr_triple = await self._pr.resolve_segment_to_payment_request(
            raw, arbiter_did=arb
        )
        if pr_triple is not None:
            row, nick, segment = pr_triple
            return ResolvedPaymentRequest(
                row=row, space_nickname=nick, segment=segment
            )

        deal_row = await self._deal.get_by_uid(raw)
        if deal_row is not None:
            if (deal_row.arbiter_did or "").strip() != arb:
                return None
            return ResolvedDeal(row=deal_row)
        return None
