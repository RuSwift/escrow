"""
Сервис уведомлений по DID. Пока только контракт send_message; транспорт подключится позже.
"""
from __future__ import annotations

import logging
from typing import TypedDict

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from settings import Settings

logger = logging.getLogger(__name__)


class NotifyRecipient(TypedDict):
    """Получатель уведомления."""

    did: str


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

    async def send_message(self, to: list[NotifyRecipient], text: str) -> None:
        """
        Отправить текстовое сообщение списку получателей.

        :param to: список объектов с ключом ``did`` (идентификатор получателя).
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
        logger.debug(
            "NotifyService.send_message: recipients=%d text_len=%d",
            len(to),
            len(text),
        )
