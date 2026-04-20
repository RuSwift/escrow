"""Разрешение сегмента пути /arbiter/{segment}: DID или nickname гаранта."""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import get_user_did
from repos.guarantor_direction import GuarantorDirectionRepository
from services.space import SpaceService
from settings import Settings


class ArbiterPathResolveService:
    """Сегмент URL → arbiter_did для PaymentRequest / SimpleResolve."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._guarantor_repo = GuarantorDirectionRepository(
            session=session, redis=redis, settings=settings
        )
        self._space = SpaceService(session=session, redis=redis, settings=settings)

    async def to_arbiter_did(self, segment: str) -> str | None:
        raw = (segment or "").strip()
        if not raw:
            return None
        if raw.lower().startswith("did:"):
            return raw
        slug = raw.lower()
        profile = await self._guarantor_repo.get_profile_by_arbiter_public_slug(slug)
        if profile is None:
            return None
        try:
            pw = await self._space.get_primary_wallet(profile.space)
        except ValueError:
            return None
        addr = (pw.get("address") or "").strip()
        if not addr:
            return None
        bc = (pw.get("blockchain") or "tron").strip().lower()
        return get_user_did(addr, bc)
