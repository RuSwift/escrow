"""
Схемы для DIDComm API (приём/отправка сообщений).
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DIDCommMessageRequest(BaseModel):
    """Тело запроса входящего DIDComm сообщения."""

    message: Dict[str, Any] = Field(..., description="Packed DIDComm message")
    sender_public_key: Optional[str] = Field(None, description="Sender's public key (hex)")
    sender_key_type: Optional[str] = Field(None, description="Sender's key type (ETH, RSA, EC)")


class DIDCommMessageResponse(BaseModel):
    """Ответ обработки DIDComm сообщения."""

    success: bool = Field(..., description="Whether message was handled successfully")
    message: Optional[str] = Field(None, description="Status message")
    response: Optional[Dict[str, Any]] = Field(None, description="Response message if any")


class SendTrustPingRequest(BaseModel):
    """Тело запроса отправки Trust Ping."""

    recipient_did: str = Field(..., description="DID получателя")
    response_requested: bool = Field(True, description="Whether a response is requested")
    comment: Optional[str] = Field(None, description="Optional comment for the ping message")
