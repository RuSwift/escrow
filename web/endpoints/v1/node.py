"""
Router для Node API: инициализация ноды (mnemonic/PEM), key-info, service endpoint.
Ориентир: garantex node.py — эндпоинты /api/node/*.
"""
import time
from typing import Union

import httpx
from fastapi import APIRouter, HTTPException, status

from didcomm.crypto import EthKeyPair, KeyPair as BaseKeyPair
from didcomm.did import create_peer_did_from_keypair
from didcomm.utils import create_service_endpoint
from web.endpoints.dependencies import (
    AdminDepends,
    AdminServiceDep,
    AppSettings,
    NodeServiceDep,
    RequireAdminDepends,
)
from web.endpoints.v1.schemas.admin import ChangeResponse
from web.endpoints.v1.schemas.node import (
    AdminConfiguredResponse,
    NodeInitPemRequest,
    NodeInitRequest,
    NodeInitResponse,
    SetServiceEndpointRequest,
    ServiceEndpointResponse,
    TestServiceEndpointRequest,
    TestServiceEndpointResponse,
)

router = APIRouter(prefix="/node", tags=["node"])


def _keypair_to_public_pem(priv_key: Union[EthKeyPair, BaseKeyPair]) -> str:
    """Публичный ключ в PEM (для key-info)."""
    if hasattr(priv_key, "to_public_pem"):
        return priv_key.to_public_pem().decode("utf-8")
    from cryptography.hazmat.primitives import serialization

    return priv_key._public_key_obj.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


@router.post("/init", response_model=NodeInitResponse)
async def init_node(
    data: NodeInitRequest,
    node_service: NodeServiceDep,
    settings: AppSettings,
    admin: AdminDepends,
):
    """
    Инициализация ноды из мнемонической фразы.
    Если нода уже инициализирована — требуется авторизация админа.
    """
    if not settings.secret.get_secret_value():
        raise HTTPException(
            status_code=500,
            detail="SECRET not configured in environment variables",
        )
    if settings.is_node_initialized and admin is None:
        raise HTTPException(
            status_code=401,
            detail="Node already initialized, please login as admin",
        )
    try:
        result = await node_service.init_from_mnemonic(data.mnemonic)
        if not await node_service.has_key():
            raise HTTPException(
                status_code=500,
                detail="Failed to create NodeSettings record in database",
            )
        return NodeInitResponse(
            success=True,
            message="Node initialized successfully",
            did=result.did,
            address=result.address,
            key_type=result.key_type,
            public_key=result.public_key,
            did_document=result.did_document,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing node: {str(e)}")


@router.post("/init-pem", response_model=NodeInitResponse)
async def init_node_from_pem(
    request: NodeInitPemRequest,
    node_service: NodeServiceDep,
    settings: AppSettings,
    _admin: RequireAdminDepends,
):
    """
    Инициализация ноды из PEM ключа. Требует авторизации админа.
    """
    if not settings.secret.get_secret_value():
        raise HTTPException(
            status_code=500,
            detail="SECRET not configured in environment variables",
        )
    try:
        result = await node_service.init_from_pem(
            request.pem_data,
            password=request.password,
        )
        if not await node_service.has_key():
            raise HTTPException(
                status_code=500,
                detail="Failed to create NodeSettings record in database",
            )
        return NodeInitResponse(
            success=True,
            message="Node initialized successfully",
            did=result.did,
            address=result.address,
            key_type=result.key_type,
            public_key=result.public_key,
            did_document=result.did_document,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing node: {str(e)}")


@router.get("/key-info")
async def get_key_info(
    node_service: NodeServiceDep,
    _admin: RequireAdminDepends,
):
    """
    Информация о ключе ноды: DID, DIDDoc, public key, service_endpoint.
    Требует авторизации админа.
    """
    has_key = await node_service.has_key()
    if not has_key:
        raise HTTPException(status_code=404, detail="Нода не инициализирована")
    keypair = await node_service.get_active_keypair()
    if keypair is None:
        raise HTTPException(status_code=404, detail="Ключ не найден")

    public_key_hex = keypair.public_key.hex()
    public_key_pem = _keypair_to_public_pem(keypair)
    key_type = getattr(keypair, "key_type", "Unknown")
    address = getattr(keypair, "address", None)

    service_endpoint = await node_service.get_service_endpoint()
    service_endpoints = None
    if service_endpoint:
        service_endpoints = [create_service_endpoint(service_endpoint)]

    did_obj = create_peer_did_from_keypair(keypair, service_endpoints=service_endpoints)
    return {
        "address": address,
        "key_type": key_type,
        "public_key": public_key_hex,
        "public_key_pem": public_key_pem,
        "did": did_obj.did,
        "did_document": did_obj.to_dict(),
        "service_endpoint": service_endpoint,
    }


@router.get("/is-admin-configured", response_model=AdminConfiguredResponse)
async def check_admin_configured(
    admin_service: AdminServiceDep,
):
    """
    Проверка: настроен ли админ (пароль или хотя бы один TRON-адрес).
    """
    is_configured = await admin_service.is_admin_configured()
    admin = await admin_service.get_admin()
    has_password = bool(admin and admin.username and admin.password_hash)
    addresses = await admin_service.get_tron_addresses(active_only=True)
    tron_count = len(addresses)
    return AdminConfiguredResponse(
        configured=is_configured,
        has_password=has_password,
        tron_addresses_count=tron_count,
    )


@router.post("/set-service-endpoint", response_model=ChangeResponse)
async def set_service_endpoint(
    request: SetServiceEndpointRequest,
    node_service: NodeServiceDep,
    settings: AppSettings,
    admin: AdminDepends,
):
    """
    Установка service endpoint ноды.
    Если нода уже инициализирована — требуется авторизация.
    """
    if settings.is_node_initialized and admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
        )
    try:
        success = await node_service.set_service_endpoint(request.service_endpoint)
        if not success:
            raise HTTPException(status_code=404, detail="Node not initialized")
        return ChangeResponse(
            success=True,
            message="Service endpoint configured successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error configuring service endpoint: {str(e)}",
        )


@router.get("/service-endpoint", response_model=ServiceEndpointResponse)
async def get_service_endpoint(
    node_service: NodeServiceDep,
    _admin: RequireAdminDepends,
):
    """
    Текущий service endpoint. Требует авторизации админа.
    """
    try:
        endpoint = await node_service.get_service_endpoint()
        configured = await node_service.is_service_endpoint_configured()
        return ServiceEndpointResponse(
            service_endpoint=endpoint,
            configured=configured,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting service endpoint: {str(e)}",
        )


@router.post("/test-service-endpoint", response_model=TestServiceEndpointResponse)
async def test_service_endpoint(request: TestServiceEndpointRequest):
    """
    Проверка доступности указанного URL (GET 200).
    """
    try:
        start = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(request.service_endpoint)
                response_time_ms = (time.time() - start) * 1000
                if response.status_code == 200:
                    return TestServiceEndpointResponse(
                        success=True,
                        status_code=response.status_code,
                        message=f"Endpoint is accessible (HTTP {response.status_code})",
                        response_time_ms=round(response_time_ms, 2),
                    )
                return TestServiceEndpointResponse(
                    success=False,
                    status_code=response.status_code,
                    message=f"Endpoint returned HTTP {response.status_code}, expected 200",
                    response_time_ms=round(response_time_ms, 2),
                )
            except httpx.ConnectError:
                return TestServiceEndpointResponse(
                    success=False,
                    status_code=None,
                    message="Connection failed: Cannot connect to endpoint",
                    response_time_ms=None,
                )
            except httpx.TimeoutException:
                return TestServiceEndpointResponse(
                    success=False,
                    status_code=None,
                    message="Request timeout: Endpoint took too long to respond",
                    response_time_ms=None,
                )
            except Exception as e:
                return TestServiceEndpointResponse(
                    success=False,
                    status_code=None,
                    message=f"Request failed: {str(e)}",
                    response_time_ms=None,
                )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error testing endpoint: {str(e)}",
        )


@router.get("/is-service-endpoint-configured")
async def check_service_endpoint_configured(
    node_service: NodeServiceDep,
):
    """
    Проверка: задан ли service endpoint.
    """
    configured = await node_service.is_service_endpoint_configured()
    return {"configured": configured}
