"""
Router арбитра: API для управления адресами арбитра (RequireAdmin).
Ориентир: garantex routers/marketplace.py (arbiter endpoints).
"""
import logging
from fastapi import APIRouter, HTTPException, status

from web.endpoints.dependencies import ArbiterServiceDep, RequireAdminDepends
from web.endpoints.v1.schemas.arbiter import (
    ArbiterAddressListResponse,
    ArbiterAddressResponse,
    CreateArbiterRequest,
    UpdateArbiterNameRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/arbiter", tags=["arbiter"])


def _to_response(item) -> ArbiterAddressResponse:
    """ArbiterResource.Get → ArbiterAddressResponse."""
    return ArbiterAddressResponse(
        id=item.id,
        name=item.name,
        tron_address=item.tron_address,
        ethereum_address=item.ethereum_address,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/is-initialized")
async def arbiter_is_initialized(
    arbiter_service: ArbiterServiceDep,
    _admin: RequireAdminDepends,
):
    """Проверка: инициализирован ли арбитр (есть ли активный адрес)."""
    initialized = await arbiter_service.is_arbiter_initialized()
    return {"initialized": initialized}


@router.get("/addresses", response_model=ArbiterAddressListResponse)
async def list_arbiter_addresses(
    arbiter_service: ArbiterServiceDep,
    _admin: RequireAdminDepends,
):
    """Список адресов арбитра (активные и резервные)."""
    try:
        items = await arbiter_service.list_arbiter_addresses()
        return ArbiterAddressListResponse(
            addresses=[_to_response(a) for a in items],
            total=len(items),
        )
    except Exception as e:
        logger.exception("Error listing arbiter addresses")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/addresses",
    response_model=ArbiterAddressResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_arbiter_address(
    request: CreateArbiterRequest,
    arbiter_service: ArbiterServiceDep,
    _admin: RequireAdminDepends,
):
    """Создать адрес арбитра из имени и мнемоники."""
    try:
        item = await arbiter_service.create_arbiter_address(
            name=request.name,
            mnemonic=request.mnemonic,
        )
        return _to_response(item)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error creating arbiter address")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/addresses/{wallet_id}", response_model=ArbiterAddressResponse)
async def get_arbiter_address(
    wallet_id: int,
    arbiter_service: ArbiterServiceDep,
    _admin: RequireAdminDepends,
):
    """Адрес арбитра по id."""
    item = await arbiter_service.get_arbiter_address(wallet_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arbiter address not found",
        )
    return _to_response(item)


@router.put(
    "/addresses/{wallet_id}/name",
    response_model=ArbiterAddressResponse,
)
async def update_arbiter_address_name(
    wallet_id: int,
    request: UpdateArbiterNameRequest,
    arbiter_service: ArbiterServiceDep,
    _admin: RequireAdminDepends,
):
    """Обновить имя адреса арбитра."""
    try:
        item = await arbiter_service.update_arbiter_name(
            wallet_id=wallet_id,
            name=request.name,
        )
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arbiter address not found",
            )
        return _to_response(item)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/addresses/{wallet_id}/activate",
    response_model=ArbiterAddressResponse,
)
async def activate_arbiter_address(
    wallet_id: int,
    arbiter_service: ArbiterServiceDep,
    _admin: RequireAdminDepends,
):
    """Сделать резервный адрес активным; текущий активный становится резервным."""
    try:
        item = await arbiter_service.switch_active_arbiter(wallet_id)
        return _to_response(item)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/addresses/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_arbiter_address(
    wallet_id: int,
    arbiter_service: ArbiterServiceDep,
    _admin: RequireAdminDepends,
):
    """Удалить адрес арбитра (только резервный)."""
    try:
        deleted = await arbiter_service.delete_arbiter_address(wallet_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arbiter address not found",
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
