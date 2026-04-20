"""Simple UI: JSON API с контекстом арбитра в path: /v1/arbiter/{arbiter_space_did}/..."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from core.exceptions import SpacePermissionDenied
from services.arbiter_path import ArbiterPathResolveService
from services.payment_request import PaymentRequestService
from services.simple_resolve import ResolvedDeal, ResolvedPaymentRequest, SimpleResolveService
from web.endpoints.dependencies import (
    CurrentWalletUser,
    get_arbiter_path_resolve_service,
    get_payment_request_service,
    get_simple_resolve_service,
)
from web.endpoints.v1.schemas.payment_requests import (
    PaymentRequestCreateBody,
    PaymentRequestCreateResponse,
    PaymentRequestDeactivateBody,
    PaymentRequestDeactivateResponse,
    PaymentRequestListResponse,
    PaymentRequestOut,
)
from web.endpoints.v1.schemas.simple_resolve import SimpleDealOut, SimpleResolveResponse

router = APIRouter(prefix="/arbiter/{arbiter_space_did}", tags=["simple"])


async def get_resolved_arbiter_did(
    arbiter_space_did: str,
    resolver: ArbiterPathResolveService = Depends(get_arbiter_path_resolve_service),
) -> str:
    did = await resolver.to_arbiter_did(arbiter_space_did)
    if not did:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Арбитр не найден",
        )
    return did


ResolvedArbiterDid = Annotated[str, Depends(get_resolved_arbiter_did)]


@router.get("/resolve/{public_uid}", response_model=SimpleResolveResponse)
async def resolve_simple_context(
    arbiter_did: ResolvedArbiterDid,
    _user: CurrentWalletUser,
    public_uid: str,
    svc: SimpleResolveService = Depends(get_simple_resolve_service),
):
    """Контекст для /arbiter/{arbiter}/deal/{segment}: PaymentRequest по uid или public_ref, иначе Deal по uid."""
    arb = arbiter_did
    result = await svc.resolve_public_uid(public_uid, arbiter_space_did=arb)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка или сделка не найдена",
        )
    if isinstance(result, ResolvedPaymentRequest):
        return SimpleResolveResponse(
            kind="payment_request_only",
            payment_request=PaymentRequestOut.from_model(
                result.row, space_nickname=result.space_nickname
            ),
            deal=None,
        )
    assert isinstance(result, ResolvedDeal)
    return SimpleResolveResponse(
        kind="deal_only",
        payment_request=None,
        deal=SimpleDealOut.from_model(result.row),
    )


@router.get("/payment-requests", response_model=PaymentRequestListResponse)
async def list_payment_requests(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    svc: PaymentRequestService = Depends(get_payment_request_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=512),
):
    """Список заявок PaymentRequest для текущего кошелька в контексте арбитра."""
    try:
        rows, total = await svc.list_payment_requests(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            arbiter_did=arbiter_did,
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
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    body: PaymentRequestCreateBody,
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Создать заявку fiat↔stable (без записи в deal); arbiter_did из path."""
    try:
        row, space_nickname = await svc.create_payment_request(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            arbiter_did=arbiter_did,
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
    arbiter_did: ResolvedArbiterDid,
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
            arbiter_did=arbiter_did,
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
