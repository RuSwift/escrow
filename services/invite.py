"""
Сервис приглашений в спейс: одноразовые ссылки (Redis), резолв по токену, подтверждение подписью.
Поддержка только TronLink (nonce + verify через TronAuth).
"""
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WalletUserSubRole
from repos.wallet_user import WalletUserRepository
from settings import Settings

INVITE_PREFIX = "invite:"
INVITE_TTL_SEC = 7 * 24 * 3600  # 7 days


@dataclass
class InvitePayload:
    """Данные приглашения для отображения на странице верификации."""
    sub_id: int
    space_name: str
    inviter_nickname: str
    roles: List[WalletUserSubRole]
    wallet_address: str
    blockchain: str
    participant_nickname: Optional[str]


class InviteService:
    """Создание, резолв и подтверждение invite-токенов (Redis + репозиторий)."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ):
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = WalletUserRepository(
            session=session, redis=redis, settings=settings
        )

    def _key(self, token: str) -> str:
        return f"{INVITE_PREFIX}{token.strip()}"

    async def create_token(self, sub_id: int, space: str) -> tuple[str, datetime]:
        """Создать invite-токен, сохранить в Redis. Возвращает (token, expires_at)."""
        token = secrets.token_urlsafe(24)
        key = self._key(token)
        payload = json.dumps({"sub_id": sub_id, "space": space})
        await self._redis.setex(key, INVITE_TTL_SEC, payload)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=INVITE_TTL_SEC)
        return token, expires_at

    async def get_invite_by_token(self, token: str) -> Optional[InvitePayload]:
        """
        Резолв токена: Redis -> sub_id, space; загрузить sub и owner.
        Возвращает None, если токен не найден, истёк или уже использован.
        """
        key = self._key(token)
        raw = await self._redis.get(key)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            sub_id = int(data.get("sub_id"))
            space = (data.get("space") or "").strip()
            if not space:
                return None
        except (TypeError, ValueError, KeyError):
            return None
        sub = await self._repo.get_sub_by_id(sub_id)
        if not sub:
            return None
        owner = await self._repo.get(sub.wallet_user_id)
        if not owner or owner.nickname != space:
            return None
        roles = []
        for r in (sub.roles or []):
            try:
                roles.append(WalletUserSubRole(r))
            except ValueError:
                continue
        return InvitePayload(
            sub_id=sub.id,
            space_name=space,
            inviter_nickname=owner.nickname or space,
            roles=roles,
            wallet_address=sub.wallet_address,
            blockchain=sub.blockchain or "tron",
            participant_nickname=sub.nickname,
        )

    async def consume_token(self, token: str) -> None:
        """Удалить токен из Redis (одноразовое использование)."""
        key = self._key(token)
        await self._redis.delete(key)

    async def set_sub_verified(self, sub_id: int) -> bool:
        """Установить is_verified=True для участника. Возвращает True, если обновлено."""
        return await self._repo.set_sub_verified(sub_id, True)

    async def commit(self) -> None:
        """Зафиксировать изменения в БД (после set_sub_verified и т.д.)."""
        await self._session.commit()


__all__ = ["InviteService", "InvitePayload", "INVITE_TTL_SEC"]
