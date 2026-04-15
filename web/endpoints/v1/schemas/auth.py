"""
Схемы для auth API (nonce, verify, JWT ответы).
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class NonceRequest(BaseModel):
    """Запрос nonce для подписи."""

    wallet_address: str = Field(..., description="Адрес кошелька пользователя")


class NonceResponse(BaseModel):
    """Ответ с nonce и сообщением для подписи."""

    nonce: str = Field(..., description="Nonce для подписи")
    message: str = Field(..., description="Сообщение для подписи")


class VerifyRequest(BaseModel):
    """Запрос верификации подписи."""

    wallet_address: str = Field(..., description="Адрес кошелька пользователя")
    signature: str = Field(..., description="Подпись сообщения")
    message: Optional[str] = Field(
        None,
        description="Сообщение (опционально, если отличается от стандартного)",
    )


class AuthResponse(BaseModel):
    """Ответ с JWT, адресом и списком spaces (nicknames) после верификации."""

    token: str = Field(..., description="JWT токен для авторизации")
    wallet_address: str = Field(..., description="Адрес кошелька")
    spaces: List[str] = Field(
        default_factory=list,
        description="Список space (nickname), в которых участвует адрес",
    )


class InitRequest(BaseModel):
    """Запрос инициации нового пользователя (при пустых spaces)."""

    nickname: str = Field(..., min_length=1, max_length=100, description="Nickname пользователя")


class InitResponse(BaseModel):
    """Ответ после успешной инициации: клиент сохраняет токен от verify и переходит в space."""

    space: str = Field(..., description="Nickname (space), в который перейти")


class EnsureSpaceResponse(BaseModel):
    """Ответ для /v1/auth/tron/ensure-space: выбрать или создать подходящий space."""

    space: str = Field(..., description="Nickname (space), который нужно использовать")
    created: bool = Field(False, description="True если space был создан на лету")
    primary_matched: bool = Field(
        False,
        description="True если найден space, где primary wallet совпал с текущим адресом",
    )
