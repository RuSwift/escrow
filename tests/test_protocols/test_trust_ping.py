"""
Tests for Trust Ping protocol (RFC 0048)
"""
import uuid

import pytest
from didcomm.crypto import EthKeyPair, KeyPair
from didcomm.did import create_peer_did_from_keypair
from didcomm.message import DIDCommMessage, pack_message, unpack_message

from services.protocols.schemas import TrustPingMessage, TrustPingResponse
from services.protocols.trust_ping import TrustPingHandler


class TestTrustPingHandler:
    """Test suite for Trust Ping protocol handler."""

    @pytest.fixture
    def alice_key(self):
        """Alice's Ethereum key."""
        return EthKeyPair()

    @pytest.fixture
    def bob_key(self):
        """Bob's Ethereum key."""
        return EthKeyPair()

    @pytest.fixture
    def alice_did(self, alice_key):
        """Alice's DID."""
        did_obj = create_peer_did_from_keypair(alice_key)
        return did_obj.did

    @pytest.fixture
    def bob_did(self, bob_key):
        """Bob's DID."""
        did_obj = create_peer_did_from_keypair(bob_key)
        return did_obj.did

    @pytest.fixture
    def alice_handler(self, alice_key, alice_did):
        """Alice's Trust Ping handler."""
        return TrustPingHandler(alice_key, alice_did)

    @pytest.fixture
    def bob_handler(self, bob_key, bob_did):
        """Bob's Trust Ping handler."""
        return TrustPingHandler(bob_key, bob_did)

    def test_handler_initialization(self, alice_handler, alice_key, alice_did):
        """Test that handler initializes correctly."""
        assert alice_handler.my_key == alice_key
        assert alice_handler.my_did == alice_did
        assert alice_handler.protocol_name == "trust-ping"
        assert "1.0" in alice_handler.supported_versions

    def test_create_ping_message(self, alice_handler, bob_did):
        """Test creating a ping message."""
        ping = alice_handler.create_ping(
            recipient_did=bob_did,
            response_requested=True,
            comment="Testing ping",
        )

        assert isinstance(ping, DIDCommMessage)
        assert ping.type == TrustPingHandler.MSG_TYPE_PING
        assert ping.from_did == alice_handler.my_did
        assert bob_did in ping.to
        assert ping.body["response_requested"] is True
        assert ping.body.get("comment") == "Testing ping"

    def test_create_ping_without_response(self, alice_handler, bob_did):
        """Test creating a ping without response requested."""
        ping = alice_handler.create_ping(
            recipient_did=bob_did,
            response_requested=False,
        )

        assert ping.body["response_requested"] is False

    def test_create_ping_response(self, alice_handler, bob_did):
        """Test creating a ping response."""
        original_ping_id = str(uuid.uuid4())

        pong = alice_handler.create_ping_response(
            original_ping_id=original_ping_id,
            sender_did=bob_did,
            comment="Pong!",
        )

        assert isinstance(pong, DIDCommMessage)
        assert pong.type == TrustPingHandler.MSG_TYPE_PING_RESPONSE
        pong_dict = pong.to_dict()
        assert pong_dict.get("thid") == original_ping_id
        assert bob_did in pong.to

    @pytest.mark.asyncio
    async def test_handle_ping_with_response_requested(self, bob_handler, alice_did):
        """Test handling ping message when response is requested."""
        ping = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=TrustPingHandler.MSG_TYPE_PING,
            body={"response_requested": True},
            from_did=alice_did,
            to=[bob_handler.my_did],
        )

        response = await bob_handler.handle_message(ping)

        assert response is not None
        assert response.type == TrustPingHandler.MSG_TYPE_PING_RESPONSE
        response_dict = response.to_dict()
        assert response_dict.get("thid") == ping.id

    @pytest.mark.asyncio
    async def test_handle_ping_without_response_requested(self, bob_handler, alice_did):
        """Test handling ping message when response is not requested."""
        ping = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=TrustPingHandler.MSG_TYPE_PING,
            body={"response_requested": False},
            from_did=alice_did,
            to=[bob_handler.my_did],
        )

        response = await bob_handler.handle_message(ping)

        assert response is None

    @pytest.mark.asyncio
    async def test_handle_ping_response(self, bob_handler, alice_did):
        """Test handling ping response (should return None)."""
        pong = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=TrustPingHandler.MSG_TYPE_PING_RESPONSE,
            body={},
            from_did=alice_did,
            to=[bob_handler.my_did],
        )

        pong_dict = pong.to_dict()
        pong_dict["thid"] = str(uuid.uuid4())
        pong = DIDCommMessage.from_dict(pong_dict)

        response = await bob_handler.handle_message(pong)

        assert response is None

    def test_validate_ping_message(self, alice_handler, bob_did):
        """Test ping message validation."""
        ping = alice_handler.create_ping(bob_did)
        assert alice_handler.validate_ping_message(ping) is True

        invalid_ping = DIDCommMessage(
            id=str(uuid.uuid4()),
            type="https://didcomm.org/invalid/1.0/message",
            body={"response_requested": True},
            from_did=alice_handler.my_did,
            to=[bob_did],
        )
        assert alice_handler.validate_ping_message(invalid_ping) is False

    def test_validate_ping_response(self, alice_handler, bob_did):
        """Test ping response validation."""
        pong = alice_handler.create_ping_response(
            original_ping_id=str(uuid.uuid4()),
            sender_did=bob_did,
        )
        assert alice_handler.validate_ping_response(pong) is True

        invalid_pong = DIDCommMessage(
            id=str(uuid.uuid4()),
            type=TrustPingHandler.MSG_TYPE_PING_RESPONSE,
            body={},
            from_did=alice_handler.my_did,
            to=[bob_did],
        )
        assert alice_handler.validate_ping_response(invalid_pong) is False

    def test_supports_message_type(self, alice_handler):
        """Test message type support checking."""
        assert alice_handler.supports_message_type(
            "https://didcomm.org/trust-ping/1.0/ping"
        ) is True

        assert alice_handler.supports_message_type(
            "https://didcomm.org/trust-ping/1.0/ping-response"
        ) is True

        assert alice_handler.supports_message_type(
            "https://didcomm.org/other-protocol/1.0/message"
        ) is False

        assert alice_handler.supports_message_type(
            "https://didcomm.org/trust-ping/2.0/ping"
        ) is False

    def test_extract_protocol_from_type(self, alice_handler):
        """Test protocol name extraction from message type."""
        protocol = alice_handler.extract_protocol_from_type(
            "https://didcomm.org/trust-ping/1.0/ping"
        )
        assert protocol == "trust-ping"

        protocol = alice_handler.extract_protocol_from_type(
            "https://didcomm.org/issue-credential/2.0/offer"
        )
        assert protocol == "issue-credential"

    def test_extract_version_from_type(self, alice_handler):
        """Test version extraction from message type."""
        version = alice_handler.extract_version_from_type(
            "https://didcomm.org/trust-ping/1.0/ping"
        )
        assert version == "1.0"

        version = alice_handler.extract_version_from_type(
            "https://didcomm.org/issue-credential/2.0/offer"
        )
        assert version == "2.0"


class TestTrustPingEndToEnd:
    """End-to-end tests for Trust Ping protocol."""

    @pytest.fixture
    def alice_key(self):
        """Alice's key."""
        return EthKeyPair()

    @pytest.fixture
    def bob_key(self):
        """Bob's key."""
        return EthKeyPair()

    @pytest.fixture
    def alice_handler(self, alice_key):
        """Alice's handler."""
        did_obj = create_peer_did_from_keypair(alice_key)
        return TrustPingHandler(alice_key, did_obj.did)

    @pytest.fixture
    def bob_handler(self, bob_key):
        """Bob's handler."""
        did_obj = create_peer_did_from_keypair(bob_key)
        return TrustPingHandler(bob_key, did_obj.did)

    @pytest.mark.asyncio
    async def test_full_ping_pong_flow(self, alice_handler, bob_handler, alice_key, bob_key):
        """Test complete ping-pong exchange."""
        ping = alice_handler.create_ping(
            recipient_did=bob_handler.my_did,
            response_requested=True,
            comment="Hello Bob!",
        )

        packed_ping = pack_message(
            ping,
            alice_key,
            [bob_key.public_key],
            encrypt=True,
        )

        unpacked_ping = unpack_message(
            packed_ping,
            bob_key,
            sender_public_key=alice_key.public_key,
            sender_key_type="ETH",
        )

        pong = await bob_handler.handle_message(unpacked_ping)

        assert pong is not None
        assert pong.type == TrustPingHandler.MSG_TYPE_PING_RESPONSE

        packed_pong = pack_message(
            pong,
            bob_key,
            [alice_key.public_key],
            encrypt=True,
        )

        unpacked_pong = unpack_message(
            packed_pong,
            alice_key,
            sender_public_key=bob_key.public_key,
            sender_key_type="ETH",
        )

        pong_dict = unpacked_pong.to_dict()
        assert pong_dict.get("thid") == ping.id

    @pytest.mark.asyncio
    async def test_ping_without_encryption(self, alice_handler, bob_handler, alice_key, bob_key):
        """Test ping-pong without encryption."""
        ping = alice_handler.create_ping(
            recipient_did=bob_handler.my_did,
            response_requested=True,
        )

        packed_ping = pack_message(
            ping,
            alice_key,
            [bob_key.public_key],
            encrypt=False,
        )

        unpacked_ping = unpack_message(
            packed_ping,
            bob_key,
            sender_public_key=alice_key.public_key,
            sender_key_type="ETH",
        )

        pong = await bob_handler.handle_message(unpacked_ping)
        assert pong is not None


class TestTrustPingWithDifferentKeys:
    """Test Trust Ping with different key types."""

    @pytest.mark.asyncio
    async def test_ping_with_rsa_keys(self):
        """Test ping with RSA keys."""
        alice_key = KeyPair.generate_rsa(key_size=2048)
        bob_key = KeyPair.generate_rsa(key_size=2048)

        alice_did = create_peer_did_from_keypair(alice_key).did
        bob_did = create_peer_did_from_keypair(bob_key).did

        alice_handler = TrustPingHandler(alice_key, alice_did)
        bob_handler = TrustPingHandler(bob_key, bob_did)

        ping = alice_handler.create_ping(bob_did, response_requested=True)

        packed = pack_message(ping, alice_key, [bob_key.public_key], encrypt=True)
        unpacked = unpack_message(packed, bob_key, alice_key.public_key, "RSA")

        pong = await bob_handler.handle_message(unpacked)
        assert pong is not None

    @pytest.mark.asyncio
    async def test_ping_with_ec_keys(self):
        """Test ping with EC keys (non-Ethereum)."""
        from cryptography.hazmat.primitives.asymmetric import ec

        alice_key = KeyPair.generate_ec(curve=ec.SECP256R1())
        bob_key = KeyPair.generate_ec(curve=ec.SECP256R1())

        alice_did = create_peer_did_from_keypair(alice_key).did
        bob_did = create_peer_did_from_keypair(bob_key).did

        alice_handler = TrustPingHandler(alice_key, alice_did)
        bob_handler = TrustPingHandler(bob_key, bob_did)

        ping = alice_handler.create_ping(bob_did, response_requested=True)

        packed = pack_message(ping, alice_key, [bob_key.public_key], encrypt=True)
        unpacked = unpack_message(packed, bob_key, alice_key.public_key, "EC")

        pong = await bob_handler.handle_message(unpacked)
        assert pong is not None


class TestTrustPingSchemas:
    """Test Pydantic schemas for Trust Ping."""

    def test_trust_ping_message_schema(self):
        """Test TrustPingMessage schema validation."""
        ping_data = {
            "id": str(uuid.uuid4()),
            "type": "https://didcomm.org/trust-ping/1.0/ping",
            "body": {
                "response_requested": True,
                "comment": "Test ping",
            },
            "from": "did:peer:1:zQmExample",
            "to": ["did:peer:1:zQmRecipient"],
        }

        ping = TrustPingMessage(**ping_data)
        assert ping.id == ping_data["id"]
        assert ping.body.response_requested is True
        assert ping.body.comment == "Test ping"

    def test_trust_ping_response_schema(self):
        """Test TrustPingResponse schema validation."""
        pong_data = {
            "id": str(uuid.uuid4()),
            "type": "https://didcomm.org/trust-ping/1.0/ping-response",
            "thid": str(uuid.uuid4()),
            "body": {},
            "from": "did:peer:1:zQmRecipient",
            "to": ["did:peer:1:zQmExample"],
        }

        pong = TrustPingResponse(**pong_data)
        assert pong.id == pong_data["id"]
        assert pong.thid == pong_data["thid"]
