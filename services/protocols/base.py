"""
Base protocol handler for Aries protocols
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, List
from didcomm.crypto import EthKeyPair, KeyPair
from didcomm.message import DIDCommMessage, pack_message, unpack_message


class ProtocolHandler(ABC):
    """
    Abstract base class for Aries protocol handlers

    All protocol handlers must inherit from this class and implement
    the handle_message method.
    """

    # Protocol identifier (e.g., "trust-ping", "issue-credential")
    protocol_name: str = ""

    # Supported protocol versions
    supported_versions: List[str] = ["1.0"]

    def __init__(self, my_key: Union[EthKeyPair, KeyPair], my_did: str):
        """
        Initialize protocol handler

        Args:
            my_key: Node's private key (EthKeyPair for Ethereum, KeyPair for RSA/EC)
            my_did: Node's DID identifier
        """
        self.my_key = my_key
        self.my_did = my_did

    @abstractmethod
    async def handle_message(
        self,
        message: DIDCommMessage,
        sender_public_key: Optional[bytes] = None,
        sender_key_type: Optional[str] = None
    ) -> Optional[DIDCommMessage]:
        """
        Handle incoming protocol message

        Args:
            message: Unpacked DIDComm message
            sender_public_key: Sender's public key (for signature verification)
            sender_key_type: Sender's key type ("ETH", "RSA", "EC")

        Returns:
            Response message if needed, None otherwise
        """
        pass

    def pack_response(
        self,
        response: DIDCommMessage,
        recipient_public_keys: List[bytes],
        encrypt: bool = True
    ) -> Dict[str, Any]:
        """
        Pack response message for sending

        Args:
            response: DIDComm message to pack
            recipient_public_keys: List of recipient public keys
            encrypt: Whether to encrypt the message

        Returns:
            Packed message ready for transmission
        """
        return pack_message(
            response,
            self.my_key,
            recipient_public_keys,
            encrypt=encrypt
        )

    def unpack_message_internal(
        self,
        packed_message: Dict[str, Any],
        sender_public_key: Optional[bytes] = None,
        sender_key_type: Optional[str] = None
    ) -> DIDCommMessage:
        """
        Unpack incoming message

        Args:
            packed_message: Packed DIDComm message
            sender_public_key: Expected sender's public key
            sender_key_type: Sender's key type

        Returns:
            Unpacked DIDComm message
        """
        return unpack_message(
            packed_message,
            self.my_key,
            sender_public_key=sender_public_key,
            sender_key_type=sender_key_type
        )

    def validate_message_type(self, message: DIDCommMessage, expected_type: str) -> bool:
        """
        Validate that message type matches expected type

        Args:
            message: DIDComm message
            expected_type: Expected message type URI

        Returns:
            True if message type matches
        """
        return message.type == expected_type

    def extract_protocol_from_type(self, message_type: str) -> Optional[str]:
        """
        Extract protocol name from message type URI

        Example: "https://didcomm.org/trust-ping/1.0/ping" -> "trust-ping"

        Args:
            message_type: Full message type URI

        Returns:
            Protocol name or None
        """
        try:
            parts = message_type.split('/')
            if len(parts) >= 4:
                return parts[-3]  # protocol name is third from end
        except Exception:
            pass
        return None

    def extract_version_from_type(self, message_type: str) -> Optional[str]:
        """
        Extract version from message type URI

        Example: "https://didcomm.org/trust-ping/1.0/ping" -> "1.0"

        Args:
            message_type: Full message type URI

        Returns:
            Version string or None
        """
        try:
            parts = message_type.split('/')
            if len(parts) >= 4:
                return parts[-2]  # version is second from end
        except Exception:
            pass
        return None

    def supports_message_type(self, message_type: str) -> bool:
        """
        Check if this handler supports the given message type

        Args:
            message_type: Message type URI

        Returns:
            True if supported
        """
        protocol = self.extract_protocol_from_type(message_type)
        version = self.extract_version_from_type(message_type)

        return (
            protocol == self.protocol_name and
            version in self.supported_versions
        )
