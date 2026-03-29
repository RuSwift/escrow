"""
Сервис уведомлений по DID. Пока только контракт send_message; транспорт подключится позже.
"""
from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any, Literal, NotRequired, TypedDict

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import get_user_did
from db.models import WalletUserSubRole
from i18n.translations import get_translation
from repos.wallet_user import WalletUserRepository
from settings import Settings

logger = logging.getLogger(__name__)

# Роли для фильтрации получателей; в БД у субаккаунтов owner | operator | reader.
# «admin» трактуем как синоним owner (полного доступа в спейсе).
NotifyRole = Literal["admin", "owner", "operator", "reader"]

_ALLOWED_SUB_ROLES = frozenset({"owner", "operator", "reader"})
_ROLE_ALIASES = {"admin": "owner"}

_EVENT_I18N_KEY: dict[str, str] = {
    "ramp_wallet_created": "notify.ramp_wallet_created",
    "ramp_wallet_deleted": "notify.ramp_wallet_deleted",
    "multisig_configured_active": "notify.multisig_configured_active",
    "multisig_reconfigured_active": "notify.multisig_reconfigured_active",
    "multisig_reconfigured_noop": "notify.multisig_reconfigured_noop",
}


class RampNotifyEvent(StrEnum):
    """События Ramp / multisig для текстов уведомлений (см. ``NotifyService._message_for_event``)."""

    RAMP_WALLET_CREATED = "ramp_wallet_created"
    RAMP_WALLET_DELETED = "ramp_wallet_deleted"
    MULTISIG_CONFIGURED_ACTIVE = "multisig_configured_active"
    MULTISIG_RECONFIGURED_ACTIVE = "multisig_reconfigured_active"
    MULTISIG_RECONFIGURED_NOOP = "multisig_reconfigured_noop"


class NotifyRecipient(TypedDict):
    """
    Получатель уведомления.

    ``scope`` — опционально: идентификатор спейса (например nickname владельца), если важен для разделения контекста.
    """

    did: str
    scope: NotRequired[str]


def _p(payload: dict[str, Any], key: str) -> str:
    v = payload.get(key)
    if v is None or v == "":
        return "—"
    return str(v)


def _normalize_notify_locale(raw: str | None) -> str:
    """Только ru/en для уведомлений; иначе и при пустом значении — ru."""
    if not raw or not str(raw).strip():
        return "ru"
    code = str(raw).strip().split("-", maxsplit=1)[0].lower()
    if code in ("ru", "en"):
        return code
    return "ru"


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

    async def _language_for_scope(self, scope: str) -> str:
        """
        Язык уведомлений: ``WalletUser.profile.language`` владельца спейса (scope = nickname);
        если нет или неподдерживаемый — ``ru``.
        """
        scope_key = (scope or "").strip()
        if not scope_key:
            return "ru"
        owner = await self._wallet_users.get_by_nickname(scope_key)
        if not owner or not owner.profile:
            return "ru"
        lang = getattr(owner.profile, "language", None)
        return _normalize_notify_locale(lang if isinstance(lang, str) else None)

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

    @staticmethod
    def _message_for_event(
        event: str, payload: dict[str, Any], *, language: str
    ) -> str:
        ev = str(event)
        msg_key = _EVENT_I18N_KEY.get(ev)
        if not msg_key:
            logger.warning("NotifyService: unknown event %r", event)
            return f"[{ev}] wallet_id={_p(payload, 'wallet_id')}"
        lang = _normalize_notify_locale(language)
        params = {
            "wallet_name": _p(payload, "wallet_name"),
            "wallet_id": _p(payload, "wallet_id"),
            "role": _p(payload, "role"),
            "tron_address": _p(payload, "tron_address"),
        }
        return get_translation(msg_key, lang, **params)

    async def notify_roles_event(
        self,
        scope: str,
        roles: list[NotifyRole],
        event: str,
        payload: dict[str, Any],
        *,
        language: str | None = None,
    ) -> None:
        if language is not None and str(language).strip():
            resolved = _normalize_notify_locale(language)
        else:
            resolved = await self._language_for_scope(scope)
        text = self._message_for_event(event, payload, language=resolved)
        await self.notify_roles(scope, roles, text)

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
