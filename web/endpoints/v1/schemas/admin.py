"""
Схемы для Admin API: логин (password/TRON), пароль, TRON-адреса.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    """Запрос входа админа по логину и паролю."""

    username: str = Field(..., description="Имя пользователя админа")
    password: str = Field(..., description="Пароль")


class AdminLoginResponse(BaseModel):
    """Ответ с JWT после успешного входа админа."""

    success: bool = Field(..., description="Успех операции")
    token: str = Field(..., description="JWT токен для авторизации")
    message: str = Field(..., description="Сообщение")


class AdminTronNonceRequest(BaseModel):
    """Запрос nonce для TRON-подписи админа."""

    tron_address: str = Field(..., description="TRON-адрес")


class AdminTronNonceResponse(BaseModel):
    """Ответ с nonce и сообщением для подписи."""

    nonce: str = Field(..., description="Nonce")
    message: str = Field(..., description="Сообщение для подписи")


class AdminTronVerifyRequest(BaseModel):
    """Запрос верификации TRON-подписи админа."""

    tron_address: str = Field(..., description="TRON-адрес")
    signature: str = Field(..., description="Подпись сообщения")
    message: str = Field(..., description="Подписанное сообщение")


class SetPasswordRequest(BaseModel):
    """Установка или смена пароля админа."""

    username: str = Field(..., description="Имя пользователя")
    password: str = Field(..., description="Новый пароль")


class ChangePasswordRequest(BaseModel):
    """Смена пароля (требуется старый пароль)."""

    old_password: str = Field(..., description="Текущий пароль")
    new_password: str = Field(..., description="Новый пароль")


class ChangeResponse(BaseModel):
    """Ответ об успешном изменении."""

    success: bool = Field(..., description="Успех")
    message: str = Field(..., description="Сообщение")


class AdminInfoResponse(BaseModel):
    """Информация об админе."""

    id: int = Field(..., description="ID админа")
    has_password: bool = Field(..., description="Настроена ли парольная авторизация")
    username: Optional[str] = Field(None, description="Имя пользователя")
    tron_addresses_count: int = Field(..., description="Количество TRON-адресов")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")


class TronAddressItem(BaseModel):
    """Один TRON-адрес админа."""

    id: int = Field(..., description="ID записи")
    tron_address: str = Field(..., description="TRON-адрес")
    label: Optional[str] = Field(None, description="Метка")
    is_active: bool = Field(..., description="Активен ли адрес")
    created_at: datetime = Field(..., description="Дата добавления")
    updated_at: datetime = Field(..., description="Дата обновления")


class TronAddressList(BaseModel):
    """Список TRON-адресов админа."""

    addresses: List[TronAddressItem] = Field(..., description="Список адресов")


class AddTronAddressRequest(BaseModel):
    """Добавление TRON-адреса в whitelist."""

    tron_address: str = Field(..., description="TRON-адрес")
    label: Optional[str] = Field(None, description="Метка")


class UpdateTronAddressRequest(BaseModel):
    """Обновление TRON-адреса или метки."""

    tron_address: Optional[str] = Field(None, description="Новый TRON-адрес")
    label: Optional[str] = Field(None, description="Новая метка")


class ToggleTronAddressRequest(BaseModel):
    """Включение/выключение TRON-адреса."""

    is_active: bool = Field(..., description="Активен ли адрес")
