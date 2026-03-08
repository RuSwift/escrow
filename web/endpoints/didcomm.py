"""
DIDComm: публичный service endpoint (GET/POST /endpoint по аналогии с garantex),
приём и маршрутизация сообщений, send-ping.
Роутер монтируется в node.py с префиксом /didcomm.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from didcomm.did import create_peer_did_from_keypair
from didcomm.message import unpack_message
from didcomm.utils import create_service_endpoint
from services.protocols import get_protocol_handler
from services.protocols.connection import ConnectionHandler
from services.protocols.trust_ping import TrustPingHandler
from web.endpoints.dependencies import (
    AppSettings,
    NodeKeypairOptionalDep,
    NodeKeypairRequiredDep,
    NodeServiceDep,
)
from web.endpoints.v1.schemas.didcomm import (
    DIDCommMessageRequest,
    DIDCommMessageResponse,
    SendTrustPingRequest,
)

router = APIRouter(tags=["DIDComm"])


def extract_protocol_name(message_type: str) -> Optional[str]:
    """Извлекает имя протокола из типа сообщения DIDComm."""
    if not message_type:
        return None
    parts = message_type.split("/")
    if len(parts) >= 3:
        return parts[-3]
    return None


async def get_node_keypair_for_didcomm(
    node_service: NodeServiceDep,
    settings: AppSettings,
):
    """Зависимость: ключ ноды для DIDComm; 503, если нода не инициализирована или ключа нет."""
    if not settings.is_node_initialized:
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


# --- Public service endpoint (garantex-style) ---


@router.get("/endpoint")
async def get_node_did_document(
    keypair: NodeKeypairOptionalDep,
    node_service: NodeServiceDep,
):
    """
    Публичный эндпоинт: DID Document ноды.
    Без ключа — 200 и { status: "not_initialized", initialized: false }.
    """
    if keypair is None:
        has_key = await node_service.has_key()
        return {
            "status": "not_initialized",
            "message": "Node is not initialized. Please initialize the node first.",
            "initialized": False,
        }
    try:
        service_endpoint = await node_service.get_service_endpoint()
        service_endpoints = None
        if service_endpoint:
            service_endpoints = [create_service_endpoint(service_endpoint)]
        did_obj = create_peer_did_from_keypair(keypair, service_endpoints=service_endpoints)
        return did_obj.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating DID Document: {str(e)}",
        )


@router.post("/endpoint")
async def receive_didcomm_message(
    message: dict,
    keypair: NodeKeypairRequiredDep,
    node_service: NodeServiceDep,
):
    """
    Публичный эндпоинт: приём packed DIDComm сообщения (garantex-style).
    Распаковка, маршрутизация по протоколу, возврат ответа при необходимости.
    """
    sender_public_key = None
    sender_key_type = None
    didcomm_message = message
    if isinstance(message, dict):
        if "sender_public_key" in message:
            sender_public_key = bytes.fromhex(message["sender_public_key"])
            sender_key_type = message.get("sender_key_type")
            didcomm_message = message.get("message", message)

    try:
        unpacked_message = unpack_message(
            didcomm_message,
            keypair,
            sender_public_key=sender_public_key,
            sender_key_type=sender_key_type,
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

    protocol_name = extract_protocol_name(unpacked_message.type)
    if not protocol_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not determine protocol from message type: {unpacked_message.type}",
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
            unpacked_message,
            sender_public_key=sender_public_key,
            sender_key_type=sender_key_type,
        )

        if response_message and sender_public_key:
            packed_response = handler.pack_response(
                response_message,
                [sender_public_key],
                encrypt=True,
            )
            return {
                "success": True,
                "message": f"Message processed by {protocol_name} protocol",
                "response": packed_response,
            }
        return {
            "success": True,
            "message": f"Message processed by {protocol_name} protocol",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}",
        )


# --- Structured message and send-ping (require node initialized) ---


@router.post("/message", response_model=DIDCommMessageResponse)
async def handle_didcomm_message(
    request: DIDCommMessageRequest,
    node_service: NodeServiceDep,
    keypair=Depends(get_node_keypair_for_didcomm),
):
    """
    Принимает packed DIDComm сообщение (структурированный запрос), распаковывает,
    маршрутизирует по протоколу и возвращает ответ (если есть).
    """
    sender_public_key = None
    if request.sender_public_key:
        sender_public_key = bytes.fromhex(request.sender_public_key)

    try:
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
    keypair=Depends(get_node_keypair_for_didcomm),
):
    """
    Формирует Trust Ping сообщение для указанного DID.
    Возвращает unpacked сообщение; упаковать с ключом получателя нужно на стороне вызывающего.
    """
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
