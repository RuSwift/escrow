"""Simple UI: JSON API без {space} в path — space из JWT/cookie."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.exceptions import SpacePermissionDenied
from services.deal import DealService
from web.endpoints.dependencies import CurrentWalletUser, get_deal_service
from web.endpoints.v1.schemas.simple_deals import (
    SimpleApplicationCreateRequest,
    SimpleApplicationCreateResponse,
    SimpleDealListResponse,
    SimpleDealOut,
)

router = APIRouter(prefix="/simple", tags=["simple"])


@router.get("/deals", response_model=SimpleDealListResponse)
async def list_simple_deals(
    user: CurrentWalletUser,
    svc: DealService = Depends(get_deal_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=512),
):
    """Список Simple-заявок (Deal) для текущего кошелька / спейса из авторизации."""
    try:
        rows, total = await svc.list_simple_applications(
            wallet_address=user.wallet_address,
            actor_did=user.did,
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
    return SimpleDealListResponse(
        items=[SimpleDealOut.model_validate(r) for r in rows],
        total=total,
    )


@router.post(
    "/deals/simple-application",
    response_model=SimpleApplicationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_simple_deal_application(
    user: CurrentWalletUser,
    body: SimpleApplicationCreateRequest,
    svc: DealService = Depends(get_deal_service),
):
    """Создать заявку fiat↔stable как Deal (Simple)."""
    try:
        deal = await svc.create_simple_application(
            wallet_address=user.wallet_address,
            sender_did=user.did,
            standard=user.standard,
            direction=body.direction,
            primary_leg=body.primary_leg.model_dump(),
            counter_leg=body.counter_leg.model_dump(),
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ValueError as e:
        msg = str(e)
        if "Arbiter not configured" in msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=msg,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from e
    return SimpleApplicationCreateResponse(deal=SimpleDealOut.model_validate(deal))
