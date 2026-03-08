"""
Схемы для Node API: инициализация ноды, key-info, service endpoint.
Ориентир: garantex schemas/node, node.py /api/node.
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class NodeInitRequest(BaseModel):
    """Запрос инициализации ноды из мнемоники."""

    mnemonic: str = Field(..., description="Мнемоническая фраза")


class NodeInitPemRequest(BaseModel):
    """Запрос инициализации ноды из PEM."""

    pem_data: str = Field(..., description="PEM данные ключа")
    password: Optional[str] = Field(None, description="Пароль для расшифровки PEM")


class NodeInitResponse(BaseModel):
    """Ответ после успешной инициализации ноды."""

    success: bool = Field(..., description="Успех операции")
    message: str = Field(..., description="Сообщение")
    did: str = Field(..., description="Peer DID ноды")
    address: Optional[str] = Field(None, max_length=42, description="Ethereum-адрес")
    key_type: str = Field(..., description="Тип ключа: mnemonic или pem")
    public_key: str = Field(..., description="Публичный ключ в hex")
    did_document: Dict[str, Any] = Field(..., description="DID Document (JSON)")


class AdminConfiguredResponse(BaseModel):
    """Статус настройки админа."""

    configured: bool = Field(..., description="Настроен ли хотя бы один способ входа")
    has_password: bool = Field(..., description="Настроен ли пароль")
    tron_addresses_count: int = Field(..., description="Количество TRON-адресов")


class SetServiceEndpointRequest(BaseModel):
    """Установка service endpoint ноды."""

    service_endpoint: str = Field(..., description="URL эндпоинта")


class ServiceEndpointResponse(BaseModel):
    """Текущий service endpoint."""

    service_endpoint: Optional[str] = Field(None, description="URL эндпоинта или None")
    configured: bool = Field(..., description="Задан ли endpoint")


class TestServiceEndpointRequest(BaseModel):
    """Запрос проверки доступности endpoint."""

    service_endpoint: str = Field(..., description="URL для проверки")


class TestServiceEndpointResponse(BaseModel):
    """Результат проверки endpoint."""

    success: bool = Field(..., description="Доступен ли endpoint")
    status_code: Optional[int] = Field(None, description="HTTP код ответа")
    message: str = Field(..., description="Сообщение")
    response_time_ms: Optional[float] = Field(None, description="Время ответа в мс")
