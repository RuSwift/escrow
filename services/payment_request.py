"""Заявки PaymentRequest (Simple UI): fiat↔stable до создания Deal."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Literal, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PaymentRequest
from repos.payment_request import PaymentRequestRepository
from services.exchange_wallets import ExchangeWalletService
from services.space import SpaceService
from services.wallet_user import WalletUserService
from settings import Settings

logger = logging.getLogger(__name__)

SimpleDirection = Literal["fiat_to_stable", "stable_to_fiat"]
SimplePaymentLifetime = Literal["24h", "48h", "72h", "forever"]


class PaymentRequestService:
    """Simple-заявки без space в URL (space из auth); Deal создаётся позже при принятии."""

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

    async def list_payment_requests(
        self,
        *,
        wallet_address: str,
        owner_did: str,
        standard: str,
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
        return await self._requests.list_for_owner(
            owner_did, page=page, page_size=page_size, q=q
        )

    async def deactivate_payment_request(
        self,
        *,
        wallet_address: str,
        owner_did: str,
        standard: str,
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
                owner_did, pk, confirm_pk
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

        await self._space.ensure_owner_or_operator(space_nick, wallet_address)

        self._validate_simple_legs(direction, primary_leg, counter_leg)
        h = (heading or "").strip()
        heading_val: Optional[str] = h if h else None

        ramp_wallet_id = await self._exchange.primary_ramp_wallet_id_for_space(
            space_nick, wallet_address
        )

        expires_at = self._expires_at_for_lifetime(lifetime)

        uid = uuid.uuid4().hex
        row = await self._requests.insert(
            uid=uid,
            space_id=space_id,
            owner_did=owner_did,
            direction=direction,
            primary_leg=primary_leg,
            counter_leg=counter_leg,
            primary_ramp_wallet_id=ramp_wallet_id,
            heading=heading_val,
            expires_at=expires_at,
        )
        await self._session.commit()
        await self._session.refresh(row)
        logger.info(
            "PaymentRequest created uid=%s space_id=%s space_nick=%s owner=%s",
            uid,
            space_id,
            space_nick,
            owner_did,
        )
        return row, space_nick

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


# Создание Deal при принятии заявки контрагентом — отдельный поток (эндпоинт + fill deal_id).
