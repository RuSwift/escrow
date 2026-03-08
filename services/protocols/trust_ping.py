"""
Trust Ping protocol handler (Aries RFC 0048)

Reference: https://github.com/hyperledger/aries-rfcs/tree/main/features/0048-trust-ping
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Union, Dict, Any
from didcomm.crypto import EthKeyPair, KeyPair
from didcomm.message import DIDCommMessage
from services.protocols.base import ProtocolHandler
from services.protocols.schemas import TrustPingMessage, TrustPingResponse, TrustPingBody, TrustPingResponseBody


class TrustPingHandler(ProtocolHandler):
    """
    Handler for Trust Ping protocol (RFC 0048)

    Trust Ping is used to test connectivity and responsiveness
    between DIDComm agents. It's a simple ping-pong protocol
    where one agent sends a ping and optionally requests a response.
    """

    protocol_name = "trust-ping"
    supported_versions = ["1.0"]

    # Message types
    MSG_TYPE_PING = "https://didcomm.org/trust-ping/1.0/ping"
    MSG_TYPE_PING_RESPONSE = "https://didcomm.org/trust-ping/1.0/ping-response"

    def __init__(self, my_key: Union[EthKeyPair, KeyPair], my_did: str):
        """
        Initialize Trust Ping handler

        Args:
            my_key: Node's private key
            my_did: Node's DID
        """
        super().__init__(my_key, my_did)

    async def handle_message(
        self,
        message: DIDCommMessage,
        sender_public_key: Optional[bytes] = None,
        sender_key_type: Optional[str] = None
    ) -> Optional[DIDCommMessage]:
        """
        Handle incoming Trust Ping message

        Args:
            message: Unpacked DIDComm message
            sender_public_key: Sender's public key
            sender_key_type: Sender's key type

        Returns:
            Response message if needed, None otherwise
        """
        # Route to appropriate handler based on message type
        if message.type == self.MSG_TYPE_PING:
            return await self._handle_ping(message)
        elif message.type == self.MSG_TYPE_PING_RESPONSE:
            return await self._handle_ping_response(message)
        else:
            raise ValueError(f"Unsupported message type: {message.type}")

    async def _handle_ping(self, message: DIDCommMessage) -> Optional[DIDCommMessage]:
        """
        Handle incoming ping message

        Args:
            message: Ping message

        Returns:
            Pong response if requested, None otherwise
        """
        # Extract response_requested flag from body
        response_requested = message.body.get("response_requested", True)

        # If response is not requested, just acknowledge receipt
        if not response_requested:
            return None

        # Create response message
        response = self.create_ping_response(
            original_ping_id=message.id,
            sender_did=message.from_did
        )

        return response

    async def _handle_ping_response(self, message: DIDCommMessage) -> Optional[DIDCommMessage]:
        """
        Handle incoming ping response (pong)

        This is typically just logged/stored, no further response needed

        Args:
            message: Ping response message

        Returns:
            None (no response needed)
        """
        # Log or store the ping response for metrics/monitoring
        # In a production system, you'd update connection status, measure latency, etc.
        return None

    def create_ping(
        self,
        recipient_did: str,
        response_requested: bool = True,
        comment: Optional[str] = None,
        expires_time: Optional[str] = None
    ) -> DIDCommMessage:
        """
        Create a new ping message

        Args:
            recipient_did: Recipient's DID
            response_requested: Whether to request a response
            comment: Optional human-readable comment
            expires_time: Optional expiration time (ISO 8601)

        Returns:
            DIDComm message ready to send
        """
        # Create message body
        body = {
            "response_requested": response_requested
        }

        if comment:
            body["comment"] = comment

        # Create DIDComm message
        message = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=self.MSG_TYPE_PING,
            body=body,
            from_did=self.my_did,
            to=[recipient_did],
            created_time=datetime.now(timezone.utc).isoformat(),
            expires_time=expires_time
        )

        return message

    def create_ping_response(
        self,
        original_ping_id: str,
        sender_did: Optional[str] = None,
        comment: Optional[str] = None
    ) -> DIDCommMessage:
        """
        Create a ping response (pong) message

        Args:
            original_ping_id: ID of the original ping message (for threading)
            sender_did: Original sender's DID
            comment: Optional human-readable comment

        Returns:
            DIDComm message ready to send
        """
        # Create message body (usually empty for ping response)
        body = {}
        if comment:
            body["comment"] = comment

        # Create response with thread ID referencing original ping
        message = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=self.MSG_TYPE_PING_RESPONSE,
            body=body,
            from_did=self.my_did,
            to=[sender_did] if sender_did else [],
            created_time=datetime.now(timezone.utc).isoformat(),
            thid=original_ping_id  # Thread ID references the original ping
        )

        return message

    def validate_ping_message(self, message: DIDCommMessage) -> bool:
        """
        Validate that a message is a valid ping message

        Args:
            message: DIDComm message to validate

        Returns:
            True if valid
        """
        # Check message type
        if not self.validate_message_type(message, self.MSG_TYPE_PING):
            return False

        # Validate body structure
        if not isinstance(message.body, dict):
            return False

        # response_requested is optional, defaults to true
        if "response_requested" in message.body:
            if not isinstance(message.body["response_requested"], bool):
                return False

        return True

    def validate_ping_response(self, message: DIDCommMessage) -> bool:
        """
        Validate that a message is a valid ping response

        Args:
            message: DIDComm message to validate

        Returns:
            True if valid
        """
        # Check message type
        if not self.validate_message_type(message, self.MSG_TYPE_PING_RESPONSE):
            return False

        # Ping response should have a thread ID
        if not hasattr(message, 'thid') or not message.thid:
            return False

        return True
