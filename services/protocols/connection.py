"""
Connection protocol handler (Aries RFC 0160)

Reference: https://github.com/decentralized-identity/aries-rfcs/tree/main/features/0160-connection-protocol
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Union, Dict, Any, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from didcomm.crypto import EthKeyPair, KeyPair
from didcomm.message import DIDCommMessage

import db
from db.models import Connection
from services.protocols.base import ProtocolHandler
from services.protocols.schemas import (
    ConnectionInvitation,
    ConnectionInvitationBody,
    ConnectionRequest,
    ConnectionRequestBody,
    ConnectionResponse,
    ConnectionResponseBody,
)


class ConnectionHandler(ProtocolHandler):
    """
    Handler for Connection protocol (RFC 0160)

    The Connection protocol is used to establish a connection between two DIDComm agents.
    It involves three main steps:
    1. Invitation - One party creates and shares an invitation
    2. Request - The other party responds with a connection request
    3. Response - The inviter accepts the connection with a response

    After these steps, both parties have a mutual connection for future communication.
    """

    protocol_name = "connections"
    supported_versions = ["1.0"]

    # Message types
    MSG_TYPE_INVITATION = "https://didcomm.org/connections/1.0/invitation"
    MSG_TYPE_REQUEST = "https://didcomm.org/connections/1.0/request"
    MSG_TYPE_RESPONSE = "https://didcomm.org/connections/1.0/response"

    def __init__(self, my_key: Union[EthKeyPair, KeyPair], my_did: str, service_endpoint: Optional[str] = None):
        """
        Initialize Connection handler

        Args:
            my_key: Node's private key
            my_did: Node's DID
            service_endpoint: Service endpoint URL for receiving messages

        Raises:
            RuntimeError: If database SessionLocal is not initialized
        """
        super().__init__(my_key, my_did)
        self.service_endpoint = service_endpoint

        # Check that database is initialized
        if db.SessionLocal is None:
            raise RuntimeError(
                "Database not initialized. Call db.init_db() before creating ConnectionHandler. "
                "SessionLocal must be initialized to store connection data."
            )

    async def _get_db_session(self) -> AsyncSession:
        """Get database session"""
        return db.SessionLocal()

    async def _save_connection(
        self,
        connection_id: str,
        status: str,
        connection_type: str,
        their_did: Optional[str] = None,
        label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        message_data: Optional[Dict[str, Any]] = None
    ) -> Connection:
        """
        Save or update connection in database

        Args:
            connection_id: Unique connection identifier
            status: Connection status ('pending' or 'established')
            connection_type: Type of connection ('invitation', 'request', 'response')
            their_did: DID of the other party
            label: Human-readable label
            metadata: Additional metadata
            message_data: Original message data

        Returns:
            Connection model instance
        """
        async with (await self._get_db_session()) as session:
            # Check if connection exists
            result = await session.execute(
                select(Connection).where(
                    Connection.connection_id == connection_id,
                    Connection.my_did == self.my_did
                )
            )
            connection = result.scalar_one_or_none()

            if connection:
                # Update existing connection
                connection.status = status
                connection.their_did = their_did or connection.their_did
                connection.label = label or connection.label
                connection.connection_metadata = metadata or connection.connection_metadata
                connection.message_data = message_data or connection.message_data
                connection.updated_at = datetime.now(timezone.utc)

                if status == 'established' and connection.established_at is None:
                    connection.established_at = datetime.now(timezone.utc)
            else:
                # Create new connection
                connection = Connection(
                    connection_id=connection_id,
                    my_did=self.my_did,
                    their_did=their_did,
                    status=status,
                    connection_type=connection_type,
                    label=label,
                    connection_metadata=metadata,
                    message_data=message_data,
                    established_at=datetime.now(timezone.utc) if status == 'established' else None
                )
                session.add(connection)

            await session.commit()
            await session.refresh(connection)
            return connection

    async def _get_connection_by_id(self, connection_id: str) -> Optional[Connection]:
        """Get connection by connection_id"""
        async with (await self._get_db_session()) as session:
            result = await session.execute(
                select(Connection).where(
                    Connection.connection_id == connection_id,
                    Connection.my_did == self.my_did
                )
            )
            return result.scalar_one_or_none()

    async def _get_connection_by_their_did(self, their_did: str) -> Optional[Connection]:
        """Get connection by their DID"""
        async with (await self._get_db_session()) as session:
            result = await session.execute(
                select(Connection).where(
                    Connection.their_did == their_did,
                    Connection.my_did == self.my_did,
                    Connection.status == 'established'
                ).order_by(Connection.established_at.desc())
            )
            return result.scalar_one_or_none()

    async def _get_pending_connections(self) -> List[Connection]:
        """Get all pending connections"""
        async with (await self._get_db_session()) as session:
            result = await session.execute(
                select(Connection).where(
                    Connection.my_did == self.my_did,
                    Connection.status == 'pending'
                ).order_by(Connection.created_at.desc())
            )
            return list(result.scalars().all())

    async def _get_established_connections(self) -> List[Connection]:
        """Get all established connections"""
        async with (await self._get_db_session()) as session:
            result = await session.execute(
                select(Connection).where(
                    Connection.my_did == self.my_did,
                    Connection.status == 'established'
                ).order_by(Connection.established_at.desc())
            )
            return list(result.scalars().all())

    async def _delete_connection(self, connection_id: str):
        """Delete connection from database"""
        async with (await self._get_db_session()) as session:
            await session.execute(
                delete(Connection).where(
                    Connection.connection_id == connection_id,
                    Connection.my_did == self.my_did
                )
            )
            await session.commit()

    async def handle_message(
        self,
        message: DIDCommMessage,
        sender_public_key: Optional[bytes] = None,
        sender_key_type: Optional[str] = None
    ) -> Optional[DIDCommMessage]:
        """
        Handle incoming Connection protocol message

        Args:
            message: Unpacked DIDComm message
            sender_public_key: Sender's public key
            sender_key_type: Sender's key type

        Returns:
            Response message if needed, None otherwise
        """
        # Route to appropriate handler based on message type
        if message.type == self.MSG_TYPE_INVITATION:
            return await self._handle_invitation(message)
        elif message.type == self.MSG_TYPE_REQUEST:
            return await self._handle_request(message)
        elif message.type == self.MSG_TYPE_RESPONSE:
            return await self._handle_response(message)
        else:
            raise ValueError(f"Unsupported message type: {message.type}")

    async def _handle_invitation(self, message: DIDCommMessage) -> Optional[DIDCommMessage]:
        """
        Handle incoming connection invitation

        Typically, an invitation is not directly "handled" - it's shared out-of-band.
        But we store it for reference and can automatically respond with a request.

        Args:
            message: Invitation message

        Returns:
            None (invitations don't get automatic responses by default)
        """
        # Store invitation in database for reference
        await self._save_connection(
            connection_id=message.id,
            status='pending',
            connection_type='invitation',
            label=message.body.get("label"),
            metadata={
                "recipient_keys": message.body.get("recipient_keys", []),
                "service_endpoint": message.body.get("service_endpoint"),
                "routing_keys": message.body.get("routing_keys", [])
            },
            message_data=message.to_dict()
        )

        # In a real implementation, you might want to automatically send a request
        # or notify the user about the invitation
        return None

    async def _handle_request(self, message: DIDCommMessage) -> Optional[DIDCommMessage]:
        """
        Handle incoming connection request

        Args:
            message: Connection request message

        Returns:
            Connection response accepting the request
        """
        # Extract connection details from the request
        connection_data = message.body.get("connection", {})
        requester_did = connection_data.get("DID")
        requester_label = message.body.get("label", "Unknown")

        if not requester_did:
            raise ValueError("Connection request missing DID in connection field")

        # Store request in database (first as pending, then will be updated to established)
        await self._save_connection(
            connection_id=message.id,
            status='pending',
            connection_type='request',
            their_did=requester_did,
            label=requester_label,
            metadata={
                "did_doc": connection_data.get("DIDDoc"),
                "image_url": message.body.get("image_url")
            },
            message_data=message.to_dict()
        )

        # Create and return connection response
        response = self.create_response(
            request_id=message.id,
            requester_did=requester_did
        )

        # Move to established connections
        await self._save_connection(
            connection_id=message.id,
            status='established',
            connection_type='request',
            their_did=requester_did,
            label=requester_label,
            metadata={
                "did_doc": connection_data.get("DIDDoc"),
                "image_url": message.body.get("image_url"),
                "request_id": message.id
            },
            message_data=message.to_dict()
        )

        return response

    async def _handle_response(self, message: DIDCommMessage) -> Optional[DIDCommMessage]:
        """
        Handle incoming connection response

        This completes the connection establishment from the requester's side.

        Args:
            message: Connection response message

        Returns:
            None (no further response needed)
        """
        # Extract connection details
        connection_data = message.body.get("connection", {})
        responder_did = connection_data.get("DID")

        if not responder_did:
            raise ValueError("Connection response missing DID in connection field")

        # Find the original request using thread ID
        request_id = message.thid
        pending_connection = await self._get_connection_by_id(request_id)

        if pending_connection:
            # Get the invitation label from metadata
            invitation_label = "Unknown"
            if pending_connection.connection_metadata and "invitation_label" in pending_connection.connection_metadata:
                invitation_label = pending_connection.connection_metadata["invitation_label"]

            # Update to established connection
            await self._save_connection(
                connection_id=request_id,
                status='established',
                connection_type=pending_connection.connection_type,
                their_did=responder_did,
                label=invitation_label,
                metadata={
                    **(pending_connection.connection_metadata or {}),
                    "response_did_doc": connection_data.get("DIDDoc"),
                    "response_id": message.id
                },
                message_data=message.to_dict()
            )

        # Connection is now established, no response needed
        return None

    async def create_invitation(
        self,
        label: str,
        recipient_keys: Optional[List[str]] = None,
        routing_keys: Optional[List[str]] = None,
        image_url: Optional[str] = None
    ) -> DIDCommMessage:
        """
        Create a new connection invitation

        Args:
            label: Human-readable label for this agent
            recipient_keys: Public keys for encryption (defaults to own key)
            routing_keys: Keys for routing messages
            image_url: Optional image URL for display

        Returns:
            DIDComm invitation message
        """
        # Use own DID key if not specified
        if recipient_keys is None:
            recipient_keys = [self.my_did]

        # Create message body
        body = {
            "label": label,
            "recipient_keys": recipient_keys,
            "routing_keys": routing_keys or []
        }

        if self.service_endpoint:
            body["service_endpoint"] = self.service_endpoint

        if image_url:
            body["image_url"] = image_url

        # Create DIDComm message
        message = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=self.MSG_TYPE_INVITATION,
            body=body,
            created_time=datetime.now(timezone.utc).isoformat()
        )

        # Store invitation in database
        await self._save_connection(
            connection_id=message.id,
            status='pending',
            connection_type='invitation',
            label=label,
            metadata={
                "recipient_keys": recipient_keys,
                "routing_keys": routing_keys or [],
                "service_endpoint": self.service_endpoint,
                "image_url": image_url
            },
            message_data=message.to_dict()
        )

        return message

    async def create_request(
        self,
        invitation: DIDCommMessage,
        label: str,
        did_doc: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None
    ) -> DIDCommMessage:
        """
        Create a connection request in response to an invitation

        Args:
            invitation: The invitation message to respond to
            label: Human-readable label for this agent
            did_doc: DID document (optional, can be generated)
            image_url: Optional image URL for display

        Returns:
            DIDComm request message
        """
        # Create basic DID document if not provided
        if did_doc is None:
            did_doc = {
                "@context": "https://w3id.org/did/v1",
                "id": self.my_did,
                "publicKey": [{
                    "id": f"{self.my_did}#keys-1",
                    "type": "Ed25519VerificationKey2018",
                    "controller": self.my_did,
                    "publicKeyBase58": self.my_did  # Simplified
                }],
                "service": []
            }

        if self.service_endpoint:
            did_doc["service"].append({
                "id": f"{self.my_did}#didcomm",
                "type": "did-communication",
                "serviceEndpoint": self.service_endpoint
            })

        # Create message body
        body = {
            "label": label,
            "connection": {
                "DID": self.my_did,
                "DIDDoc": did_doc
            }
        }

        if image_url:
            body["image_url"] = image_url

        # Get recipient DID from invitation
        recipient_keys = invitation.body.get("recipient_keys", [])

        # Create DIDComm message
        message = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=self.MSG_TYPE_REQUEST,
            body=body,
            from_did=self.my_did,
            to=recipient_keys,
            created_time=datetime.now(timezone.utc).isoformat()
        )

        # Store request in database with invitation label for later use
        invitation_label = invitation.body.get("label", "Unknown")
        await self._save_connection(
            connection_id=message.id,
            status='pending',
            connection_type='request',
            label=label,
            metadata={
                "invitation_id": invitation.id,
                "invitation_label": invitation_label,
                "did_doc": did_doc,
                "image_url": image_url,
                "recipient_keys": recipient_keys
            },
            message_data=message.to_dict()
        )

        return message

    def create_response(
        self,
        request_id: str,
        requester_did: str,
        did_doc: Optional[Dict[str, Any]] = None
    ) -> DIDCommMessage:
        """
        Create a connection response accepting a request

        Args:
            request_id: ID of the request message (for threading)
            requester_did: DID of the requester
            did_doc: DID document (optional, can be generated)

        Returns:
            DIDComm response message
        """
        # Create basic DID document if not provided
        if did_doc is None:
            did_doc = {
                "@context": "https://w3id.org/did/v1",
                "id": self.my_did,
                "publicKey": [{
                    "id": f"{self.my_did}#keys-1",
                    "type": "Ed25519VerificationKey2018",
                    "controller": self.my_did,
                    "publicKeyBase58": self.my_did  # Simplified
                }],
                "service": []
            }

        if self.service_endpoint:
            did_doc["service"].append({
                "id": f"{self.my_did}#didcomm",
                "type": "did-communication",
                "serviceEndpoint": self.service_endpoint
            })

        # Create message body with signed connection
        body = {
            "connection": {
                "DID": self.my_did,
                "DIDDoc": did_doc
            }
        }

        # Create response with thread ID referencing original request
        message = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=self.MSG_TYPE_RESPONSE,
            body=body,
            from_did=self.my_did,
            to=[requester_did],
            created_time=datetime.now(timezone.utc).isoformat(),
            thid=request_id  # Thread ID references the original request
        )

        return message

    def validate_invitation(self, message: DIDCommMessage) -> bool:
        """
        Validate that a message is a valid connection invitation

        Args:
            message: DIDComm message to validate

        Returns:
            True if valid
        """
        if not self.validate_message_type(message, self.MSG_TYPE_INVITATION):
            return False

        body = message.body
        if not isinstance(body, dict):
            return False

        # Required fields
        if "label" not in body or "recipient_keys" not in body:
            return False

        if not isinstance(body["recipient_keys"], list) or len(body["recipient_keys"]) == 0:
            return False

        return True

    def validate_request(self, message: DIDCommMessage) -> bool:
        """
        Validate that a message is a valid connection request

        Args:
            message: DIDComm message to validate

        Returns:
            True if valid
        """
        if not self.validate_message_type(message, self.MSG_TYPE_REQUEST):
            return False

        body = message.body
        if not isinstance(body, dict):
            return False

        # Required fields
        if "label" not in body or "connection" not in body:
            return False

        connection = body["connection"]
        if not isinstance(connection, dict) or "DID" not in connection:
            return False

        return True

    def validate_response(self, message: DIDCommMessage) -> bool:
        """
        Validate that a message is a valid connection response

        Args:
            message: DIDComm message to validate

        Returns:
            True if valid
        """
        if not self.validate_message_type(message, self.MSG_TYPE_RESPONSE):
            return False

        # Response should have a thread ID
        if not hasattr(message, 'thid') or not message.thid:
            return False

        body = message.body
        if not isinstance(body, dict) or "connection" not in body:
            return False

        connection = body["connection"]
        if not isinstance(connection, dict) or "DID" not in connection:
            return False

        return True

    async def get_connection(self, did: str) -> Optional[Dict[str, Any]]:
        """
        Get established connection by DID

        Args:
            did: DID of the connected party

        Returns:
            Connection details or None if not found
        """
        connection = await self._get_connection_by_their_did(did)
        if not connection:
            return None

        return {
            "did": connection.their_did,
            "label": connection.label,
            "connection_id": connection.connection_id,
            "established": connection.established_at.isoformat() if connection.established_at else None,
            "metadata": connection.connection_metadata
        }

    async def list_connections(self) -> List[Dict[str, Any]]:
        """
        List all established connections

        Returns:
            List of connection details
        """
        connections = await self._get_established_connections()
        return [
            {
                "did": conn.their_did,
                "label": conn.label,
                "connection_id": conn.connection_id,
                "established": conn.established_at.isoformat() if conn.established_at else None,
                "metadata": conn.connection_metadata
            }
            for conn in connections
        ]

    async def list_pending_connections(self) -> List[Dict[str, Any]]:
        """
        List all pending connections (invitations and requests)

        Returns:
            List of pending connection details
        """
        connections = await self._get_pending_connections()
        return [
            {
                "connection_id": conn.connection_id,
                "type": conn.connection_type,
                "label": conn.label,
                "their_did": conn.their_did,
                "timestamp": conn.created_at.isoformat(),
                "metadata": conn.connection_metadata
            }
            for conn in connections
        ]
