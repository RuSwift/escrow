"""Бизнес-логика конфигураций onRamp/offRamp (exchange_services) в разрезе space."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.bc import PaymentForm
from db.models import ExchangeRateMode, ExchangeServiceType
from repos.exchange_service import ExchangeServiceRepository
from repos.wallet import WalletRepository
from repos.wallet_user import WalletUserRepository
from services.requisites_form_effective import (
    EffectiveRequisitesFormSource,
    resolve_effective_requisites_form,
)
from services.space import SpaceService
from settings import Settings


class ExchangeServiceValidationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _strip(s: str | None) -> str:
    return (s or "").strip()


def _optional_str(s: Any) -> str | None:
    if s is None:
        return None
    t = _strip(str(s))
    return t if t else None


def _optional_text(s: Any) -> str | None:
    if s is None:
        return None
    t = str(s).strip()
    return t if t else None


def _normalize_svc_type(raw: str) -> str:
    t = _strip(raw).lower().replace("-", "_")
    if t in ("onramp", "on_ramp"):
        return ExchangeServiceType.on_ramp.value
    if t in ("offramp", "off_ramp"):
        return ExchangeServiceType.off_ramp.value
    if t in (ExchangeServiceType.on_ramp.value, ExchangeServiceType.off_ramp.value):
        return t
    raise ExchangeServiceValidationError(
        "invalid_service_type",
        "service_type must be on_ramp or off_ramp",
    )


def _normalize_rate_mode(raw: str) -> str:
    m = _strip(raw).lower()
    for v in (
        ExchangeRateMode.manual.value,
        ExchangeRateMode.on_request.value,
        ExchangeRateMode.ratios.value,
    ):
        if m == v:
            return v
    raise ExchangeServiceValidationError(
        "invalid_rate_mode",
        "rate_mode must be manual, on_request, or ratios",
    )


def _validate_payload(
    *,
    rate_mode: str,
    manual_rate: Decimal | None,
    ratios_engine_key: str | None,
    min_fiat: Decimal,
    max_fiat: Decimal,
) -> None:
    if min_fiat >= max_fiat:
        raise ExchangeServiceValidationError(
            "invalid_fiat_range",
            "min_fiat_amount must be less than max_fiat_amount",
        )
    if rate_mode == ExchangeRateMode.manual.value:
        if manual_rate is None or manual_rate <= 0:
            raise ExchangeServiceValidationError(
                "manual_rate_required",
                "manual_rate is required and must be positive for rate_mode=manual",
            )
    if rate_mode == ExchangeRateMode.ratios.value:
        if not (ratios_engine_key or "").strip():
            raise ExchangeServiceValidationError(
                "ratios_engine_key_required",
                "ratios_engine_key is required for rate_mode=ratios",
            )


def _validate_cash_verification(
    *,
    fiat: str,
    payment_code: str | None,
    verif: dict[str, Any],
) -> None:
    """
    Наличные направления: ``verification_requirements.cash`` и ``cash_cities``;
    при ``cash is True`` — непустой список городов и ``payment_code == CASH{FIAT}``.
    """
    cash = verif.get("cash")
    if cash is not True:
        return
    cities = verif.get("cash_cities")
    if not isinstance(cities, list) or len(cities) < 1:
        raise ExchangeServiceValidationError(
            "cash_cities_required",
            "cash_cities must be a non-empty list when cash is true",
        )
    fiat_u = _strip(fiat).upper()
    if len(fiat_u) != 3:
        return
    expected_pc = f"CASH{fiat_u}"
    pc = _strip(payment_code or "").upper()
    if pc != expected_pc:
        raise ExchangeServiceValidationError(
            "cash_payment_code_mismatch",
            f"payment_code must be {expected_pc} for cash directions",
        )
    for c in cities:
        if isinstance(c, dict):
            nm = _strip(str(c.get("name", "")))
            if not nm:
                raise ExchangeServiceValidationError(
                    "cash_city_name_required",
                    "each cash_cities item must have a non-empty name",
                )
        elif isinstance(c, str):
            if not _strip(c):
                raise ExchangeServiceValidationError(
                    "cash_city_name_required",
                    "each cash_cities item must be a non-empty string or object with name",
                )
        else:
            raise ExchangeServiceValidationError(
                "invalid_cash_city",
                "cash_cities items must be objects with name or non-empty strings",
            )


async def _owner_did_for_space_session(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    space: str,
) -> str:
    users = WalletUserRepository(session=session, redis=redis, settings=settings)
    owner = await users.get_by_nickname((space or "").strip())
    if not owner:
        raise ExchangeServiceValidationError("space_not_found", "Space not found")
    return owner.did


def _parse_dt(v: Any) -> datetime | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    return None


class SpaceExchangeService:
    """CRUD exchange_services (только owner спейса)."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = ExchangeServiceRepository(
            session=session, redis=redis, settings=settings
        )
        self._space = SpaceService(session=session, redis=redis, settings=settings)

    async def _validate_off_ramp_space_wallet(
        self,
        space: str,
        wallet_id: int,
    ) -> int:
        if wallet_id <= 0:
            raise ExchangeServiceValidationError(
                "invalid_space_wallet_id",
                "space_wallet_id must be a positive integer",
            )
        owner_did = await _owner_did_for_space_session(
            self._session, self._redis, self._settings, space
        )
        wr = WalletRepository(self._session, self._redis, self._settings)
        w = await wr.get_exchange_wallet(wallet_id, owner_did)
        if not w:
            raise ExchangeServiceValidationError(
                "space_wallet_not_found",
                "Corporate wallet not found or does not belong to this space",
            )
        return wallet_id

    def _payment_form_resolver(self):
        from repos.bestchange import PaymentFormsYamlRepository
        from repos.space_payment_form import SpacePaymentFormOverrideRepository
        from services.payment_form_resolve import PaymentFormResolutionService

        return PaymentFormResolutionService(
            SpacePaymentFormOverrideRepository(
                session=self._session, redis=self._redis, settings=self._settings
            ),
            PaymentFormsYamlRepository(
                session=self._session, redis=self._redis, settings=self._settings
            ),
        )

    async def get_effective_payment_form(
        self,
        space: str,
        service_id: int,
        actor_wallet_address: str,
    ) -> tuple[PaymentForm | None, EffectiveRequisitesFormSource, str] | None:
        """Форма реквизитов для направления: кастом из БД или каталог (как в заявках).

        ``None`` — направление не найдено (не 404 формы).
        """
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        row = await self._repo.get_by_id(service_id, space)
        if row is None:
            return None
        form, src = await resolve_effective_requisites_form(
            space=space,
            payment_code=row.payment_code,
            requisites_form_schema=row.requisites_form_schema,
            resolver=self._payment_form_resolver(),
        )
        code = _strip(row.payment_code)
        return form, src, code

    async def list_services(self, space: str, actor_wallet_address: str):
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        rows = await self._repo.list_for_space(space)
        out = []
        for r in rows:
            tiers = await self._repo.list_fee_tiers(int(r.id))
            out.append((r, tiers))
        return out

    async def get_service(
        self,
        space: str,
        service_id: int,
        actor_wallet_address: str,
    ):
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        row = await self._repo.get_by_id(service_id, space)
        if row is None:
            return None
        tiers = await self._repo.list_fee_tiers(int(row.id))
        return row, tiers

    async def create_service(
        self,
        space: str,
        actor_wallet_address: str,
        *,
        payload: dict[str, Any],
        fee_tiers: Optional[list[dict[str, Any]]] = None,
    ):
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        st = _normalize_svc_type(str(payload.get("service_type", "")))
        rm = _normalize_rate_mode(str(payload.get("rate_mode", "")))
        fiat = _strip(payload.get("fiat_currency_code", "")).upper()
        if len(fiat) != 3:
            raise ExchangeServiceValidationError(
                "invalid_fiat",
                "fiat_currency_code must be ISO 4217 (3 letters)",
            )
        manual_rate = payload.get("manual_rate")
        mr = Decimal(str(manual_rate)) if manual_rate is not None else None
        min_f = Decimal(str(payload["min_fiat_amount"]))
        max_f = Decimal(str(payload["max_fiat_amount"]))
        ratios_key = _optional_str(payload.get("ratios_engine_key"))
        mrv = _parse_dt(payload.get("manual_rate_valid_until"))
        rcp = payload.get("ratios_commission_percent")
        rcp_d = Decimal(str(rcp)) if rcp is not None else None
        payment_code = _optional_str(payload.get("payment_code"))
        title_raw = payload.get("title")
        if title_raw is None:
            raise ExchangeServiceValidationError(
                "title_required",
                "title is required",
            )
        title = _strip(str(title_raw))
        if not title:
            raise ExchangeServiceValidationError(
                "title_required",
                "title must not be empty",
            )
        if len(title) > 255:
            raise ExchangeServiceValidationError(
                "title_too_long",
                "title must be at most 255 characters",
            )
        description = _optional_text(payload.get("description"))
        requisites = payload.get("requisites_form_schema") or {}
        verif = payload.get("verification_requirements") or {}
        if not isinstance(requisites, dict):
            raise ExchangeServiceValidationError(
                "invalid_requisites",
                "requisites_form_schema must be an object",
            )
        if not isinstance(verif, dict):
            raise ExchangeServiceValidationError(
                "invalid_verif",
                "verification_requirements must be an object",
            )
        _validate_cash_verification(
            fiat=fiat,
            payment_code=payment_code,
            verif=verif,
        )
        _validate_payload(
            rate_mode=rm,
            manual_rate=mr,
            ratios_engine_key=ratios_key,
            min_fiat=min_f,
            max_fiat=max_f,
        )
        sc_base = _optional_str(payload.get("stablecoin_base_currency"))
        row_fields: dict[str, Any] = {
            "service_type": st,
            "fiat_currency_code": fiat,
            "stablecoin_symbol": _strip(payload.get("stablecoin_symbol", "")),
            "network": _strip(payload.get("network", "")),
            "contract_address": _strip(payload.get("contract_address", "")),
            "stablecoin_base_currency": sc_base.upper() if sc_base else None,
            "title": title,
            "description": description,
            "payment_code": payment_code,
            "rate_mode": rm,
            "manual_rate": mr,
            "manual_rate_valid_until": mrv,
            "ratios_engine_key": ratios_key,
            "ratios_commission_percent": rcp_d,
            "min_fiat_amount": min_f,
            "max_fiat_amount": max_f,
            "requisites_form_schema": requisites,
            "verification_requirements": verif,
            "is_active": bool(payload.get("is_active", True)),
            "is_deleted": False,
        }
        if st == ExchangeServiceType.off_ramp.value:
            sw_raw = payload.get("space_wallet_id")
            if sw_raw is None:
                raise ExchangeServiceValidationError(
                    "space_wallet_required",
                    "space_wallet_id is required for off_ramp",
                )
            try:
                sw_id = int(sw_raw)
            except (TypeError, ValueError):
                raise ExchangeServiceValidationError(
                    "invalid_space_wallet_id",
                    "space_wallet_id must be a positive integer",
                )
            row_fields["space_wallet_id"] = await self._validate_off_ramp_space_wallet(
                space, sw_id
            )
        else:
            row_fields["space_wallet_id"] = None
        if (
            not row_fields["stablecoin_symbol"]
            or not row_fields["network"]
            or not row_fields["contract_address"]
        ):
            raise ExchangeServiceValidationError(
                "stable_network_required",
                "stablecoin_symbol, network, contract_address are required",
            )
        row = await self._repo.create(
            space=space, row_fields=row_fields, fee_tiers=fee_tiers
        )
        tiers = await self._repo.list_fee_tiers(int(row.id))
        await self._session.commit()
        await self._session.refresh(row)
        return row, tiers

    async def patch_service(
        self,
        space: str,
        service_id: int,
        actor_wallet_address: str,
        *,
        payload: dict[str, Any],
        fee_tiers: Optional[list[dict[str, Any]]] = None,
        replace_fee_tiers: bool = False,
    ):
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        row = await self._repo.get_by_id(service_id, space, include_deleted=True)
        if row is None or row.is_deleted:
            return None
        fields: dict[str, Any] = {}
        if "service_type" in payload:
            fields["service_type"] = _normalize_svc_type(str(payload["service_type"]))
        if "fiat_currency_code" in payload:
            fiat = _strip(payload["fiat_currency_code"]).upper()
            if len(fiat) != 3:
                raise ExchangeServiceValidationError(
                    "invalid_fiat",
                    "fiat_currency_code must be ISO 4217 (3 letters)",
                )
            fields["fiat_currency_code"] = fiat
        for key in ("stablecoin_symbol", "network", "contract_address"):
            if key in payload:
                fields[key] = _strip(payload[key])
        if "stablecoin_base_currency" in payload:
            v = _optional_str(payload["stablecoin_base_currency"])
            fields["stablecoin_base_currency"] = v.upper() if v else None
        if "title" in payload:
            t = _strip(str(payload["title"]))
            if not t:
                raise ExchangeServiceValidationError(
                    "title_required",
                    "title must not be empty",
                )
            if len(t) > 255:
                raise ExchangeServiceValidationError(
                    "title_too_long",
                    "title must be at most 255 characters",
                )
            fields["title"] = t
        if "description" in payload:
            fields["description"] = _optional_text(payload["description"])
        if "payment_code" in payload:
            fields["payment_code"] = _optional_str(payload["payment_code"])
        if "rate_mode" in payload:
            fields["rate_mode"] = _normalize_rate_mode(str(payload["rate_mode"]))
        if "manual_rate" in payload:
            mr = payload["manual_rate"]
            fields["manual_rate"] = Decimal(str(mr)) if mr is not None else None
        if "manual_rate_valid_until" in payload:
            fields["manual_rate_valid_until"] = _parse_dt(payload["manual_rate_valid_until"])
        if "ratios_engine_key" in payload:
            fields["ratios_engine_key"] = _optional_str(payload["ratios_engine_key"])
        if "ratios_commission_percent" in payload:
            rcp = payload["ratios_commission_percent"]
            fields["ratios_commission_percent"] = (
                Decimal(str(rcp)) if rcp is not None else None
            )
        if "min_fiat_amount" in payload:
            fields["min_fiat_amount"] = Decimal(str(payload["min_fiat_amount"]))
        if "max_fiat_amount" in payload:
            fields["max_fiat_amount"] = Decimal(str(payload["max_fiat_amount"]))
        if "requisites_form_schema" in payload:
            req = payload["requisites_form_schema"]
            if not isinstance(req, dict):
                raise ExchangeServiceValidationError(
                    "invalid_requisites",
                    "requisites_form_schema must be an object",
                )
            fields["requisites_form_schema"] = req
        if "verification_requirements" in payload:
            ver = payload["verification_requirements"]
            if not isinstance(ver, dict):
                raise ExchangeServiceValidationError(
                    "invalid_verif",
                    "verification_requirements must be an object",
                )
            fields["verification_requirements"] = ver
        if "is_active" in payload:
            fields["is_active"] = bool(payload["is_active"])
        if "space_wallet_id" in payload:
            sw_raw = payload["space_wallet_id"]
            if sw_raw is None:
                fields["space_wallet_id"] = None
            else:
                try:
                    sw_id = int(sw_raw)
                except (TypeError, ValueError):
                    raise ExchangeServiceValidationError(
                        "invalid_space_wallet_id",
                        "space_wallet_id must be a positive integer",
                    )
                fields["space_wallet_id"] = await self._validate_off_ramp_space_wallet(
                    space, sw_id
                )
        eff_type = fields.get("service_type", row.service_type)
        if eff_type == ExchangeServiceType.on_ramp.value:
            fields["space_wallet_id"] = None
        elif eff_type == ExchangeServiceType.off_ramp.value:
            eff_sw = fields.get("space_wallet_id", row.space_wallet_id)
            if eff_sw is None:
                raise ExchangeServiceValidationError(
                    "space_wallet_required",
                    "space_wallet_id is required for off_ramp",
                )
        if not fields and not replace_fee_tiers:
            tiers = await self._repo.list_fee_tiers(int(row.id))
            return row, tiers
        ver_merged: dict[str, Any] = dict(row.verification_requirements or {})
        if "verification_requirements" in fields:
            ver_merged = dict(fields["verification_requirements"] or {})
        pc_merged = (
            fields["payment_code"] if "payment_code" in fields else row.payment_code
        )
        fiat_merged = (
            fields["fiat_currency_code"]
            if "fiat_currency_code" in fields
            else row.fiat_currency_code
        )
        _validate_cash_verification(
            fiat=str(fiat_merged or ""),
            payment_code=_optional_str(pc_merged),
            verif=ver_merged,
        )
        rm = fields.get("rate_mode", row.rate_mode)
        mr = fields.get("manual_rate", row.manual_rate)
        rk = fields.get("ratios_engine_key", row.ratios_engine_key)
        min_f = fields.get("min_fiat_amount", row.min_fiat_amount)
        max_f = fields.get("max_fiat_amount", row.max_fiat_amount)
        _validate_payload(
            rate_mode=rm,
            manual_rate=mr,
            ratios_engine_key=rk,
            min_fiat=min_f,
            max_fiat=max_f,
        )
        stable_sym = fields.get("stablecoin_symbol", row.stablecoin_symbol)
        net = fields.get("network", row.network)
        ca = fields.get("contract_address", row.contract_address)
        if not _strip(stable_sym) or not _strip(net) or not _strip(ca):
            raise ExchangeServiceValidationError(
                "stable_network_required",
                "stablecoin_symbol, network, contract_address are required",
            )
        updated = await self._repo.update(
            service_id,
            space,
            fields=fields,
            fee_tiers=fee_tiers,
            replace_tiers=replace_fee_tiers,
        )
        if updated is None:
            return None
        tiers = await self._repo.list_fee_tiers(service_id)
        await self._session.commit()
        await self._session.refresh(updated)
        return updated, tiers

    async def delete_service(
        self,
        space: str,
        service_id: int,
        actor_wallet_address: str,
    ) -> bool:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        ok = await self._repo.soft_delete(service_id, space)
        if ok:
            await self._session.commit()
        return ok
