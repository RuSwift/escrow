"""Сервис UI-предпочтений: только owner/operator спейса, ключ — WalletUser.id актора."""
from __future__ import annotations

from typing import Any, Dict

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from repos.wallet_user import WalletUserRepository
from repos.wallet_space_ui_prefs import WalletSpaceUIPrefsRepository
from services.space import SpaceService
from settings import Settings


class WalletSpaceUIPrefsService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._prefs = WalletSpaceUIPrefsRepository(session)
        self._users = WalletUserRepository(session=session, redis=redis, settings=settings)
        self._space = SpaceService(session=session, redis=redis, settings=settings)

    async def get_prefs(
        self,
        space: str,
        actor_wallet_address: str,
    ) -> Dict[str, Any]:
        await self._space.ensure_owner_or_operator(space, actor_wallet_address)
        user = await self._users.get_by_wallet_address((actor_wallet_address or "").strip())
        if not user:
            raise ValueError("Wallet user not found")
        return await self._prefs.get_payload(user.id, space)

    async def patch_prefs(
        self,
        space: str,
        actor_wallet_address: str,
        patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        await self._space.ensure_owner_or_operator(space, actor_wallet_address)
        user = await self._users.get_by_wallet_address((actor_wallet_address or "").strip())
        if not user:
            raise ValueError("Wallet user not found")
        if not isinstance(patch, dict):
            raise ValueError("Invalid patch body")
        merged = await self._prefs.merge_payload(user.id, space, patch)
        await self._session.commit()
        return merged
