"""Заявки PaymentRequest (Simple UI): fiat↔stable до создания Deal."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.short_id import generate_public_ref
from db.models import PaymentRequest
from repos.payment_request import PaymentRequestRepository, PaymentRequestResolveSegment
from services.exchange_wallets import ExchangeWalletService
from services.payment_request_commission_graph import (
    build_slot_snapshots,
    build_slot_snapshots_for_pr,
    intermediary_slot_keys_for_did,
    is_intermediary_commission_slot,
)
from services.space import SpaceService
from services.wallet_user import WalletUserService
from settings import Settings

logger = logging.getLogger(__name__)

_SIMPLE_PR_UNIQUE_RETRIES = 24
_ALIAS_UNIQUE_RETRIES = 24

SimpleDirection = Literal["fiat_to_stable", "stable_to_fiat"]
SimplePaymentLifetime = Literal["24h", "48h", "72h", "forever"]

SYSTEM_SLOT_KEY = "system"


class PaymentRequestService:
    """Simple-заявки без space в URL (space из auth); Deal создаётся позже при принятии."""

    _RESELL_PCT_MIN = Decimal("0.1")
    _RESELL_PCT_MAX = Decimal("100")

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._requests = PaymentRequestRepository(
            session=session, redis=redis, settings=settings
        )
        self._space = SpaceService(session=session, redis=redis, settings=settings)
        self._wallet_users = WalletUserService(
            session=session, redis=redis, settings=settings
        )
        self._exchange = ExchangeWalletService(
            session=session, redis=redis, settings=settings
        )

    def _blockchain_for_standard(self, standard: str) -> str:
        s = (standard or "").strip().lower()
        if s == "tron":
            return "tron"
        if s == "web3":
            return "ethereum"
        return "tron"

    @staticmethod
    def _format_percent_decimal(d: Decimal) -> str:
        q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        t = format(q, "f")
        if "." in t:
            t = t.rstrip("0").rstrip(".")
        return t or "0"

    async def _generate_unique_alias_public_ref(self) -> str:
        for attempt in range(_ALIAS_UNIQUE_RETRIES):
            ref = generate_public_ref()
            exists = await self._requests.alias_public_ref_exists_anywhere(ref.lower())
            if not exists:
                return ref
            if attempt + 1 == _ALIAS_UNIQUE_RETRIES:
                raise RuntimeError("Could not allocate unique alias_public_ref")
        raise RuntimeError("Could not allocate unique alias_public_ref")

    async def ensure_commissioner_view(
        self,
        row: PaymentRequest,
        viewer_did: str,
    ) -> None:
        """Для не-system слота комиссионера: создать alias_public_ref и снимки при отсутствии."""
        vd = (viewer_did or "").strip()
        owner = (row.owner_did or "").strip()
        if not vd or vd == owner:
            return

        raw_comm = row.commissioners
        comm = dict(raw_comm) if isinstance(raw_comm, dict) else {}
        keys_for_viewer: List[str] = []
        for sk, slot in comm.items():
            if not isinstance(slot, dict):
                continue
            if (slot.get("did") or "").strip() != vd:
                continue
            if str(slot.get("role") or "").strip().lower() == SYSTEM_SLOT_KEY:
                continue
            if not is_intermediary_commission_slot(sk, slot):
                continue
            keys_for_viewer.append(sk)

        if not keys_for_viewer:
            return

        changed = False
        for target_key in sorted(keys_for_viewer):
            slot_obj = dict(comm[target_key])
            if (slot_obj.get("alias_public_ref") or "").strip():
                continue

            alias = await self._generate_unique_alias_public_ref()
            slot_obj["alias_public_ref"] = alias

            snaps = build_slot_snapshots_for_pr(row, [target_key])
            if target_key in snaps:
                slot_obj["payment_amount"] = snaps[target_key]["payment_amount"]
                slot_obj["borrow_amount"] = snaps[target_key]["borrow_amount"]

            comm[target_key] = slot_obj
            changed = True

        if not changed:
            return

        root_ref = str(getattr(row, "public_ref", "") or "")
        from web.endpoints.v1.schemas.payment_request_commissioners import (
            CommissionersPayload,
            validate_commissioners_parent_refs,
        )

        validate_commissioners_parent_refs(comm, root_public_ref=root_ref)
        CommissionersPayload.model_validate(comm)

        row.commissioners = comm
        await self._session.flush()
        await self._session.refresh(row)

    async def _build_commissioners_for_create(
        self,
        *,
        root_public_ref: str,
        direction: SimpleDirection,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
        blockchain: str,
    ) -> Dict[str, Any]:
        cw = self._settings.commission_wallet
        addr = (cw.address_for_blockchain(blockchain) or "").strip()
        if not addr:
            return {}

        pct_str = self._format_percent_decimal(cw.percent)
        sys_alias = await self._generate_unique_alias_public_ref()
        system_slot: Dict[str, Any] = {
            "did": "system",
            "role": SYSTEM_SLOT_KEY,
            "commission": {"kind": "percent", "value": pct_str},
            "parent_id": root_public_ref,
            "alias_public_ref": sys_alias,
            "payout_address": addr,
        }
        comm = {SYSTEM_SLOT_KEY: system_slot}
        snaps = build_slot_snapshots(
            str(direction),
            primary_leg,
            counter_leg,
            comm,
            [SYSTEM_SLOT_KEY],
        )
        if SYSTEM_SLOT_KEY in snaps:
            system_slot["payment_amount"] = snaps[SYSTEM_SLOT_KEY]["payment_amount"]
            system_slot["borrow_amount"] = snaps[SYSTEM_SLOT_KEY]["borrow_amount"]

        from web.endpoints.v1.schemas.payment_request_commissioners import (
            CommissionersPayload,
            validate_commissioners_parent_refs,
        )

        validate_commissioners_parent_refs(comm, root_public_ref=root_public_ref)
        CommissionersPayload.model_validate(comm)
        return comm

    async def list_payment_requests(
        self,
        *,
        wallet_address: str,
        owner_did: str,
        standard: str,
        arbiter_did: str,
        page: int,
        page_size: int,
        q: Optional[str],
    ) -> Tuple[List[Tuple[PaymentRequest, str]], int]:
        bc = self._blockchain_for_standard(standard)
        pair = await self._wallet_users.resolve_primary_space_nickname_and_id(
            wallet_address, bc
        )
        if not pair:
            raise ValueError("No space for this wallet")
        space_nick, _ = pair
        await self._space.ensure_owner_or_operator(space_nick, wallet_address)

        rows, total = await self._requests.list_for_owner_or_commissioner(
            (owner_did or "").strip(),
            (arbiter_did or "").strip(),
            page=page,
            page_size=page_size,
            q=q,
        )
        out_rows: List[Tuple[PaymentRequest, str]] = []
        for r, nick in rows:
            await self.ensure_commissioner_view(r, owner_did)
            out_rows.append((r, nick))
        return out_rows, total

    async def deactivate_payment_request(
        self,
        *,
        wallet_address: str,
        owner_did: str,
        standard: str,
        arbiter_did: str,
        pk: int,
        confirm_pk: str,
    ) -> Tuple[PaymentRequest, str]:
        bc = self._blockchain_for_standard(standard)
        pair = await self._wallet_users.resolve_primary_space_nickname_and_id(
            wallet_address, bc
        )
        if not pair:
            raise ValueError("No space for this wallet")
        space_nick, _ = pair
        await self._space.ensure_owner_or_operator(space_nick, wallet_address)

        try:
            out = await self._requests.deactivate_for_owner(
                owner_did,
                (arbiter_did or "").strip(),
                pk,
                confirm_pk,
            )
        except ValueError as e:
            msg = str(e)
            if msg == "confirm_mismatch":
                raise ValueError("Номер заявки не совпадает") from None
            if msg == "already_deactivated":
                raise ValueError("Заявка уже деактивирована") from None
            raise

        if out is None:
            raise ValueError("Заявка не найдена")

        row, nick = out
        await self._session.commit()
        await self._session.refresh(row)
        return row, nick

    @staticmethod
    def _expires_at_for_lifetime(lifetime: SimplePaymentLifetime) -> Optional[datetime]:
        now = datetime.now(timezone.utc)
        if lifetime == "forever":
            return None
        if lifetime == "24h":
            return now + timedelta(hours=24)
        if lifetime == "48h":
            return now + timedelta(hours=48)
        return now + timedelta(hours=72)

    async def create_payment_request(
        self,
        *,
        wallet_address: str,
        owner_did: str,
        standard: str,
        arbiter_did: str,
        direction: SimpleDirection,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
        heading: Optional[str] = None,
        lifetime: SimplePaymentLifetime = "72h",
    ) -> Tuple[PaymentRequest, str]:
        bc = self._blockchain_for_standard(standard)
        pair = await self._wallet_users.resolve_primary_space_nickname_and_id(
            wallet_address, bc
        )
        if not pair:
            raise ValueError("No space for this wallet")
        space_nick, space_id = pair

        arb = (arbiter_did or "").strip()
        if not arb:
            raise ValueError("arbiter_did is required")

        await self._space.ensure_owner_or_operator(space_nick, wallet_address)

        self._validate_simple_legs(direction, primary_leg, counter_leg)
        h = (heading or "").strip()
        heading_val: Optional[str] = h if h else None

        ramp_wallet_id = await self._exchange.primary_ramp_wallet_id_for_space(
            space_nick, wallet_address
        )

        expires_at = self._expires_at_for_lifetime(lifetime)

        uid = uuid.uuid4().hex
        for attempt in range(_SIMPLE_PR_UNIQUE_RETRIES):
            public_ref = generate_public_ref()
            commissioners_payload = await self._build_commissioners_for_create(
                root_public_ref=public_ref,
                direction=direction,
                primary_leg=primary_leg,
                counter_leg=counter_leg,
                blockchain=bc,
            )
            try:
                row = await self._requests.insert(
                    uid=uid,
                    public_ref=public_ref,
                    space_id=space_id,
                    owner_did=owner_did,
                    arbiter_did=arb,
                    direction=direction,
                    primary_leg=primary_leg,
                    counter_leg=counter_leg,
                    primary_ramp_wallet_id=ramp_wallet_id,
                    heading=heading_val,
                    expires_at=expires_at,
                    commissioners=commissioners_payload,
                )
                await self._session.commit()
                await self._session.refresh(row)
            except IntegrityError:
                await self._session.rollback()
                if attempt + 1 == _SIMPLE_PR_UNIQUE_RETRIES:
                    raise
                continue
            logger.info(
                "PaymentRequest created uid=%s public_ref=%s space_id=%s space_nick=%s owner=%s arbiter=%s",
                uid,
                public_ref,
                space_id,
                space_nick,
                owner_did,
                arb,
            )
            return row, space_nick
        raise RuntimeError("PaymentRequest insert failed")

    @staticmethod
    def build_pair_label(
        direction: SimpleDirection,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
    ) -> str:
        a = PaymentRequestService._leg_code(primary_leg)
        b = PaymentRequestService._leg_code(counter_leg)
        return f"{a} — {b}"

    @staticmethod
    def _leg_code(leg: Dict[str, Any]) -> str:
        return str((leg or {}).get("code") or "").strip().upper()

    @staticmethod
    def _leg_amount_str(leg: Dict[str, Any]) -> Optional[str]:
        raw = (leg or {}).get("amount")
        if raw is None:
            return None
        s = str(raw).strip()
        return s if s else None

    def primary_amount_decimal(self, primary_leg: Dict[str, Any]) -> Optional[Decimal]:
        s = self._leg_amount_str(primary_leg)
        if not s:
            return None
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    def _validate_simple_legs(
        self,
        direction: SimpleDirection,
        primary_leg: Dict[str, Any],
        counter_leg: Dict[str, Any],
    ) -> None:
        if direction not in ("fiat_to_stable", "stable_to_fiat"):
            raise ValueError("Invalid direction")
        for name, leg in (("primary_leg", primary_leg), ("counter_leg", counter_leg)):
            if not isinstance(leg, dict):
                raise ValueError(f"{name} must be an object")
            at = str(leg.get("asset_type") or "").strip().lower()
            if at not in ("fiat", "stable"):
                raise ValueError(f"{name}.asset_type invalid")
            code = str(leg.get("code") or "").strip()
            if not code or len(code) > 32:
                raise ValueError(f"{name}.code invalid")
            side = str(leg.get("side") or "").strip().lower()
            if side not in ("give", "receive"):
                raise ValueError(f"{name}.side invalid")
            amt = self._leg_amount_str(leg)
            if name == "primary_leg" and not amt:
                raise ValueError("primary_leg.amount is required")
            if name == "counter_leg" and not amt and not leg.get("amount_discussed"):
                raise ValueError(
                    "counter_leg.amount or counter_leg.amount_discussed required"
                )

    @classmethod
    def _normalize_intermediary_percent(cls, raw: Optional[str]) -> str:
        s = (raw or "").strip() or "0.5"
        try:
            d = Decimal(s)
        except InvalidOperation as exc:
            raise ValueError("intermediary_percent_invalid") from exc
        if d < cls._RESELL_PCT_MIN or d > cls._RESELL_PCT_MAX:
            raise ValueError("intermediary_percent_range")
        q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        t = format(q, "f")
        if "." in t:
            t = t.rstrip("0").rstrip(".")
        return t or "0"

    def _resell_parent_ref(self, comm: Dict[str, Any], row_public_ref: str) -> str:
        sys_slot = comm.get(SYSTEM_SLOT_KEY)
        if isinstance(sys_slot, dict):
            alias = (sys_slot.get("alias_public_ref") or "").strip()
            if alias:
                return alias
        return str(row_public_ref)

    def _allocate_new_intermediary_slot_key(self, base: Dict[str, Any]) -> str:
        for _ in range(64):
            k = "i_" + uuid.uuid4().hex[:12]
            if k not in base:
                return k
        raise RuntimeError("Could not allocate intermediary slot key")

    def _canonical_parent_ref_for_resell(
        self,
        comm: Dict[str, Any],
        root_public_ref: str,
        parent_ref_raw: str,
    ) -> str:
        """parent_id для слота resell при явном ref из URL (alias слота или column public_ref)."""
        o = (parent_ref_raw or "").strip()
        if not o:
            raise ValueError("commissioners_invalid")
        ol = o.lower()
        root = (root_public_ref or "").strip()
        if root and ol == root.lower():
            return root
        for slot in comm.values():
            if not isinstance(slot, dict):
                continue
            alias = (slot.get("alias_public_ref") or "").strip()
            if alias and alias.lower() == ol:
                return alias
        raise ValueError("commissioners_invalid")

    async def maybe_auto_resell_on_resolve(
        self,
        row: PaymentRequest,
        space_nickname: str,
        viewer_did: str,
        arbiter_did: str,
        segment: PaymentRequestResolveSegment,
    ) -> Tuple[PaymentRequest, str]:
        """
        Не-владелец при GET resolve: новый посредник получает слот i_<…>; уже есть слот — только ensure alias.
        """
        vd = (viewer_did or "").strip()
        owner = (row.owner_did or "").strip()
        if not vd or vd == owner:
            return row, space_nickname
        if row.deactivated_at is not None:
            return row, space_nickname
        if row.deal_id is not None:
            return row, space_nickname

        raw_comm = row.commissioners
        base: Dict[str, Any] = dict(raw_comm) if isinstance(raw_comm, dict) else {}
        if intermediary_slot_keys_for_did(base, vd):
            await self.ensure_commissioner_view(row, vd)
            await self._session.commit()
            await self._session.refresh(row)
            return row, space_nickname

        parent_override: Optional[str] = None
        if segment.match_kind == "commissioner_alias" and segment.commissioner_parent_ref:
            parent_override = segment.commissioner_parent_ref.strip()

        try:
            return await self.apply_resell_intermediary(
                actor_did=vd,
                arbiter_did=arbiter_did,
                public_uid=str(row.uid),
                intermediary_percent=None,
                parent_ref_override=parent_override,
            )
        except ValueError as exc:
            logger.info("auto resell on resolve skipped: %s", exc)
            return row, space_nickname

    async def apply_resell_intermediary(
        self,
        *,
        actor_did: str,
        arbiter_did: str,
        public_uid: str,
        intermediary_percent: Optional[str] = None,
        parent_ref_override: Optional[str] = None,
    ) -> Tuple[PaymentRequest, str]:
        arb = (arbiter_did or "").strip()
        uid_key = (public_uid or "").strip()
        if not uid_key:
            raise ValueError("public_uid_required")
        actor = (actor_did or "").strip()
        if not actor:
            raise ValueError("actor_required")

        pair = await self._requests.get_by_uid(uid_key, arbiter_did=arb)
        if pair is None:
            raise ValueError("not_found")

        row, nick = pair
        if row.deactivated_at is not None:
            raise ValueError("request_deactivated")
        if row.deal_id is not None:
            raise ValueError("request_already_accepted")
        owner_row = (row.owner_did or "").strip()
        if actor == owner_row:
            raise ValueError("owner_cannot_resell")

        pct_str = self._normalize_intermediary_percent(intermediary_percent)

        raw_comm = row.commissioners
        base: Dict[str, Any] = dict(raw_comm) if isinstance(raw_comm, dict) else {}

        actor_slot_keys = intermediary_slot_keys_for_did(base, actor)

        root_ref = str(getattr(row, "public_ref", "") or "")
        if parent_ref_override is not None:
            parent_ref = self._canonical_parent_ref_for_resell(
                base, root_ref, parent_ref_override
            )
        else:
            parent_ref = self._resell_parent_ref(base, root_ref)

        if actor_slot_keys:
            slot_key = actor_slot_keys[0]
            prev = dict(base[slot_key])
            prev["commission"] = {"kind": "percent", "value": pct_str}
            if parent_ref_override is not None:
                prev["parent_id"] = parent_ref
            base[slot_key] = prev
        else:
            slot_key = self._allocate_new_intermediary_slot_key(base)
            base[slot_key] = {
                "did": actor,
                "role": "intermediary",
                "commission": {"kind": "percent", "value": pct_str},
                "parent_id": parent_ref,
            }
        snaps = build_slot_snapshots(
            str(row.direction or ""),
            dict(row.primary_leg) if isinstance(row.primary_leg, dict) else {},
            dict(row.counter_leg) if isinstance(row.counter_leg, dict) else {},
            base,
            [slot_key],
        )
        if slot_key in snaps:
            base[slot_key]["payment_amount"] = snaps[slot_key]["payment_amount"]
            base[slot_key]["borrow_amount"] = snaps[slot_key]["borrow_amount"]

        from web.endpoints.v1.schemas.payment_request_commissioners import (
            CommissionersPayload,
            validate_commissioners_parent_refs,
        )

        validate_commissioners_parent_refs(base, root_public_ref=root_ref)
        try:
            CommissionersPayload.model_validate(base)
        except ValidationError as exc:
            raise ValueError("commissioners_invalid") from exc

        row.commissioners = base
        await self._session.commit()
        await self._session.refresh(row)
        await self.ensure_commissioner_view(row, actor)
        await self._session.commit()
        await self._session.refresh(row)
        return row, nick


# Создание Deal при принятии заявки контрагентом — отдельный поток (эндпоинт + fill deal_id).
