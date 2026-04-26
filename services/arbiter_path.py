"""Разрешение сегмента пути /arbiter/{segment}: DID или nickname гаранта."""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import get_user_did
from db.models import WalletUser
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
        self._session = session
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
            print(f"DEBUG ArbiterPath: profile NOT FOUND for slug {slug}")
            return None
        try:
            pw = await self._space.get_primary_wallet(profile.space)
        except ValueError:
            print(f"DEBUG ArbiterPath: primary wallet NOT FOUND for space {profile.space}")
            return None
        addr = (pw.get("address") or "").strip()
        if not addr:
            print(f"DEBUG ArbiterPath: address EMPTY for space {profile.space}")
            return None
        bc = (pw.get("blockchain") or "tron").strip().lower()
        
        # Нам нужен DID именно арбитра (владельца профиля), а не спейса,
        # в котором этот профиль настроен.
        # Но в Simple режиме arbiter_did в URL часто соответствует DID WalletUser-а арбитра.
        
        # Получаем WalletUser арбитра
        stmt = select(WalletUser).where(WalletUser.id == profile.wallet_user_id)
        res = await self._session.execute(stmt)
        user = res.scalar_one_or_none()
        if user:
            return user.did
            
        return get_user_did(addr, bc)
