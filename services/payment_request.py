"""Заявки PaymentRequest (Simple UI): fiat↔stable до создания Deal."""

from __future__ import annotations

import copy
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.short_id import generate_public_ref
from db.models import PaymentRequest, Wallet, WalletUser
from i18n.translations import get_translation
from repos.deal import DealRepository
from repos.payment_request import PaymentRequestRepository, PaymentRequestResolveSegment
from services.notify import NotifyService
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
        participant_keys: List[str] = []
        for sk, slot in comm.items():
            if not isinstance(slot, dict):
                continue
            if (slot.get("did") or "").strip() != vd:
                continue
            if str(slot.get("role") or "").strip().lower() == SYSTEM_SLOT_KEY:
                continue
            role = str(slot.get("role") or "").strip().lower()
            if role == "participant":
                participant_keys.append(sk)
                continue
            if is_intermediary_commission_slot(sk, slot):
                keys_for_viewer.append(sk)

        if not keys_for_viewer:
            # participant slots: ensure alias_public_ref exists
            if not participant_keys:
                return
            changed_p = False
            for target_key in sorted(participant_keys):
                slot_obj = dict(comm[target_key])
                if (slot_obj.get("alias_public_ref") or "").strip():
                    continue
                alias = await self._generate_unique_alias_public_ref()
                slot_obj["alias_public_ref"] = alias
                comm[target_key] = slot_obj
                changed_p = True
            if not changed_p:
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

    async def extend_payment_request_owner(
        self,
        *,
        wallet_address: str,
        owner_did: str,
        standard: str,
        arbiter_did: str,
        pk: int,
        lifetime: SimplePaymentLifetime = "72h",
    ) -> Tuple[PaymentRequest, str]:
        """
        Продлить срок заявки (expires_at) владельцем.

        Семантика: выставить expires_at = max(now, текущий expires_at) + lifetime (24/48/72h).
        Для forever (expires_at is NULL) — no-op.
        """
        bc = self._blockchain_for_standard(standard)
        pair = await self._wallet_users.resolve_primary_space_nickname_and_id(
            wallet_address, bc
        )
        if not pair:
            raise ValueError("No space for this wallet")
        space_nick, _ = pair
        await self._space.ensure_owner_or_operator(space_nick, wallet_address)

        got = await self._requests.get_by_pk(pk, arbiter_did=(arbiter_did or "").strip())
        if got is None:
            raise ValueError("not_found")
        row, nick = got
        od = (owner_did or "").strip()
        if not od or od != (row.owner_did or "").strip():
            raise ValueError("not_owner")

        lt = str(lifetime or "72h").strip()
        if lt not in ("24h", "48h", "72h"):
            raise ValueError("invalid_lifetime")

        now = datetime.now(timezone.utc)
        cur = getattr(row, "expires_at", None)
        if cur is None:
            # forever; keep as is
            await self._session.commit()
            await self._session.refresh(row)
            return row, nick
        base = cur if isinstance(cur, datetime) and cur > now else now
        hours = 24 if lt == "24h" else (48 if lt == "48h" else 72)
        row.expires_at = base + timedelta(hours=hours)
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
        # If viewer already has any slot (participant/intermediary/counterparty) — just ensure alias.
        has_any = False
        for _sk, slot in base.items():
            if not isinstance(slot, dict):
                continue
            if (slot.get("did") or "").strip() != vd:
                continue
            if str(slot.get("role") or "").strip().lower() == SYSTEM_SLOT_KEY:
                continue
            has_any = True
            break
        if has_any:
            await self.ensure_commissioner_view(row, vd)
            await self._session.commit()
            await self._session.refresh(row)
            return row, space_nickname

        parent_override: Optional[str] = None
        if segment.match_kind == "commissioner_alias" and segment.commissioner_parent_ref:
            parent_override = segment.commissioner_parent_ref.strip()

        # Create participant slot (no commission) with personal alias_public_ref.
        root_ref = str(getattr(row, "public_ref", "") or "")
        if parent_override is not None:
            parent_ref = self._canonical_parent_ref_for_resell(base, root_ref, parent_override)
        else:
            parent_ref = self._resell_parent_ref(base, root_ref)

        slot_key = self._allocate_new_intermediary_slot_key(base)
        alias = await self._generate_unique_alias_public_ref()
        base[slot_key] = {
            "did": vd,
            "role": "participant",
            "parent_id": parent_ref,
            "alias_public_ref": alias,
        }
        from web.endpoints.v1.schemas.payment_request_commissioners import (
            CommissionersPayload,
            validate_commissioners_parent_refs,
        )
        validate_commissioners_parent_refs(base, root_public_ref=root_ref)
        CommissionersPayload.model_validate(base)
        row.commissioners = base
        await self._session.commit()
        await self._session.refresh(row)
        return row, space_nickname

    async def set_payment_request_viewer_role(
        self,
        *,
        actor_did: str,
        arbiter_did: str,
        pk: int,
        role: Literal["counterparty", "intermediary"],
        parent_ref: Optional[str] = None,
    ) -> Tuple[PaymentRequest, str]:
        """
        Зафиксировать роль viewer на стадии согласования условий.

        - counterparty: убрать (если есть) intermediary-слоты данного did.
        - intermediary: добавить/обновить intermediary-слот (как resell), опционально с parent_ref (alias в URL).
        """
        pair = await self._requests.get_by_pk(pk, arbiter_did=arbiter_did)
        if pair is None:
            raise ValueError("not_found")
        row, space_nickname = pair
        if row.deactivated_at is not None:
            raise ValueError("request_deactivated")
        if row.deal_id is not None:
            raise ValueError("request_already_accepted")

        actor = (actor_did or "").strip()
        if not actor:
            raise ValueError("actor_required")
        owner = (row.owner_did or "").strip()
        if actor == owner:
            raise ValueError("owner_cannot_resell")

        raw_comm = row.commissioners
        base: Dict[str, Any] = dict(raw_comm) if isinstance(raw_comm, dict) else {}
        actor_slot_keys = intermediary_slot_keys_for_did(base, actor)

        # Find existing non-system slot key for actor (participant/intermediary/counterparty)
        slot_key: Optional[str] = None
        for sk, slot in base.items():
            if not isinstance(slot, dict):
                continue
            if (slot.get("did") or "").strip() != actor:
                continue
            if str(slot.get("role") or "").strip().lower() == SYSTEM_SLOT_KEY:
                continue
            slot_key = sk
            break
        if slot_key is None:
            raise ValueError("no_viewer_slot")

        slot_obj = dict(base[slot_key]) if isinstance(base.get(slot_key), dict) else {}
        if role == "counterparty":
            slot_obj["role"] = "counterparty"
            # В сегменте комиссию не обнуляем: роль контрагента не участвует в расчётах комиссий,
            # но если пользователь вернётся к посреднику, прежний % должен сохраниться.
            base[slot_key] = slot_obj
            row.commissioners = base
            self._rebuild_all_commission_snapshots(row)
            await self._session.commit()
            await self._session.refresh(row)
            return row, space_nickname

        # role == intermediary
        slot_obj["role"] = "intermediary"
        comm = slot_obj.get("commission")
        if not isinstance(comm, dict):
            slot_obj["commission"] = {"kind": "percent", "value": "0.5"}
        else:
            # Если комиссия залипла в 0 (после выбора контрагента) — вернуть дефолт 0.5%.
            if str(comm.get("kind") or "").strip().lower() == "percent":
                v = str(comm.get("value") or "").strip()
                if v in ("0", "0.0", "0.00"):
                    comm["value"] = "0.5"
                    slot_obj["commission"] = comm
        base[slot_key] = slot_obj
        row.commissioners = base
        self._rebuild_all_commission_snapshots(row)
        await self._session.commit()
        await self._session.refresh(row)
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

    @staticmethod
    def _commission_snapshot_keys(comm: Dict[str, Any]) -> List[str]:
        keys: List[str] = []
        for k, slot in comm.items():
            if not isinstance(slot, dict):
                continue
            role = str(slot.get("role") or "").strip().lower()
            if role not in ("system", "intermediary"):
                continue
            if isinstance(slot.get("commission"), dict):
                keys.append(str(k))
        return keys

    def _validate_commissioners_row(self, row: PaymentRequest, comm: Dict[str, Any]) -> None:
        root_ref = str(getattr(row, "public_ref", "") or "")
        from web.endpoints.v1.schemas.payment_request_commissioners import (
            CommissionersPayload,
            validate_commissioners_parent_refs,
        )

        validate_commissioners_parent_refs(comm, root_public_ref=root_ref)
        CommissionersPayload.model_validate(comm)

    def _rebuild_all_commission_snapshots(self, row: PaymentRequest) -> None:
        raw = row.commissioners
        comm = dict(raw) if isinstance(raw, dict) else {}
        keys = self._commission_snapshot_keys(comm)
        if not keys:
            row.commissioners = comm
            return
        snaps = build_slot_snapshots(
            str(row.direction or ""),
            dict(row.primary_leg) if isinstance(row.primary_leg, dict) else {},
            dict(row.counter_leg) if isinstance(row.counter_leg, dict) else {},
            comm,
            keys,
        )
        for k in keys:
            slot = comm.get(k)
            if not isinstance(slot, dict):
                continue
            if k in snaps:
                slot["payment_amount"] = snaps[k]["payment_amount"]
                slot["borrow_amount"] = snaps[k]["borrow_amount"]
        row.commissioners = comm
        self._validate_commissioners_row(row, comm)

    @staticmethod
    def _commissioner_notify_recipients(comm: Dict[str, Any]) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        seen: set[str] = set()
        for slot in comm.values():
            if not isinstance(slot, dict):
                continue
            did = (slot.get("did") or "").strip()
            if not did or did == "system":
                continue
            if did in seen:
                continue
            seen.add(did)
            out.append({"did": did})
        return out

    async def _notify_handshake_event(
        self,
        *,
        row: PaymentRequest,
        space_nickname: str,
        event: str,
    ) -> None:
        notify = NotifyService(self._session, self._redis, self._settings)
        lang = await notify._language_for_scope(space_nickname)
        pub = str(row.public_ref or "")
        keys = {
            "accepted": "notify.payment_request_handshake_accepted",
            "confirmed": "notify.payment_request_handshake_confirmed",
            "withdrawn": "notify.payment_request_handshake_withdrawn",
        }
        msg_key = keys.get(event)
        if not msg_key:
            return
        text = get_translation(msg_key, lang, public_ref=pub)
        await notify.notify_roles(space_nickname, ["owner", "operator"], text)
        comm = dict(row.commissioners) if isinstance(row.commissioners, dict) else {}
        recipients = self._commissioner_notify_recipients(comm)
        if recipients:
            await notify.send_message(recipients, text)

    async def accept_payment_request_counterparty(
        self,
        *,
        actor_did: str,
        arbiter_did: str,
        pk: int,
        counter_stable_amount: Optional[str] = None,
    ) -> Tuple[PaymentRequest, str]:
        pair = await self._requests.get_by_pk(pk, arbiter_did=arbiter_did)
        if pair is None:
            raise ValueError("not_found")
        row, space_nickname = pair
        if row.deactivated_at is not None:
            raise ValueError("request_deactivated")
        if row.deal_id is not None:
            raise ValueError("request_already_accepted")
        owner = (row.owner_did or "").strip()
        actor = (actor_did or "").strip()
        if not actor:
            raise ValueError("actor_required")
        if actor == owner:
            raise ValueError("owner_cannot_accept")

        locked = (row.counterparty_accept_did or "").strip()
        if locked and locked != actor:
            raise ValueError("counterparty_already_locked")
        if (
            locked == actor
            and row.owner_confirm_pending
            and row.deal_id is None
        ):
            await self._session.refresh(row)
            return row, space_nickname

        direction = str(row.direction or "").strip()
        if direction not in ("fiat_to_stable", "stable_to_fiat"):
            raise ValueError("invalid_direction")

        pl = dict(row.primary_leg) if isinstance(row.primary_leg, dict) else {}
        cl = dict(row.counter_leg) if isinstance(row.counter_leg, dict) else {}
        discussed = bool(cl.get("amount_discussed"))
        amt_existing = self._leg_amount_str(cl)

        if discussed:
            snap = str(counter_stable_amount or "").strip()
            if not snap:
                raise ValueError("counter_stable_amount_required")
            row.counter_leg_snapshot_json = copy.deepcopy(cl)
            cl["amount"] = snap
            cl["amount_discussed"] = False
            row.counter_leg = cl
            self._validate_simple_legs(
                cast(SimpleDirection, direction),
                pl,
                dict(row.counter_leg) if isinstance(row.counter_leg, dict) else {},
            )
            self._rebuild_all_commission_snapshots(row)
        else:
            if not amt_existing:
                raise ValueError("counter_leg_invalid")
            row.counter_leg_snapshot_json = None

        now = datetime.now(timezone.utc)
        row.counterparty_accept_did = actor
        row.counterparty_accept_at = now
        row.owner_confirm_pending = True

        await self._session.commit()
        await self._session.refresh(row)
        await self._notify_handshake_event(
            row=row, space_nickname=space_nickname, event="accepted"
        )
        return row, space_nickname

    async def _signer_from_wallet_user_did(self, did: str) -> Dict[str, str]:
        """Primary wallet спейса по DID участника (WalletUser)."""
        d = (did or "").strip()
        if not d:
            raise ValueError("signer_did_empty")
        user = await self._wallet_users.get_by_identifier(d)
        nickname: Optional[str] = user.nickname if user is not None else None
        # Fallback: в проде WalletUser.did может быть did:web:..., а в заявке хранится did:tron:<address>.
        # В этом случае ищем участника по wallet_address из DID.
        if nickname is None:
            low = d.lower()
            addr: Optional[str] = None
            if low.startswith("did:tron:"):
                addr = d[len("did:tron:") :].strip()
            elif low.startswith("did:ethr:"):
                addr = d[len("did:ethr:") :].strip()
            if addr:
                stmt = select(WalletUser.nickname).where(WalletUser.wallet_address == addr).limit(1)
                res = await self._session.execute(stmt)
                nickname = res.scalar_one_or_none()
        if not nickname:
            raise ValueError("wallet_user_not_found_for_did")
        pw = await self._space.get_primary_wallet(nickname)
        addr = (pw.get("address") or "").strip()
        bc = (str(pw.get("blockchain") or "tron")).strip().lower()
        if not addr:
            raise ValueError("primary_wallet_empty")
        return {"address": addr, "blockchain": bc}

    async def _signer_for_arbiter_did(self, arbiter_did: str) -> Dict[str, str]:
        """Арбитр: либо спейс (did:tron / did:ethr), либо кошелёк ноды (did:peer / …) из wallets."""
        aid = (arbiter_did or "").strip()
        if not aid:
            raise ValueError("arbiter_did_empty")
        low = aid.lower()
        if low.startswith("did:tron:") or low.startswith("did:ethr:"):
            return await self._signer_from_wallet_user_did(aid)
        stmt = (
            select(Wallet.tron_address)
            .where(
                Wallet.owner_did == aid,
                Wallet.role == "arbiter",
                Wallet.tron_address.isnot(None),
            )
            .limit(1)
        )
        res = await self._session.execute(stmt)
        ta = res.scalar_one_or_none()
        ta_s = (ta or "").strip()
        if not ta_s:
            raise ValueError("arbiter_wallet_not_found")
        return {"address": ta_s, "blockchain": "tron"}

    async def _build_deal_signers_for_simple_confirm(
        self,
        *,
        sender_did: str,
        receiver_did: str,
        arbiter_did: str,
    ) -> Dict[str, Any]:
        """Фиксированные адреса подписантов escrow на момент создания Deal."""
        return {
            "sender": await self._signer_from_wallet_user_did(sender_did),
            "receiver": await self._signer_from_wallet_user_did(receiver_did),
            "arbiter": await self._signer_for_arbiter_did(arbiter_did),
        }

    async def confirm_payment_request_owner(
        self,
        *,
        owner_did: str,
        arbiter_did: str,
        pk: int,
    ) -> Tuple[PaymentRequest, str, str]:
        pair = await self._requests.get_by_pk(pk, arbiter_did=arbiter_did)
        if pair is None:
            raise ValueError("not_found")
        row, space_nickname = pair
        od = (owner_did or "").strip()
        if not od or od != (row.owner_did or "").strip():
            raise ValueError("not_owner")
        if row.deal_id is not None:
            raise ValueError("already_confirmed")
        if not row.owner_confirm_pending or row.counterparty_accept_at is None:
            raise ValueError("nothing_to_confirm")
        cp = (row.counterparty_accept_did or "").strip()
        if not cp:
            raise ValueError("nothing_to_confirm")

        # Deal participants mapping:
        # - sender: the party that deposits stable into escrow (gives stable)
        # - receiver: the other party
        # For fiat_to_stable the counterparty (acceptor) gives stable; for stable_to_fiat the owner gives stable.
        direction = str(row.direction or "").strip()
        if direction == "fiat_to_stable":
            sender_did = cp
            receiver_did = od
        else:
            sender_did = od
            receiver_did = cp

        deals = DealRepository(self._session, self._redis, self._settings)
        label = self.build_pair_label(
            cast(SimpleDirection, str(row.direction or "").strip()),
            dict(row.primary_leg) if isinstance(row.primary_leg, dict) else {},
            dict(row.counter_leg) if isinstance(row.counter_leg, dict) else {},
        )
        signers = await self._build_deal_signers_for_simple_confirm(
            sender_did=sender_did,
            receiver_did=receiver_did,
            arbiter_did=str(row.arbiter_did or "").strip(),
        )
        deal = await deals.create_from_simple_payment_request(
            sender_did=sender_did,
            receiver_did=receiver_did,
            arbiter_did=str(row.arbiter_did or "").strip(),
            label=label,
            signers=signers,
        )
        row.deal_id = deal.pk
        row.owner_confirmed_at = datetime.now(timezone.utc)
        row.owner_confirm_pending = False

        await self._session.commit()
        await self._session.refresh(row)
        await self._notify_handshake_event(
            row=row, space_nickname=space_nickname, event="confirmed"
        )
        return row, space_nickname, str(deal.uid)

    async def withdraw_payment_request_acceptance(
        self,
        *,
        actor_did: str,
        arbiter_did: str,
        pk: int,
    ) -> Tuple[PaymentRequest, str]:
        pair = await self._requests.get_by_pk(pk, arbiter_did=arbiter_did)
        if pair is None:
            raise ValueError("not_found")
        row, space_nickname = pair
        if row.deal_id is not None:
            raise ValueError("cannot_withdraw")
        actor = (actor_did or "").strip()
        acc = (row.counterparty_accept_did or "").strip()
        if not acc or actor != acc:
            raise ValueError("not_accepting_party")
        if not row.owner_confirm_pending:
            raise ValueError("no_pending_acceptance")

        snap_raw = row.counter_leg_snapshot_json
        if isinstance(snap_raw, dict):
            row.counter_leg = copy.deepcopy(snap_raw)
            row.counter_leg_snapshot_json = None
            self._rebuild_all_commission_snapshots(row)
        else:
            row.counter_leg_snapshot_json = None

        row.counterparty_accept_did = None
        row.counterparty_accept_at = None
        row.owner_confirm_pending = False

        await self._session.commit()
        await self._session.refresh(row)
        await self._notify_handshake_event(
            row=row, space_nickname=space_nickname, event="withdrawn"
        )
        return row, space_nickname


# Создание Deal при принятии заявки контрагентом — отдельный поток (эндпоинт + fill deal_id).
