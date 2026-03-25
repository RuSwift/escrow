"""
Сервис уведомлений по DID. Пока только контракт send_message; транспорт подключится позже.
"""
from __future__ import annotations

import logging
from typing import Literal, NotRequired, TypedDict

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import get_user_did
from db.models import WalletUserSubRole
from repos.wallet_user import WalletUserRepository
from settings import Settings

logger = logging.getLogger(__name__)

# Роли для фильтрации получателей; в БД у субаккаунтов owner | operator | reader.
# «admin» трактуем как синоним owner (полного доступа в спейсе).
NotifyRole = Literal["admin", "owner", "operator", "reader"]

_ALLOWED_SUB_ROLES = frozenset({"owner", "operator", "reader"})
_ROLE_ALIASES = {"admin": "owner"}


class NotifyRecipient(TypedDict):
    """
    Получатель уведомления.

    ``scope`` — опционально: идентификатор спейса (например nickname владельца), если важен для разделения контекста.
    """

    did: str
    scope: NotRequired[str]


class NotifyService:
    """Рассылка сообщений получателям по DID."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._wallet_users = WalletUserRepository(
            session=session, redis=redis, settings=settings
        )

    @staticmethod
    def _normalize_roles(roles: list[NotifyRole]) -> frozenset[str]:
        out: set[str] = set()
        for raw in roles:
            key = (raw or "").strip().lower()
            key = _ROLE_ALIASES.get(key, key)
            if key not in _ALLOWED_SUB_ROLES:
                raise ValueError(
                    f"unsupported notify role {raw!r}; "
                    f"expected one of admin, owner, operator, reader"
                )
            out.add(key)
        return frozenset(out)

    @staticmethod
    def _sub_has_any_role(
        sub_roles: list[WalletUserSubRole], wanted: frozenset[str]
    ) -> bool:
        for r in sub_roles:
            val = r.value if isinstance(r, WalletUserSubRole) else str(r)
            if val in wanted:
                return True
        return False

    async def notify_roles(
        self, scope: str, roles: list[NotifyRole], text: str
    ) -> None:
        """
        Оповестить участников спейса (субаккаунты владельца), у которых есть хотя бы одна
        из указанных ролей.

        :param scope: идентификатор спейса — ``WalletUser.nickname`` владельца (как в API спейса).
        :param roles: подмножество ``admin`` (как owner), ``owner``, ``operator``, ``reader``.
        :param text: текст сообщения (те же правила, что у ``send_message``).
        """
        scope_key = (scope or "").strip()
        if not scope_key:
            raise ValueError("scope is required")
        if not roles:
            return
        wanted = self._normalize_roles(roles)
        owner = await self._wallet_users.get_by_nickname(scope_key)
        if not owner:
            logger.warning(
                "NotifyService.notify_roles: scope %r not found (no WalletUser)",
                scope_key,
            )
            return
        subs = await self._wallet_users.list_subs(owner.id)
        recipients: list[NotifyRecipient] = []
        seen_did: set[str] = set()
        for sub in subs:
            if sub.is_blocked:
                continue
            if not self._sub_has_any_role(sub.roles, wanted):
                continue
            did = get_user_did(sub.wallet_address, sub.blockchain)
            if did in seen_did:
                continue
            seen_did.add(did)
            recipients.append({"did": did, "scope": scope_key})
        await self.send_message(recipients, text)

    async def send_message(self, to: list[NotifyRecipient], text: str) -> None:
        """
        Отправить текстовое сообщение списку получателей.

        :param to: список объектов с ключом ``did``; опционально ``scope`` (контекст спейса).
        :param text: текст сообщения.
        """
        if not text or not str(text).strip():
            raise ValueError("text is required")
        if not to:
            return
        for i, recipient in enumerate(to):
            did = (recipient.get("did") or "").strip()
            if not did:
                raise ValueError(f"recipient at index {i} must have a non-empty did")
            if "scope" in recipient:
                sc = recipient.get("scope")
                if sc is None:
                    continue
                if not str(sc).strip():
                    raise ValueError(
                        f"recipient at index {i} must not have empty scope when key is set"
                    )
        logger.debug(
            "NotifyService.send_message: recipients=%d text_len=%d",
            len(to),
            len(text),
        )
