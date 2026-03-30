"""Ордера дашборда: список, заявка на вывод, публичная подпись (без JWT)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from core.exceptions import SpacePermissionDenied
from services.order import OrderService, WithdrawalDeleteForbidden
from web.endpoints.dependencies import (
    get_exchange_wallet_service,
    get_order_service,
    get_required_wallet_address_for_space,
)
from web.endpoints.v1.schemas.order_withdrawal import (
    OrderSignContextResponse,
    OrderSignSubmitRequest,
    WithdrawalCreateRequest,
    WithdrawalCreateResponse,
)
from web.endpoints.v1.schemas.orders import OrderItem, OrderListResponse

router = APIRouter(tags=["orders"])


@router.get("/spaces/{space}/orders", response_model=OrderListResponse)
async def list_space_orders(
    space: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: OrderService = Depends(get_order_service),
):
    """Список эфемерных и заявок на вывод по ramp-кошелькам спейса (владелец спейса)."""
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


@router.delete(
    "/spaces/{space}/orders/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_space_order(
    space: str,
    order_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: OrderService = Depends(get_order_service),
):
    """Удаление заявки на вывод (owner | operator)."""
    try:
        await svc.delete_withdrawal_order(space, wallet_address, order_id)
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except WithdrawalDeleteForbidden as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/spaces/{space}/orders/{order_id}/withdrawal-signatures",
    response_model=OrderItem,
)
async def clear_withdrawal_order_signatures(
    space: str,
    order_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: OrderService = Depends(get_order_service),
):
    """Сброс off-chain подписей заявки на вывод (multisig, owner | operator)."""
    try:
        order = await svc.clear_offchain_signatures(
            space, wallet_address, order_id
        )
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
    return OrderItem.model_validate(order.model_dump())


@router.post(
    "/spaces/{space}/orders/withdrawal",
    response_model=WithdrawalCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_withdrawal_order(
    request: Request,
    space: str,
    body: WithdrawalCreateRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: OrderService = Depends(get_order_service),
    exchange_svc=Depends(get_exchange_wallet_service),
):
    """Создание заявки на вывод (owner | operator)."""
    try:
        order, _token, sign_path = await svc.create_withdrawal(
            space,
            wallet_address,
            exchange_svc,
            wallet_id=body.wallet_id,
            token_type=body.token_type,
            symbol=body.symbol,
            contract_address=body.contract_address,
            amount_raw=body.amount_raw,
            destination_address=body.destination_address,
        )
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
    base = str(request.base_url).rstrip("/")
    sign_url = f"{base}{sign_path}"
    return WithdrawalCreateResponse(
        order=OrderItem.model_validate(order.model_dump()),
        sign_url=sign_url,
    )


@router.get("/order-sign/{token}", response_model=OrderSignContextResponse)
async def get_order_sign_context(
    token: str,
    svc: OrderService = Depends(get_order_service),
):
    """Публичный контекст заявки на подпись (без JWT)."""
    ctx = await svc.get_public_sign_context(token)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired link",
        )
    return OrderSignContextResponse(**ctx)


@router.post("/order-sign/{token}/submit", response_model=OrderItem)
async def submit_order_signature(
    token: str,
    body: OrderSignSubmitRequest,
    svc: OrderService = Depends(get_order_service),
):
    """Публичная отправка подписанной транзакции (без JWT)."""
    try:
        order = await svc.submit_signed_transaction(
            token,
            body.signed_transaction,
            body.signer_address,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return OrderItem.model_validate(order.model_dump())
