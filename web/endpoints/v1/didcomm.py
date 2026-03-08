"""
DIDComm: приём и маршрутизация DIDComm-сообщений по протоколам (Trust Ping, Connection и др.).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from didcomm.did import create_peer_did_from_keypair
from didcomm.message import unpack_message
from services.protocols import get_protocol_handler
from services.protocols.connection import ConnectionHandler
from services.protocols.trust_ping import TrustPingHandler
from web.endpoints.dependencies import NodeServiceDep
from web.endpoints.v1.schemas.didcomm import (
    DIDCommMessageRequest,
    DIDCommMessageResponse,
    SendTrustPingRequest,
)

router = APIRouter(prefix="/didcomm", tags=["DIDComm"])


def extract_protocol_name(message_type: str) -> Optional[str]:
    """
    Извлекает имя протокола из типа сообщения DIDComm.
    Например: "https://didcomm.org/trust-ping/1.0/ping" -> "trust-ping".
    """
    if not message_type:
        return None
    parts = message_type.split("/")
    if len(parts) >= 3:
        return parts[-3]
    return None


async def get_node_keypair_for_didcomm(node_service: NodeServiceDep):
    """Зависимость: ключ ноды для DIDComm; 503, если нода не инициализирована или ключа нет."""
    if not await node_service.is_node_initialized():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node not initialized. Please initialize the node first.",
        )
    keypair = await node_service.get_active_keypair()
    if keypair is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node key not available",
        )
    return keypair


@router.post("/message", response_model=DIDCommMessageResponse)
async def handle_didcomm_message(
    request: DIDCommMessageRequest,
    node_service: NodeServiceDep,
    keypair=Depends(get_node_keypair_for_didcomm),
):
    """
    Принимает packed DIDComm сообщение, распаковывает, маршрутизирует по протоколу
    и возвращает ответ (если есть).
    """

    try:
        sender_public_key = None
        if request.sender_public_key:
            sender_public_key = bytes.fromhex(request.sender_public_key)

        message = unpack_message(
            request.message,
            keypair,
            sender_public_key=sender_public_key,
            sender_key_type=request.sender_key_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid message format: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}",
        )

    protocol_name = extract_protocol_name(message.type)
    if not protocol_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not determine protocol from message type: {message.type}",
        )

    handler_class = get_protocol_handler(protocol_name)
    if not handler_class:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Protocol '{protocol_name}' is not supported",
        )

    try:
        did_obj = create_peer_did_from_keypair(keypair)
        if handler_class is ConnectionHandler:
            service_endpoint = await node_service.get_service_endpoint()
            handler = handler_class(keypair, did_obj.did, service_endpoint=service_endpoint)
        else:
            handler = handler_class(keypair, did_obj.did)

        response_message = await handler.handle_message(
            message,
            sender_public_key=sender_public_key,
            sender_key_type=request.sender_key_type,
        )

        response_data = None
        if response_message and sender_public_key:
            response_data = handler.pack_response(
                response_message,
                [sender_public_key],
                encrypt=True,
            )

        return DIDCommMessageResponse(
            success=True,
            message=f"Message handled successfully by {protocol_name} protocol",
            response=response_data,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}",
        )


@router.post("/send-ping")
async def send_trust_ping(
    request: SendTrustPingRequest,
    node_service: NodeServiceDep,
):
    """
    Формирует Trust Ping сообщение для указанного DID (для проверки связности).
    Возвращает unpacked сообщение; упаковать с ключом получателя нужно на стороне вызывающего.
    """
    if not await node_service.is_node_initialized():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node not initialized",
        )
    keypair = await node_service.get_active_keypair()
    if keypair is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node key not available",
        )

    did_obj = create_peer_did_from_keypair(keypair)
    handler = TrustPingHandler(keypair, did_obj.did)
    ping_message = handler.create_ping(
        recipient_did=request.recipient_did,
        response_requested=request.response_requested,
        comment=request.comment,
    )

    return {
        "success": True,
        "message": ping_message.to_dict(),
        "note": "This is an unpacked message. You need to pack it with recipient's public key before sending.",
    }
