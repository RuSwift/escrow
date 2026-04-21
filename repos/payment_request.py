"""Репозиторий заявок PaymentRequest (Simple UI)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy import String, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PaymentRequest, WalletUser
from repos.base import BaseRepository
from settings import Settings


@dataclass(frozen=True)
class PaymentRequestResolveSegment:
    """Как URL-сегмент сопоставился заявке (для auto-resell: родитель в графе комиссионеров)."""

    match_kind: Literal["uid", "column_public_ref", "commissioner_alias"]
    commissioner_parent_ref: Optional[str] = None


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

    def _q_text_filter(self, q: Optional[str]) -> List[Any]:
        if not q or not (needle := q.strip()):
            return []
        pat = f"%{needle}%"
        return [
            or_(
                PaymentRequest.direction.ilike(pat),
                func.cast(PaymentRequest.primary_leg, String).ilike(pat),
                func.cast(PaymentRequest.counter_leg, String).ilike(pat),
                PaymentRequest.space_id.in_(
                    select(WalletUser.id).where(WalletUser.nickname.ilike(pat))
                ),
                func.coalesce(PaymentRequest.heading, "").ilike(pat),
            )
        ]

    def _owner_filters(
        self, owner_did: str, arbiter_did: str, q: Optional[str]
    ) -> List[Any]:
        base: List[Any] = [
            PaymentRequest.owner_did == owner_did,
            PaymentRequest.arbiter_did == arbiter_did,
        ]
        base.extend(self._q_text_filter(q))
        return base

    async def list_for_owner_or_commissioner(
        self,
        viewer_did: str,
        arbiter_did: str,
        *,
        page: int,
        page_size: int,
        q: Optional[str],
    ) -> Tuple[List[Tuple[PaymentRequest, str]], int]:
        """Заявки где viewer — владелец или DID в commissioners (не system)."""
        offset = max(0, (page - 1) * page_size)
        vd = (viewer_did or "").strip()
        arb = (arbiter_did or "").strip()

        commissioner_exists = text(
            "EXISTS (SELECT 1 FROM jsonb_each(payment_request.commissioners) "
            "AS jc(slot_key, slot_val) WHERE "
            "lower(trim(COALESCE(slot_val->>'did',''))) = lower(:viewer_did) "
            "AND COALESCE(lower(trim(slot_val->>'role')), '') != :sysrole)"
        ).bindparams(viewer_did=vd, sysrole="system")

        owner_or_comm = or_(
            PaymentRequest.owner_did == vd,
            commissioner_exists,
        )
        filters: List[Any] = [
            PaymentRequest.arbiter_did == arb,
            owner_or_comm,
        ]
        filters.extend(self._q_text_filter(q))

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

    async def alias_public_ref_exists_anywhere(self, alias_norm_lower: str) -> bool:
        """True если ref занят колонкой public_ref или любым alias_public_ref в commissioners."""
        a = (alias_norm_lower or "").strip().lower()
        if not a:
            return False
        col = (
            await self._session.execute(
                select(func.count()).select_from(PaymentRequest).where(
                    func.lower(PaymentRequest.public_ref) == a,
                ),
            )
        ).scalar_one()
        if int(col or 0) > 0:
            return True
        json_alias = text(
            "EXISTS (SELECT 1 FROM jsonb_each(payment_request.commissioners) "
            "AS je(k, v) WHERE lower(trim(COALESCE(v->>'alias_public_ref',''))) = :xref)"
        ).bindparams(xref=a)
        row = (
            await self._session.execute(
                select(func.count()).select_from(PaymentRequest).where(json_alias),
            )
        ).scalar_one()
        return int(row or 0) > 0

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

    async def resolve_segment_to_payment_request(
        self,
        uid: str,
        *,
        arbiter_did: Optional[str] = None,
    ) -> Optional[Tuple[PaymentRequest, str, PaymentRequestResolveSegment]]:
        """Публичная заявка по uid, column public_ref или alias_public_ref слота + метаданные матча."""
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
        if row is not None:
            pr, nick = row[0], str(row[1])
            uid_l = (pr.uid or "").strip().lower()
            pub_l = (pr.public_ref or "").strip().lower()
            if uid_norm == uid_l:
                seg = PaymentRequestResolveSegment("uid", None)
            elif uid_norm == pub_l:
                seg = PaymentRequestResolveSegment("column_public_ref", None)
            else:
                seg = PaymentRequestResolveSegment("column_public_ref", None)
            return pr, nick, seg

        conds_alias: List[Any] = [
            text(
                "EXISTS (SELECT 1 FROM jsonb_each(payment_request.commissioners) "
                "AS ae(k,v) WHERE lower(trim(COALESCE(v->>'alias_public_ref',''))) "
                "= :uid_n)"
            ).bindparams(uid_n=uid_norm),
        ]
        if arbiter_did is not None and (arbiter_did or "").strip():
            conds_alias.append(PaymentRequest.arbiter_did == (arbiter_did or "").strip())
        stmt_alias = (
            select(PaymentRequest, WalletUser.nickname)
            .join(WalletUser, PaymentRequest.space_id == WalletUser.id)
            .where(*conds_alias)
        )
        res = await self._session.execute(stmt_alias)
        row = res.first()
        if row is None:
            return None
        pr, nick = row[0], str(row[1])
        rc = pr.commissioners if isinstance(pr.commissioners, dict) else {}
        exact_alias: Optional[str] = None
        for slot in rc.values():
            if not isinstance(slot, dict):
                continue
            ar = (slot.get("alias_public_ref") or "").strip()
            if ar.lower() == uid_norm:
                exact_alias = ar
                break
        seg = PaymentRequestResolveSegment(
            "commissioner_alias",
            exact_alias if exact_alias is not None else raw,
        )
        return pr, nick, seg

    async def get_by_uid(
        self,
        uid: str,
        *,
        arbiter_did: Optional[str] = None,
    ) -> Optional[Tuple[PaymentRequest, str]]:
        """Публичная заявка по hex uid или по public_ref (без фильтра по владельцу)."""
        triple = await self.resolve_segment_to_payment_request(
            uid, arbiter_did=arbiter_did
        )
        if triple is None:
            return None
        return triple[0], triple[1]

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
