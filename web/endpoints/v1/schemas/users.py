"""Схемы API пользователей (admin: список, CRUD, баланс, DID Document)."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserItem(BaseModel):
    """Элемент списка / один пользователь."""
    id: int = Field(..., description="ID пользователя")
    wallet_address: str = Field(..., description="Адрес кошелька")
    blockchain: str = Field(..., description="Блокчейн")
    nickname: str = Field(..., description="Никнейм")
    is_verified: bool = Field(..., description="Верифицирован")
    access_to_admin_panel: bool = Field(..., description="Доступ в админ-панель")
    balance_usdt: float = Field(..., description="Баланс USDT")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: Optional[datetime] = Field(None, description="Дата обновления")


class UserListResponse(BaseModel):
    """Список пользователей с пагинацией."""
    users: List[UserItem] = Field(..., description="Пользователи")
    total: int = Field(..., description="Всего записей")


class CreateUserRequest(BaseModel):
    """Запрос на создание пользователя (админ)."""
    wallet_address: str = Field(..., description="Адрес кошелька", max_length=255)
    blockchain: str = Field(..., description="Блокчейн: tron или ethereum", max_length=20)
    nickname: str = Field(..., description="Никнейм", max_length=100)
    is_verified: bool = Field(False, description="Верифицирован")
    access_to_admin_panel: bool = Field(False, description="Доступ в админ-панель")


class UpdateUserRequest(BaseModel):
    """Запрос на обновление пользователя (nickname, is_verified, access_to_admin_panel)."""
    nickname: Optional[str] = Field(None, max_length=100, description="Никнейм")
    is_verified: Optional[bool] = Field(None, description="Верифицирован")
    access_to_admin_panel: Optional[bool] = Field(None, description="Доступ в админ-панель")


class BalanceOperationRequest(BaseModel):
    """Запрос на пополнение или списание баланса."""
    operation_type: str = Field(..., description="replenish или withdraw")
    amount: Decimal = Field(..., gt=0, description="Сумма USDT")


class UserDidDocumentResponse(BaseModel):
    """DID и DID Document пользователя (для diddoc-modal)."""
    did: str = Field(..., description="DID")
    did_document: Dict[str, Any] = Field(..., description="DID Document (JSON)")
