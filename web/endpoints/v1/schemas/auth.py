"""
Схемы для auth API (nonce, verify, JWT ответы).
"""
from typing import Optional

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
    """Ответ с JWT и адресом после успешной верификации."""

    token: str = Field(..., description="JWT токен для авторизации")
    wallet_address: str = Field(..., description="Адрес кошелька")
