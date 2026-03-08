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


class AddManagerRequest(BaseModel):
    """Запрос на добавление менеджера (адрес + блокчейн + никнейм)."""
    wallet_address: str = Field(..., description="Адрес кошелька", max_length=255)
    blockchain: str = Field(..., description="Блокчейн: tron или ethereum")
    nickname: str = Field(..., description="Никнейм", max_length=100)


class UpdateManagerRequest(BaseModel):
    """Запрос на обновление менеджера (доступ в админку)."""
    access_to_admin_panel: bool = Field(..., description="Доступ в админ-панель")


class ManagerDidDocumentResponse(BaseModel):
    """DID и DID Document менеджера (один адрес/блокчейн)."""
    manager_nickname: str = Field(..., description="Никнейм менеджера")
    did: str = Field(..., description="DID (did:tron:... или did:ethr:...)")
    did_document: Dict[str, Any] = Field(..., description="DID Document")


class WalletDidDocEntry(BaseModel):
    """DID и DID Document для одного блокчейна (legacy)."""
    did: str = Field(..., description="DID")
    did_document: Dict[str, Any] = Field(..., description="DID Document (JSON)")


class WalletDidDocumentsResponse(BaseModel):
    """Ответ: DID и DID Document по TRON и Ethereum для кошелька (legacy)."""
    wallet_name: str = Field(..., description="Имя кошелька")
    tron: Optional[WalletDidDocEntry] = Field(None, description="TRON DID и DIDDoc")
    ethereum: Optional[WalletDidDocEntry] = Field(None, description="Ethereum DID и DIDDoc")


class WalletDidDocumentResponse(BaseModel):
    """Один DID и один DID Document кошелька (все адреса внутри)."""
    wallet_name: str = Field(..., description="Имя кошелька")
    did: str = Field(..., description="Уникальный DID кошелька (did:ruswift:{node}:wallet:{id})")
    did_document: Dict[str, Any] = Field(..., description="DID Document с TRON и Ethereum")
