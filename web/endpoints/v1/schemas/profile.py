"""
Схемы для profile и billing API (ответы и запросы).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    """Ответ с профилем пользователя (для JSON: created_at/updated_at как ISO-строки)."""

    wallet_address: str = Field(..., description="Адрес кошелька")
    blockchain: str = Field(..., description="Тип блокчейна")
    did: str = Field(..., description="DID")
    nickname: str = Field(..., description="Никнейм")
    avatar: Optional[str] = Field(None, description="Аватар (base64 data URI)")
    access_to_admin_panel: bool = Field(..., description="Доступ в админ-панель")
    is_verified: bool = Field(..., description="Верификация")
    balance_usdt: float = Field(..., description="Баланс USDT")
    created_at: str = Field(..., description="Дата создания (ISO)")
    updated_at: str = Field(..., description="Дата обновления (ISO)")


class UpdateProfileRequest(BaseModel):
    """Запрос на обновление профиля (никнейм и/или аватар)."""

    nickname: Optional[str] = Field(None, max_length=100, description="Никнейм")
    avatar: Optional[str] = Field(None, description="Аватар (base64 data URI или пустая строка для сброса)")


class BillingItem(BaseModel):
    """Один элемент истории биллинга."""

    id: int
    wallet_user_id: int
    usdt_amount: float
    created_at: datetime


class BillingList(BaseModel):
    """Список записей биллинга с пагинацией."""

    transactions: list[BillingItem]
    total: int
    page: int
    page_size: int
