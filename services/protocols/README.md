# Aries Protocol Handlers

This module provides implementations of various Aries RFC protocols for DIDComm messaging. Each protocol is implemented as a handler class that inherits from the base `ProtocolHandler` class.

## Supported Protocols

### 1. Trust Ping Protocol (RFC 0048)

**Module:** `trust_ping.py`  
**Protocol Name:** `trust-ping`  
**Versions:** 1.0  
**Reference:** https://github.com/hyperledger/aries-rfcs/tree/main/features/0048-trust-ping

The Trust Ping protocol is used to test connectivity and responsiveness between DIDComm agents. It's a simple ping-pong protocol where one agent sends a ping and optionally requests a response.

**Message Types:**
- `https://didcomm.org/trust-ping/1.0/ping` - Ping message
- `https://didcomm.org/trust-ping/1.0/ping-response` - Pong response

**Example Usage:**
```python
from didcomm.crypto import EthKeyPair
from services.protocols import TrustPingHandler

# Initialize handler
my_key = EthKeyPair()
my_did = f"did:ethr:{my_key.address}"
handler = TrustPingHandler(my_key, my_did)

# Create a ping
ping = handler.create_ping(
    recipient_did="did:example:recipient",
    response_requested=True,
    comment="Are you there?"
)

# Handle incoming ping
response = await handler.handle_message(ping)
```

### 2. Connection Protocol (RFC 0160)

**Module:** `connection.py`  
**Protocol Name:** `connections`  
**Versions:** 1.0  
**Reference:** https://github.com/decentralized-identity/aries-rfcs/tree/main/features/0160-connection-protocol

The Connection protocol is used to establish a connection between two DIDComm agents. It involves three main steps:
1. **Invitation** - One party creates and shares an invitation
2. **Request** - The other party responds with a connection request
3. **Response** - The inviter accepts the connection with a response

After these steps, both parties have a mutual connection for future communication.

**Message Types:**
- `https://didcomm.org/connections/1.0/invitation` - Connection invitation
- `https://didcomm.org/connections/1.0/request` - Connection request
- `https://didcomm.org/connections/1.0/response` - Connection response

**Example Usage:**
```python
from didcomm.crypto import EthKeyPair
from services.protocols import ConnectionHandler

# Alice creates an invitation
alice_key = EthKeyPair()
alice_did = f"did:ethr:{alice_key.address}"
alice_handler = ConnectionHandler(
    alice_key,
    alice_did,
    service_endpoint="https://alice.example.com/didcomm"
)

invitation = await alice_handler.create_invitation(
    label="Alice Agent",
    recipient_keys=[alice_did]
)

# Bob receives invitation and creates request
bob_key = EthKeyPair()
bob_did = f"did:ethr:{bob_key.address}"
bob_handler = ConnectionHandler(
    bob_key,
    bob_did,
    service_endpoint="https://bob.example.com/didcomm"
)

request = await bob_handler.create_request(
    invitation=invitation,
    label="Bob Agent"
)

# Alice handles request and creates response
response = await alice_handler.handle_message(request)

# Bob handles response and completes connection
await bob_handler.handle_message(response)

# Now both parties have an established connection
alice_conn = await alice_handler.get_connection(bob_did)
bob_conn = await bob_handler.get_connection(alice_did)
```

**Connection Management:**
```python
# List all established connections
connections = await handler.list_connections()

# List pending connections (invitations and requests)
pending = await handler.list_pending_connections()

# Get specific connection by DID
connection = await handler.get_connection("did:example:recipient")
```

## Architecture

### Base Protocol Handler

All protocol handlers inherit from the `ProtocolHandler` base class which provides:
- **Message Type Validation:** Validates incoming message types against supported protocols
- **Message Packing/Unpacking:** Handles encryption and decryption of DIDComm messages
- **Protocol Routing:** Routes messages to appropriate handler methods
- **Utility Methods:** Common functionality for protocol version extraction, validation, etc.

### Protocol Registry

The `PROTOCOL_HANDLERS` dictionary in `__init__.py` maintains a registry of all available protocol handlers:

```python
PROTOCOL_HANDLERS = {
    "trust-ping": TrustPingHandler,
    "connections": ConnectionHandler,
}
```

Use the `get_protocol_handler()` function to retrieve a handler class by protocol name:

```python
from services.protocols import get_protocol_handler

handler_class = get_protocol_handler("connections")
if handler_class:
    handler = handler_class(my_key, my_did)
```

## References

- [Aries RFCs Repository](https://github.com/hyperledger/aries-rfcs)
- [DIDComm Messaging Specification](https://identity.foundation/didcomm-messaging/spec/)
- [DID Core Specification](https://www.w3.org/TR/did-core/)
