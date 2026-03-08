"""
Tests for Connection protocol handler (RFC 0160)
"""
import uuid
from datetime import datetime, timezone
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from didcomm.crypto import EthKeyPair, KeyPair
from didcomm.did import create_peer_did_from_keypair
from didcomm.message import DIDCommMessage, pack_message, unpack_message

from services.protocols.connection import ConnectionHandler

# In-memory storage for tests (replaces database)
_test_connections = {}


class _MockConnection:
    """Mock Connection model for tests."""

    def __init__(
        self,
        connection_id,
        my_did,
        their_did,
        status,
        connection_type,
        label,
        connection_metadata,
        message_data,
        established_at=None,
    ):
        self.connection_id = connection_id
        self.my_did = my_did
        self.their_did = their_did
        self.status = status
        self.connection_type = connection_type
        self.label = label
        self.connection_metadata = connection_metadata
        self.message_data = message_data
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.established_at = established_at


@pytest.fixture(autouse=True)
def mock_db():
    """Mock database for all connection tests: patch handler to use in-memory storage."""
    global _test_connections
    _test_connections = {}

    original_save = ConnectionHandler._save_connection
    original_get_by_id = ConnectionHandler._get_connection_by_id
    original_get_by_did = ConnectionHandler._get_connection_by_their_did
    original_get_pending = ConnectionHandler._get_pending_connections
    original_get_established = ConnectionHandler._get_established_connections

    async def mock_save(
        self,
        connection_id,
        status,
        connection_type,
        their_did=None,
        label=None,
        metadata=None,
        message_data=None,
    ):
        key = f"{self.my_did}:{connection_id}"
        conn = _MockConnection(
            connection_id,
            self.my_did,
            their_did,
            connection_type=connection_type,
            status=status,
            label=label or "",
            connection_metadata=metadata or {},
            message_data=message_data or {},
            established_at=datetime.now(timezone.utc) if status == "established" else None,
        )
        _test_connections[key] = conn
        return conn

    async def mock_get_by_id(self, connection_id):
        key = f"{self.my_did}:{connection_id}"
        return _test_connections.get(key)

    async def mock_get_by_did(self, their_did):
        for conn in _test_connections.values():
            if (
                conn.my_did == self.my_did
                and conn.their_did == their_did
                and conn.status == "established"
            ):
                return conn
        return None

    async def mock_get_pending(self):
        return [
            conn
            for conn in _test_connections.values()
            if conn.my_did == self.my_did and conn.status == "pending"
        ]

    async def mock_get_established(self):
        return [
            conn
            for conn in _test_connections.values()
            if conn.my_did == self.my_did and conn.status == "established"
        ]

    ConnectionHandler._save_connection = mock_save
    ConnectionHandler._get_connection_by_id = mock_get_by_id
    ConnectionHandler._get_connection_by_their_did = mock_get_by_did
    ConnectionHandler._get_pending_connections = mock_get_pending
    ConnectionHandler._get_established_connections = mock_get_established

    yield

    ConnectionHandler._save_connection = original_save
    ConnectionHandler._get_connection_by_id = original_get_by_id
    ConnectionHandler._get_connection_by_their_did = original_get_by_did
    ConnectionHandler._get_pending_connections = original_get_pending
    ConnectionHandler._get_established_connections = original_get_established
    _test_connections = {}


class TestConnectionHandlerEth:
    """Test Connection protocol with Ethereum keys."""

    @pytest.fixture
    def alice_key(self):
        """Alice's Ethereum key pair."""
        return EthKeyPair()

    @pytest.fixture
    def bob_key(self):
        """Bob's Ethereum key pair."""
        return EthKeyPair()

    @pytest.fixture
    def alice_handler(self, alice_key):
        """Alice's connection handler."""
        alice_did = create_peer_did_from_keypair(alice_key).did
        return ConnectionHandler(
            alice_key,
            alice_did,
            service_endpoint="https://alice.example.com/didcomm",
        )

    @pytest.fixture
    def bob_handler(self, bob_key):
        """Bob's connection handler."""
        bob_did = create_peer_did_from_keypair(bob_key).did
        return ConnectionHandler(
            bob_key,
            bob_did,
            service_endpoint="https://bob.example.com/didcomm",
        )

    @pytest.mark.asyncio
    async def test_create_invitation(self, alice_handler):
        """Test creating a connection invitation."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
            routing_keys=[],
            image_url="https://alice.example.com/avatar.png",
        )

        assert invitation.type == ConnectionHandler.MSG_TYPE_INVITATION
        assert invitation.body["label"] == "Alice Agent"
        assert alice_handler.my_did in invitation.body["recipient_keys"]
        assert invitation.body["service_endpoint"] == "https://alice.example.com/didcomm"
        assert invitation.body["image_url"] == "https://alice.example.com/avatar.png"

        pending = await alice_handler.list_pending_connections()
        assert any(p["connection_id"] == invitation.id for p in pending)

    @pytest.mark.asyncio
    async def test_validate_invitation(self, alice_handler):
        """Test invitation validation."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )

        assert alice_handler.validate_invitation(invitation) is True

        invalid_invitation = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=ConnectionHandler.MSG_TYPE_INVITATION,
            body={"recipient_keys": [alice_handler.my_did]},
        )
        assert alice_handler.validate_invitation(invalid_invitation) is False

        invalid_invitation2 = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=ConnectionHandler.MSG_TYPE_INVITATION,
            body={"label": "Test"},
        )
        assert alice_handler.validate_invitation(invalid_invitation2) is False

    @pytest.mark.asyncio
    async def test_create_request(self, alice_handler, bob_handler):
        """Test creating a connection request in response to invitation."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )

        request = await bob_handler.create_request(
            invitation=invitation,
            label="Bob Agent",
            image_url="https://bob.example.com/avatar.png",
        )

        assert request.type == ConnectionHandler.MSG_TYPE_REQUEST
        assert request.body["label"] == "Bob Agent"
        assert request.body["connection"]["DID"] == bob_handler.my_did
        assert "DIDDoc" in request.body["connection"]
        assert request.body["image_url"] == "https://bob.example.com/avatar.png"

        pending = await bob_handler.list_pending_connections()
        assert any(p["connection_id"] == request.id for p in pending)

    @pytest.mark.asyncio
    async def test_validate_request(self, alice_handler, bob_handler):
        """Test request validation."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )

        request = await bob_handler.create_request(
            invitation=invitation,
            label="Bob Agent",
        )

        assert bob_handler.validate_request(request) is True

        invalid_request = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=ConnectionHandler.MSG_TYPE_REQUEST,
            body={"connection": {"DID": bob_handler.my_did}},
        )
        assert bob_handler.validate_request(invalid_request) is False

        invalid_request2 = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=ConnectionHandler.MSG_TYPE_REQUEST,
            body={"label": "Test"},
        )
        assert bob_handler.validate_request(invalid_request2) is False

    @pytest.mark.asyncio
    async def test_handle_request_creates_response(self, alice_handler, bob_handler):
        """Test that handling a request creates an appropriate response."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )

        request = await bob_handler.create_request(
            invitation=invitation,
            label="Bob Agent",
        )

        response = await alice_handler.handle_message(request)

        assert response is not None
        assert response.type == ConnectionHandler.MSG_TYPE_RESPONSE
        assert response.thid == request.id
        assert response.body["connection"]["DID"] == alice_handler.my_did

        alice_connections = await alice_handler.list_connections()
        assert any(c["did"] == bob_handler.my_did for c in alice_connections)

    @pytest.mark.asyncio
    async def test_validate_response(self, alice_handler, bob_handler):
        """Test response validation."""
        response = alice_handler.create_response(
            request_id=str(uuid.uuid4()),
            requester_did=bob_handler.my_did,
        )

        assert alice_handler.validate_response(response) is True

        invalid_response = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=ConnectionHandler.MSG_TYPE_RESPONSE,
            body={"connection": {"DID": alice_handler.my_did}},
        )
        assert alice_handler.validate_response(invalid_response) is False

        invalid_response2 = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=ConnectionHandler.MSG_TYPE_RESPONSE,
            body={},
            thid=str(uuid.uuid4()),
        )
        assert alice_handler.validate_response(invalid_response2) is False

    @pytest.mark.asyncio
    async def test_handle_response_establishes_connection(self, alice_handler, bob_handler):
        """Test that handling a response establishes the connection."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )

        request = await bob_handler.create_request(
            invitation=invitation,
            label="Bob Agent",
        )

        response = await alice_handler.handle_message(request)

        result = await bob_handler.handle_message(response)

        assert result is None

        bob_connections = await bob_handler.list_connections()
        assert any(c["did"] == alice_handler.my_did for c in bob_connections)

    @pytest.mark.asyncio
    async def test_full_connection_flow(self, alice_handler, bob_handler):
        """Test complete connection establishment flow."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )

        assert alice_handler.validate_invitation(invitation)

        request = await bob_handler.create_request(
            invitation=invitation,
            label="Bob Agent",
        )

        assert bob_handler.validate_request(request)

        response = await alice_handler.handle_message(request)

        assert response is not None
        assert alice_handler.validate_response(response)

        alice_connections = await alice_handler.list_connections()
        assert any(c["did"] == bob_handler.my_did for c in alice_connections)

        result = await bob_handler.handle_message(response)

        assert result is None

        bob_connections = await bob_handler.list_connections()
        assert any(c["did"] == alice_handler.my_did for c in bob_connections)

        alice_conn = await alice_handler.get_connection(bob_handler.my_did)
        bob_conn = await bob_handler.get_connection(alice_handler.my_did)

        assert alice_conn is not None
        assert bob_conn is not None
        assert alice_conn["did"] == bob_handler.my_did
        assert bob_conn["did"] == alice_handler.my_did

    @pytest.mark.asyncio
    async def test_list_connections(self, alice_handler, bob_handler):
        """Test listing established connections."""
        assert len(await alice_handler.list_connections()) == 0
        assert len(await bob_handler.list_connections()) == 0

        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )
        request = await bob_handler.create_request(invitation=invitation, label="Bob Agent")
        response = await alice_handler.handle_message(request)
        await bob_handler.handle_message(response)

        assert len(await alice_handler.list_connections()) == 1
        assert len(await bob_handler.list_connections()) == 1

    @pytest.mark.asyncio
    async def test_list_pending_connections(self, alice_handler):
        """Test listing pending connections."""
        await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )

        pending = await alice_handler.list_pending_connections()
        assert len(pending) == 1
        assert pending[0]["type"] == "invitation"

    @pytest.mark.asyncio
    async def test_encrypted_connection_flow(self, alice_handler, bob_handler, alice_key, bob_key):
        """Test connection flow with encrypted messages."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent",
            recipient_keys=[alice_handler.my_did],
        )

        request = await bob_handler.create_request(
            invitation=invitation,
            label="Bob Agent",
        )

        packed_request = pack_message(
            request,
            bob_key,
            [alice_key.public_key],
            encrypt=True,
        )

        unpacked_request = unpack_message(
            packed_request,
            alice_key,
            sender_public_key=bob_key.public_key,
            sender_key_type="ETH",
        )

        response = await alice_handler.handle_message(unpacked_request)

        packed_response = pack_message(
            response,
            alice_key,
            [bob_key.public_key],
            encrypt=True,
        )

        unpacked_response = unpack_message(
            packed_response,
            bob_key,
            sender_public_key=alice_key.public_key,
            sender_key_type="ETH",
        )

        await bob_handler.handle_message(unpacked_response)

        alice_connections = await alice_handler.list_connections()
        bob_connections = await bob_handler.list_connections()
        assert any(c["did"] == bob_handler.my_did for c in alice_connections)
        assert any(c["did"] == alice_handler.my_did for c in bob_connections)

    @pytest.mark.asyncio
    async def test_unsupported_message_type(self, alice_handler):
        """Test handling of unsupported message types."""
        invalid_message = DIDCommMessage(
            id=str(uuid.uuid4()),
            type="https://didcomm.org/connections/1.0/unknown",
            body={},
        )

        with pytest.raises(ValueError, match="Unsupported message type"):
            await alice_handler.handle_message(invalid_message)

    @pytest.mark.asyncio
    async def test_protocol_name_and_version(self, alice_handler):
        """Test protocol name and version support."""
        assert alice_handler.protocol_name == "connections"
        assert "1.0" in alice_handler.supported_versions

        assert alice_handler.supports_message_type(
            "https://didcomm.org/connections/1.0/invitation"
        )
        assert alice_handler.supports_message_type(
            "https://didcomm.org/connections/1.0/request"
        )
        assert alice_handler.supports_message_type(
            "https://didcomm.org/connections/1.0/response"
        )
        assert not alice_handler.supports_message_type(
            "https://didcomm.org/trust-ping/1.0/ping"
        )


class TestConnectionHandlerRSA:
    """Test Connection protocol with RSA keys."""

    @pytest.fixture
    def alice_key(self):
        """Alice's RSA key pair."""
        return KeyPair.generate_rsa(key_size=2048)

    @pytest.fixture
    def bob_key(self):
        """Bob's RSA key pair."""
        return KeyPair.generate_rsa(key_size=2048)

    @pytest.fixture
    def alice_handler(self, alice_key):
        """Alice's connection handler."""
        alice_did = create_peer_did_from_keypair(alice_key).did
        return ConnectionHandler(
            alice_key,
            alice_did,
            service_endpoint="https://alice.example.com/didcomm",
        )

    @pytest.fixture
    def bob_handler(self, bob_key):
        """Bob's connection handler."""
        bob_did = create_peer_did_from_keypair(bob_key).did
        return ConnectionHandler(
            bob_key,
            bob_did,
            service_endpoint="https://bob.example.com/didcomm",
        )

    @pytest.mark.asyncio
    async def test_full_connection_flow_rsa(self, alice_handler, bob_handler):
        """Test complete connection flow with RSA keys."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent (RSA)",
            recipient_keys=[alice_handler.my_did],
        )

        request = await bob_handler.create_request(
            invitation=invitation,
            label="Bob Agent (RSA)",
        )

        response = await alice_handler.handle_message(request)
        await bob_handler.handle_message(response)

        alice_connections = await alice_handler.list_connections()
        bob_connections = await bob_handler.list_connections()
        assert any(c["did"] == bob_handler.my_did for c in alice_connections)
        assert any(c["did"] == alice_handler.my_did for c in bob_connections)


class TestConnectionHandlerEC:
    """Test Connection protocol with Elliptic Curve keys."""

    @pytest.fixture
    def alice_key(self):
        """Alice's EC key pair."""
        return KeyPair.generate_ec(curve=ec.SECP256K1())

    @pytest.fixture
    def bob_key(self):
        """Bob's EC key pair."""
        return KeyPair.generate_ec(curve=ec.SECP256K1())

    @pytest.fixture
    def alice_handler(self, alice_key):
        """Alice's connection handler."""
        alice_did = create_peer_did_from_keypair(alice_key).did
        return ConnectionHandler(
            alice_key,
            alice_did,
            service_endpoint="https://alice.example.com/didcomm",
        )

    @pytest.fixture
    def bob_handler(self, bob_key):
        """Bob's connection handler."""
        bob_did = create_peer_did_from_keypair(bob_key).did
        return ConnectionHandler(
            bob_key,
            bob_did,
            service_endpoint="https://bob.example.com/didcomm",
        )

    @pytest.mark.asyncio
    async def test_full_connection_flow_ec(self, alice_handler, bob_handler):
        """Test complete connection flow with EC keys."""
        invitation = await alice_handler.create_invitation(
            label="Alice Agent (EC)",
            recipient_keys=[alice_handler.my_did],
        )

        request = await bob_handler.create_request(
            invitation=invitation,
            label="Bob Agent (EC)",
        )

        response = await alice_handler.handle_message(request)
        await bob_handler.handle_message(response)

        alice_connections = await alice_handler.list_connections()
        bob_connections = await bob_handler.list_connections()
        assert any(c["did"] == bob_handler.my_did for c in alice_connections)
        assert any(c["did"] == alice_handler.my_did for c in bob_connections)


class TestConnectionHandlerEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def handler(self):
        """Basic handler for edge case testing."""
        key = EthKeyPair()
        did = create_peer_did_from_keypair(key).did
        return ConnectionHandler(
            key,
            did,
            service_endpoint="https://test.example.com/didcomm",
        )

    @pytest.mark.asyncio
    async def test_request_without_did(self, handler):
        """Test handling request without DID in connection."""
        invalid_request = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=ConnectionHandler.MSG_TYPE_REQUEST,
            body={"label": "Test", "connection": {}},
        )

        with pytest.raises(ValueError, match="missing DID"):
            await handler.handle_message(invalid_request)

    @pytest.mark.asyncio
    async def test_response_without_did(self, handler):
        """Test handling response without DID in connection."""
        invalid_response = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=ConnectionHandler.MSG_TYPE_RESPONSE,
            body={"connection": {}},
            thid=str(uuid.uuid4()),
        )

        with pytest.raises(ValueError, match="missing DID"):
            await handler.handle_message(invalid_response)

    @pytest.mark.asyncio
    async def test_get_nonexistent_connection(self, handler):
        """Test getting a connection that doesn't exist."""
        result = await handler.get_connection("did:example:nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_custom_did_doc(self, handler):
        """Test creating request with custom DID document."""
        invitation = await handler.create_invitation(
            label="Test Agent",
            recipient_keys=[handler.my_did],
        )

        custom_did_doc = {
            "@context": "https://w3id.org/did/v1",
            "id": handler.my_did,
            "service": [],
            "custom_field": "custom_value",
        }

        request = await handler.create_request(
            invitation=invitation,
            label="Custom Agent",
            did_doc=custom_did_doc,
        )

        assert request.body["connection"]["DIDDoc"]["custom_field"] == "custom_value"
