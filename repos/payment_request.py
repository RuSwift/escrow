"""Репозиторий заявок PaymentRequest (Simple UI)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PaymentRequest, WalletUser
from repos.base import BaseRepository
from settings import Settings


class PaymentRequestRepository(BaseRepository):
    async def insert(
        self,
        *,
        uid: str,
        public_ref: str,
        space_id: int,
        owner_did: str,
        direction: str,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
        primary_ramp_wallet_id: Optional[int],
        heading: Optional[str],
        expires_at: Optional[datetime],
        arbiter_did: str,
        commissioners: Optional[Dict[str, Any]] = None,
    ) -> PaymentRequest:
        row = PaymentRequest(
            uid=uid,
            public_ref=public_ref,
            commissioners=commissioners if commissioners is not None else {},
            space_id=space_id,
            owner_did=owner_did,
            arbiter_did=arbiter_did,
            direction=direction,
            primary_leg=primary_leg,
            counter_leg=counter_leg,
            primary_ramp_wallet_id=primary_ramp_wallet_id,
            heading=heading,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    def _owner_filters(
        self, owner_did: str, arbiter_did: str, q: Optional[str]
    ) -> List[Any]:
        base: List[Any] = [
            PaymentRequest.owner_did == owner_did,
            PaymentRequest.arbiter_did == arbiter_did,
        ]
        if q and (needle := q.strip()):
            pat = f"%{needle}%"
            base.append(
                or_(
                    PaymentRequest.direction.ilike(pat),
                    func.cast(PaymentRequest.primary_leg, String).ilike(pat),
                    func.cast(PaymentRequest.counter_leg, String).ilike(pat),
                    PaymentRequest.space_id.in_(
                        select(WalletUser.id).where(WalletUser.nickname.ilike(pat))
                    ),
                    func.coalesce(PaymentRequest.heading, "").ilike(pat),
                )
            )
        return base

    async def list_for_owner(
        self,
        owner_did: str,
        arbiter_did: str,
        *,
        page: int,
        page_size: int,
        q: Optional[str],
    ) -> Tuple[List[Tuple[PaymentRequest, str]], int]:
        offset = max(0, (page - 1) * page_size)
        filters = self._owner_filters(owner_did, arbiter_did, q)

        count_stmt = select(func.count()).select_from(PaymentRequest).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one() or 0)

        list_stmt = (
            select(PaymentRequest, WalletUser.nickname)
            .join(WalletUser, PaymentRequest.space_id == WalletUser.id)
            .where(*filters)
            .order_by(PaymentRequest.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        raw = (await self._session.execute(list_stmt)).all()
        rows = [(r[0], str(r[1])) for r in raw]
        return rows, total

    async def get_by_uid(
        self,
        uid: str,
        *,
        arbiter_did: Optional[str] = None,
    ) -> Optional[Tuple[PaymentRequest, str]]:
        """Публичная заявка по hex uid или по public_ref (без фильтра по владельцу)."""
        raw = (uid or "").strip()
        if not raw:
            return None
        uid_norm = raw.lower()
        conds: List[Any] = [
            or_(
                func.lower(PaymentRequest.uid) == uid_norm,
                func.lower(PaymentRequest.public_ref) == uid_norm,
            )
        ]
        if arbiter_did is not None and (arbiter_did or "").strip():
            conds.append(PaymentRequest.arbiter_did == (arbiter_did or "").strip())
        stmt = (
            select(PaymentRequest, WalletUser.nickname)
            .join(WalletUser, PaymentRequest.space_id == WalletUser.id)
            .where(*conds)
        )
        res = await self._session.execute(stmt)
        row = res.first()
        if row is None:
            return None
        return row[0], str(row[1])

    async def deactivate_for_owner(
        self,
        owner_did: str,
        arbiter_did: str,
        pk: int,
        confirm_text: str,
    ) -> Optional[Tuple[PaymentRequest, str]]:
        """Деактивация по совпадению введённого номера с pk; возвращает (row, nickname)."""
        if (confirm_text or "").strip() != str(pk).strip():
            raise ValueError("confirm_mismatch")
        stmt = (
            select(PaymentRequest, WalletUser.nickname)
            .join(WalletUser, PaymentRequest.space_id == WalletUser.id)
            .where(PaymentRequest.pk == pk)
            .where(PaymentRequest.owner_did == owner_did)
            .where(PaymentRequest.arbiter_did == arbiter_did)
        )
        res = await self._session.execute(stmt)
        row = res.first()
        if row is None:
            return None
        pr, nick = row[0], str(row[1])
        if pr.deactivated_at is not None:
            raise ValueError("already_deactivated")
        pr.deactivated_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(pr)
        return pr, nick
