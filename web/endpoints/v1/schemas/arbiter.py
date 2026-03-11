"""Схемы API арбитра (адреса арбитража)."""
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class CreateArbiterRequest(BaseModel):
    """Запрос на создание адреса арбитра."""
    name: str = Field(..., description="Имя адреса арбитра", max_length=255)
    mnemonic: str = Field(..., description="Мнемоническая фраза для генерации адресов")


class UpdateArbiterNameRequest(BaseModel):
    """Запрос на обновление имени адреса арбитра."""
    name: str = Field(..., description="Новое имя", max_length=255)


class ArbiterAddressResponse(BaseModel):
    """Ответ с данными адреса арбитра."""
    id: int = Field(..., description="ID записи")
    name: str = Field(..., description="Имя")
    tron_address: str = Field(..., description="TRON адрес")
    ethereum_address: str = Field(..., description="Ethereum адрес")
    is_active: bool = Field(..., description="Активный арбитр (True) или резервный (False)")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")


class ArbiterAddressListResponse(BaseModel):
    """Список адресов арбитра."""
    addresses: List[ArbiterAddressResponse] = Field(..., description="Адреса арбитра")
    total: int = Field(..., description="Всего записей")
