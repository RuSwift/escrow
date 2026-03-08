"""
Pydantic schemas for Aries protocol messages
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class TimingDecorator(BaseModel):
    """
    ~timing decorator for DIDComm messages
    Ref: https://github.com/hyperledger/aries-rfcs/tree/main/features/0032-message-timing
    """
    in_time: Optional[str] = Field(None, description="Time message was received (ISO 8601)")
    out_time: Optional[str] = Field(None, description="Time message was sent (ISO 8601)")
    stale_time: Optional[str] = Field(None, description="Time after which message is considered stale (ISO 8601)")
    expires_time: Optional[str] = Field(None, description="Time after which message should be discarded (ISO 8601)")
    delay_milli: Optional[int] = Field(None, description="Delay in milliseconds before processing")
    wait_until_time: Optional[str] = Field(None, description="Wait until this time before processing (ISO 8601)")


class TrustPingBody(BaseModel):
    """
    Body of a Trust Ping message
    """
    response_requested: bool = Field(
        default=True,
        description="Whether a response is requested"
    )
    comment: Optional[str] = Field(
        None,
        description="Optional comment (not machine-readable)"
    )


class TrustPingMessage(BaseModel):
    """
    Trust Ping message schema (RFC 0048)

    Message type: https://didcomm.org/trust-ping/1.0/ping
    """
    id: str = Field(..., description="Unique message identifier")
    type: str = Field(
        default="https://didcomm.org/trust-ping/1.0/ping",
        description="Message type URI"
    )
    body: TrustPingBody = Field(..., description="Message body")
    from_did: Optional[str] = Field(None, alias="from", description="Sender's DID")
    to: Optional[List[str]] = Field(None, description="Recipient DIDs")
    created_time: Optional[str] = Field(None, description="Message creation time (ISO 8601)")
    expires_time: Optional[str] = Field(None, description="Message expiration time (ISO 8601)")
    timing: Optional[TimingDecorator] = Field(None, alias="~timing", description="Timing decorator")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "trust-ping-message-id",
                "type": "https://didcomm.org/trust-ping/1.0/ping",
                "body": {
                    "response_requested": True,
                    "comment": "Checking if you're there"
                },
                "from": "did:peer:1:zQmExample",
                "to": ["did:peer:1:zQmRecipient"]
            }
        }


class TrustPingResponseBody(BaseModel):
    """
    Body of a Trust Ping response (usually empty)
    """
    comment: Optional[str] = Field(
        None,
        description="Optional comment (not machine-readable)"
    )


class TrustPingResponse(BaseModel):
    """
    Trust Ping response schema (RFC 0048)

    Message type: https://didcomm.org/trust-ping/1.0/ping-response
    """
    id: str = Field(..., description="Unique message identifier")
    type: str = Field(
        default="https://didcomm.org/trust-ping/1.0/ping-response",
        description="Message type URI"
    )
    thid: str = Field(..., description="Thread ID (references original ping message ID)")
    body: TrustPingResponseBody = Field(default_factory=TrustPingResponseBody, description="Message body")
    from_did: Optional[str] = Field(None, alias="from", description="Sender's DID")
    to: Optional[List[str]] = Field(None, description="Recipient DIDs")
    created_time: Optional[str] = Field(None, description="Message creation time (ISO 8601)")
    timing: Optional[TimingDecorator] = Field(None, alias="~timing", description="Timing decorator")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "trust-ping-response-id",
                "type": "https://didcomm.org/trust-ping/1.0/ping-response",
                "thid": "trust-ping-message-id",
                "body": {},
                "from": "did:peer:1:zQmRecipient",
                "to": ["did:peer:1:zQmExample"]
            }
        }


class BasicMessageBody(BaseModel):
    """
    Body of a basic message (RFC 0095)
    """
    content: str = Field(..., description="Message content")
    sent_time: Optional[str] = Field(None, description="Time message was sent (ISO 8601)")
    locale: Optional[str] = Field(None, description="Locale of the message (e.g., 'en-US')")


class BasicMessage(BaseModel):
    """
    Basic Message schema (RFC 0095)

    Message type: https://didcomm.org/basicmessage/1.0/message
    """
    id: str = Field(..., description="Unique message identifier")
    type: str = Field(
        default="https://didcomm.org/basicmessage/1.0/message",
        description="Message type URI"
    )
    body: BasicMessageBody = Field(..., description="Message body")
    from_did: Optional[str] = Field(None, alias="from", description="Sender's DID")
    to: Optional[List[str]] = Field(None, description="Recipient DIDs")
    created_time: Optional[str] = Field(None, description="Message creation time (ISO 8601)")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "basic-message-id",
                "type": "https://didcomm.org/basicmessage/1.0/message",
                "body": {
                    "content": "Hello, world!",
                    "sent_time": "2024-01-01T00:00:00Z",
                    "locale": "en-US"
                },
                "from": "did:peer:1:zQmExample",
                "to": ["did:peer:1:zQmRecipient"]
            }
        }


# Connection Protocol schemas (RFC 0160)


class ConnectionInvitationBody(BaseModel):
    """
    Body of a Connection Invitation message
    """
    label: str = Field(..., description="Human-readable label for the inviter")
    recipient_keys: List[str] = Field(..., description="Public keys for encryption")
    service_endpoint: Optional[str] = Field(None, description="Service endpoint URL")
    routing_keys: Optional[List[str]] = Field(None, description="Keys for routing")
    image_url: Optional[str] = Field(None, description="Optional image URL")


class ConnectionInvitation(BaseModel):
    """
    Connection Invitation schema (RFC 0160)

    Message type: https://didcomm.org/connections/1.0/invitation
    """
    id: str = Field(..., description="Unique message identifier")
    type: str = Field(
        default="https://didcomm.org/connections/1.0/invitation",
        description="Message type URI"
    )
    body: ConnectionInvitationBody = Field(..., description="Message body")
    label: Optional[str] = Field(None, description="Deprecated: use body.label instead")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "invitation-id",
                "type": "https://didcomm.org/connections/1.0/invitation",
                "body": {
                    "label": "Alice Agent",
                    "recipient_keys": ["did:key:z6MkExample"],
                    "service_endpoint": "https://example.com/didcomm",
                    "routing_keys": []
                }
            }
        }


class ConnectionRequestBody(BaseModel):
    """
    Body of a Connection Request message
    """
    label: str = Field(..., description="Human-readable label for the requester")
    connection: Dict[str, Any] = Field(..., description="Connection details with DID and DID document")
    image_url: Optional[str] = Field(None, description="Optional image URL")


class ConnectionRequest(BaseModel):
    """
    Connection Request schema (RFC 0160)

    Message type: https://didcomm.org/connections/1.0/request
    """
    id: str = Field(..., description="Unique message identifier")
    type: str = Field(
        default="https://didcomm.org/connections/1.0/request",
        description="Message type URI"
    )
    body: ConnectionRequestBody = Field(..., description="Message body")
    from_did: Optional[str] = Field(None, alias="from", description="Sender's DID")
    to: Optional[List[str]] = Field(None, description="Recipient DIDs")
    created_time: Optional[str] = Field(None, description="Message creation time (ISO 8601)")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "request-id",
                "type": "https://didcomm.org/connections/1.0/request",
                "body": {
                    "label": "Bob Agent",
                    "connection": {
                        "DID": "did:peer:1:zQmBobExample",
                        "DIDDoc": {}
                    }
                },
                "from": "did:peer:1:zQmBobExample"
            }
        }


class ConnectionResponseBody(BaseModel):
    """
    Body of a Connection Response message
    """
    connection: Dict[str, Any] = Field(..., description="Connection details with DID and signed DID document")


class ConnectionResponse(BaseModel):
    """
    Connection Response schema (RFC 0160)

    Message type: https://didcomm.org/connections/1.0/response
    """
    id: str = Field(..., description="Unique message identifier")
    type: str = Field(
        default="https://didcomm.org/connections/1.0/response",
        description="Message type URI"
    )
    thid: str = Field(..., description="Thread ID (references original request message ID)")
    body: ConnectionResponseBody = Field(..., description="Message body")
    from_did: Optional[str] = Field(None, alias="from", description="Sender's DID")
    to: Optional[List[str]] = Field(None, description="Recipient DIDs")
    created_time: Optional[str] = Field(None, description="Message creation time (ISO 8601)")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "response-id",
                "type": "https://didcomm.org/connections/1.0/response",
                "thid": "request-id",
                "body": {
                    "connection": {
                        "DID": "did:peer:1:zQmAliceExample",
                        "DIDDoc": {}
                    }
                },
                "from": "did:peer:1:zQmAliceExample"
            }
        }
