"""
Схемы для invite API: создание ссылки, данные приглашения, подтверждение подписью.
"""
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class InviteLinkResponse(BaseModel):
    """Ответ после создания invite-link (только owner)."""

    invite_link: str = Field(..., description="Абсолютный URL для приглашения")
    expires_at: datetime = Field(..., description="Момент истечения ссылки")


class InvitePayloadResponse(BaseModel):
    """Публичные данные приглашения для страницы верификации (GET /v1/invite/{token})."""

    space_name: str = Field(..., description="Название спейса")
    inviter_nickname: str = Field(..., description="Кто пригласил (никнейм владельца)")
    roles: List[str] = Field(default_factory=list, description="Роли: owner, operator, reader")
    wallet_address: str = Field(..., description="Адрес кошелька для подписи")
    wallet_address_mask: str = Field(..., description="Маска адреса для отображения (T…xyz)")
    blockchain: str = Field(default="tron", description="Блокчейн")
    participant_nickname: str | None = Field(default=None, description="Никнейм участника")


class InviteNonceResponse(BaseModel):
    """Ответ с nonce для подписи (POST /v1/invite/{token}/nonce)."""

    nonce: str = Field(..., description="Nonce для подписи")
    message: str = Field(..., description="Сообщение для подписи")


class InviteConfirmRequest(BaseModel):
    """Тело запроса подтверждения приглашения (POST /v1/invite/{token}/confirm)."""

    signature: str = Field(..., description="Подпись сообщения (personal_sign)")


class InviteConfirmResponse(BaseModel):
    """Ответ после успешного confirm: JWT и redirect."""

    token: str = Field(..., description="JWT для авторизации")
    redirect_url: str = Field(..., description="URL для перехода (например /{space})")
    space: str = Field(..., description="Space (nickname) для перехода")
