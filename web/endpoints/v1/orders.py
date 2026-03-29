"""Ордера дашборда в разрезе space (owner)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from core.exceptions import SpacePermissionDenied
from services.order import OrderService
from web.endpoints.dependencies import (
    get_order_service,
    get_required_wallet_address_for_space,
)
from web.endpoints.v1.schemas.orders import OrderItem, OrderListResponse

router = APIRouter(prefix="/spaces", tags=["orders"])


@router.get("/{space}/orders", response_model=OrderListResponse)
async def list_space_orders(
    space: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: OrderService = Depends(get_order_service),
):
    """Список эфемерных ордеров по ramp-кошелькам владельца спейса."""
    try:
        rows = await svc.list_for_space(space, wallet_address)
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return OrderListResponse(
        items=[OrderItem.model_validate(r.model_dump()) for r in rows],
    )
