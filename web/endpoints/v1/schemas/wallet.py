"""Схемы API кошельков (по аналогии с garantex schemas/wallet.py)."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateWalletRequest(BaseModel):
    """Запрос на создание кошелька."""
    name: str = Field(..., description="Имя кошелька", max_length=255)
    mnemonic: str = Field(..., description="Мнемоническая фраза")


class UpdateWalletNameRequest(BaseModel):
    """Запрос на обновление имени кошелька."""
    name: str = Field(..., description="Новое имя", max_length=255)


class WalletResponse(BaseModel):
    """Ответ с данными кошелька."""
    id: int = Field(..., description="ID кошелька")
    name: str = Field(..., description="Имя кошелька")
    tron_address: str = Field(..., description="TRON адрес")
    ethereum_address: str = Field(..., description="Ethereum адрес")
    account_permissions: Optional[Dict[str, Any]] = Field(None, description="Права TRON аккаунта")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")


class WalletListResponse(BaseModel):
    """Список кошельков."""
    wallets: List[WalletResponse] = Field(..., description="Кошельки")
    total: int = Field(..., description="Всего записей")


class ManagerItemResponse(BaseModel):
    """Элемент списка менеджеров (WalletUser с доступом в админку)."""
    id: int = Field(..., description="ID пользователя")
    nickname: str = Field(..., description="Никнейм")
    wallet_address: str = Field(..., description="Адрес кошелька")
    blockchain: str = Field(..., description="Блокчейн")


class ManagerListResponse(BaseModel):
    """Список менеджеров."""
    managers: List[ManagerItemResponse] = Field(..., description="Менеджеры")
    total: int = Field(..., description="Всего записей")
