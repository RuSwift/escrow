"""Simple UI: JSON API без {space} в path — space из JWT/cookie."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from core.exceptions import SpacePermissionDenied
from services.payment_request import PaymentRequestService
from web.endpoints.dependencies import CurrentWalletUser, get_payment_request_service
from web.endpoints.v1.schemas.payment_requests import (
    PaymentRequestCreateBody,
    PaymentRequestCreateResponse,
    PaymentRequestDeactivateBody,
    PaymentRequestDeactivateResponse,
    PaymentRequestListResponse,
    PaymentRequestOut,
)

router = APIRouter(prefix="/simple", tags=["simple"])


@router.get("/payment-requests", response_model=PaymentRequestListResponse)
async def list_payment_requests(
    user: CurrentWalletUser,
    svc: PaymentRequestService = Depends(get_payment_request_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=512),
):
    """Список заявок PaymentRequest для текущего кошелька."""
    try:
        rows, total = await svc.list_payment_requests(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            page=page,
            page_size=page_size,
            q=q,
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
    return PaymentRequestListResponse(
        items=[
            PaymentRequestOut.from_model(r, space_nickname=nick)
            for r, nick in rows
        ],
        total=total,
    )


@router.post(
    "/payment-requests",
    response_model=PaymentRequestCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_request(
    user: CurrentWalletUser,
    body: PaymentRequestCreateBody,
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Создать заявку fiat↔stable (без записи в deal)."""
    try:
        row, space_nickname = await svc.create_payment_request(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            direction=body.direction,
            primary_leg=body.primary_leg.model_dump(),
            counter_leg=body.counter_leg.model_dump(),
            heading=body.heading,
            lifetime=body.lifetime,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ValueError as e:
        msg = str(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from e
    return PaymentRequestCreateResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname
        )
    )


@router.post(
    "/payment-requests/{pk}/deactivate",
    response_model=PaymentRequestDeactivateResponse,
)
async def deactivate_payment_request(
    user: CurrentWalletUser,
    body: PaymentRequestDeactivateBody,
    svc: PaymentRequestService = Depends(get_payment_request_service),
    pk: int = Path(..., ge=1),
):
    """Деактивировать заявку после подтверждения номера (pk)."""
    try:
        row, space_nickname = await svc.deactivate_payment_request(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            pk=pk,
            confirm_pk=body.confirm_pk,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ValueError as e:
        msg = str(e)
        if msg == "Заявка не найдена":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from e
    return PaymentRequestDeactivateResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname
        )
    )
