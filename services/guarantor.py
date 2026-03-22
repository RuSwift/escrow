"""
Сервис панели гаранта: профиль (GuarantorProfile) и направления (GuarantorDirection) в разрезе space.
Доступ только для owner спейса (как профиль спейса).
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, List, Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.iso4217_fiat import iso4217_active_fiat_only
from db.models import GuarantorDirection, GuarantorProfile
from repos.bestchange import BestchangeYamlRepository, CurrencyRow
from repos.guarantor_direction import GuarantorDirectionRepository
from services.ratios import get_ratios_engines
from services.ratios.forex import ForexEngine
from services.space import SpaceService
from services.wallet_user import WalletUserService
from settings import Settings

logger = logging.getLogger(__name__)


def _fiat_ac_casefold(s: str) -> str:
    return (s or "").casefold()


def _normalized_system_currencies(settings: Settings) -> list[str]:
    return [
        str(c).strip().upper()
        for c in (settings.system_currencies or [])
        if c and str(c).strip()
    ]


def _fiat_empty_q_sort_key(settings: Settings, code: str) -> tuple[int, int, str]:
    """Пустой q: сначала system_currencies (в порядке из настроек), затем остальные по коду."""
    u = code.strip().upper()
    sys_list = _normalized_system_currencies(settings)
    try:
        idx = sys_list.index(u)
        return (0, idx, u.casefold())
    except ValueError:
        return (1, 0, u.casefold())


async def async_forex_ratios_codes(redis: Redis, settings: Settings) -> set[str]:
    """Fallback для autocomplete is_fiat: коды из ForexEngine (рынок USD-*)."""
    engines = get_ratios_engines(redis, settings.ratios, refresh_cache=False)
    forex = next((e for e in engines if isinstance(e, ForexEngine) and e.is_enabled), None)
    if forex is None:
        logger.debug("fiat autocomplete: ForexEngine not available")
        return set()
    try:
        pairs = await forex.market()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fiat autocomplete: ForexEngine.market failed: %s", exc)
        return set()
    codes: set[str] = set()
    for p in pairs:
        codes.add(p.base.upper())
        codes.add(p.quote.upper())
    return codes


async def async_forex_supported_codes(
    repo: BestchangeYamlRepository,
    redis: Redis,
    settings: Settings,
) -> set[str]:
    """
    Коды для allowlist autocomplete is_fiat: сначала ``forex_currencies`` из последнего BestchangeYamlSnapshot,
    иначе — из Forex ratios (ForexEngine). В обоих случаях оставляем только активные ISO 4217 (котировки USD.json
    содержат и криптовалюты).
    """
    snap = await repo.snapshot_forex_currency_codes()
    snap_fiat = iso4217_active_fiat_only(snap)
    if snap_fiat:
        return snap_fiat
    raw = await async_forex_ratios_codes(redis, settings)
    return iso4217_active_fiat_only(raw)


async def list_autocomplete_fiat_currencies(
    repo: BestchangeYamlRepository,
    redis: Redis,
    settings: Settings,
    q: str | None,
    limit: int,
) -> list[CurrencyRow]:
    """
    Autocomplete валют с is_fiat (/v1/autocomplete/currencies): allowlist из snapshot (forex_currencies) или Forex ratios;
    при пустом q — сначала коды из Settings.system_currencies (в заданном порядке), затем остальные из allowlist по коду;
    при непустом q — сначала совпадения из BestChange, затем добор из allowlist.
    """
    allowed = await async_forex_supported_codes(repo, redis, settings)
    if not allowed:
        return []

    needle = _fiat_ac_casefold(str(q).strip()) if q and str(q).strip() else None

    if needle is None:
        ordered = sorted(allowed, key=lambda c: _fiat_empty_q_sort_key(settings, c))
        return [CurrencyRow(code=c) for c in ordered[:limit]]

    fetch_cap = min(max(limit * 8, 64), 500)

    bc_rows: list[CurrencyRow] = await repo.list(
        "currencies",
        q=q,
        limit=fetch_cap,
    )
    out: list[CurrencyRow] = []
    seen: set[str] = set()
    for row in bc_rows:
        code_u = row.code.strip().upper()
        if code_u not in allowed or code_u in seen:
            continue
        if needle not in _fiat_ac_casefold(code_u):
            continue
        out.append(row)
        seen.add(code_u)
        if len(out) >= limit:
            return out

    rest = sorted(c for c in allowed if c not in seen and needle in _fiat_ac_casefold(c))
    for c in rest:
        if len(out) >= limit:
            break
        out.append(CurrencyRow(code=c))
        seen.add(c)
    return out[:limit]

# Минимальная комиссия по умолчанию и нижняя граница при сохранении, %
MIN_GUARANTOR_COMMISSION_PERCENT = Decimal("0.1")
MAX_GUARANTOR_COMMISSION_PERCENT = Decimal("100")


def _validate_commission(value: Decimal | None) -> None:
    if value is None:
        return
    if value < MIN_GUARANTOR_COMMISSION_PERCENT or value > MAX_GUARANTOR_COMMISSION_PERCENT:
        raise ValueError(
            f"commission_percent must be between {MIN_GUARANTOR_COMMISSION_PERCENT} and {MAX_GUARANTOR_COMMISSION_PERCENT}"
        )


class GuarantorService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._repo = GuarantorDirectionRepository(session=session, redis=redis, settings=settings)
        self._space = SpaceService(session=session, redis=redis, settings=settings)
        self._users = WalletUserService(session=session, redis=redis, settings=settings)

    async def get_state(
        self,
        space: str,
        actor_wallet_address: str,
    ) -> tuple[GuarantorProfile, List[GuarantorDirection], bool]:
        """
        Профиль гаранта (с автосозданием с комиссией 0.1%), список направлений, флаг верификации актора.
        """
        owner_id = await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        user = await self._users.get_by_wallet_address(actor_wallet_address)
        if user is None:
            raise ValueError("Wallet user not found")

        profile = await self._repo.get_profile(owner_id, space)
        if profile is None:
            profile = await self._repo.upsert_profile(
                owner_id,
                space,
                commission_percent=MIN_GUARANTOR_COMMISSION_PERCENT,
            )
            await self._session.commit()
            await self._session.refresh(profile)

        directions = await self._repo.list_for_space(space)
        return profile, directions, user.is_verified

    async def patch_profile(
        self,
        space: str,
        actor_wallet_address: str,
        *,
        commission_percent: Any = ...,
        conditions_text: Any = ...,
    ) -> GuarantorProfile:
        owner_id = await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        if commission_percent is not ...:
            _validate_commission(commission_percent)
        row = await self._repo.upsert_profile(
            owner_id,
            space,
            commission_percent=commission_percent,
            conditions_text=conditions_text,
        )
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def create_direction(
        self,
        space: str,
        actor_wallet_address: str,
        *,
        currency_code: str,
        payment_code: str,
        payment_name: str | None = None,
        conditions_text: str | None = None,
        commission_percent: Decimal | None = None,
        sort_order: int = 0,
    ) -> GuarantorDirection:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        if commission_percent is not None:
            _validate_commission(commission_percent)
        row = await self._repo.create(
            space,
            currency_code=currency_code,
            payment_code=payment_code,
            payment_name=payment_name,
            conditions_text=conditions_text,
            commission_percent=commission_percent,
            sort_order=sort_order,
        )
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def delete_direction(
        self,
        space: str,
        direction_id: int,
        actor_wallet_address: str,
    ) -> bool:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        ok = await self._repo.delete(direction_id, space)
        if ok:
            await self._session.commit()
        return ok
