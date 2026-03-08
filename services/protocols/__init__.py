"""
Aries protocol handlers for DIDComm messaging

This package provides implementations of Aries RFC protocols
with support for various cryptographic key types (Ethereum, RSA, EC).
"""

from services.protocols.base import ProtocolHandler
from services.protocols.trust_ping import TrustPingHandler
from services.protocols.connection import ConnectionHandler
from services.protocols.schemas import (
    TrustPingMessage,
    TrustPingResponse,
    TrustPingBody,
    TrustPingResponseBody,
    BasicMessage,
    BasicMessageBody,
    TimingDecorator,
    ConnectionInvitation,
    ConnectionInvitationBody,
    ConnectionRequest,
    ConnectionRequestBody,
    ConnectionResponse,
    ConnectionResponseBody,
)

__all__ = [
    "ProtocolHandler",
    "TrustPingHandler",
    "ConnectionHandler",
    "TrustPingMessage",
    "TrustPingResponse",
    "TrustPingBody",
    "TrustPingResponseBody",
    "BasicMessage",
    "BasicMessageBody",
    "TimingDecorator",
    "ConnectionInvitation",
    "ConnectionInvitationBody",
    "ConnectionRequest",
    "ConnectionRequestBody",
    "ConnectionResponse",
    "ConnectionResponseBody",
]

# Protocol registry for automatic routing
PROTOCOL_HANDLERS = {
    "trust-ping": TrustPingHandler,
    "connections": ConnectionHandler,
}


def get_protocol_handler(protocol_name: str):
    """
    Get protocol handler class by protocol name

    Args:
        protocol_name: Name of the protocol (e.g., "trust-ping", "connections")

    Returns:
        Protocol handler class or None if not found
    """
    return PROTOCOL_HANDLERS.get(protocol_name)
