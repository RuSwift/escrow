"""CRUD конфигураций onRamp/offRamp (exchange_services) в разрезе space — только owner."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from core.exceptions import SpacePermissionDenied
from services.space_exchange_service import ExchangeServiceValidationError, SpaceExchangeService
from web.endpoints.dependencies import (
    get_required_wallet_address_for_space,
    get_space_exchange_service,
)
from web.endpoints.v1.schemas.space_exchange_services import (
    CreateExchangeServiceRequest,
    ExchangeServiceListResponse,
    ExchangeServiceOut,
    PatchExchangeServiceRequest,
    exchange_service_to_out,
)
from web.endpoints.v1.schemas.space_payment_forms import EffectivePaymentFormResponse

router = APIRouter(prefix="/spaces", tags=["exchange-services"])


@router.get("/{space}/exchange-services", response_model=ExchangeServiceListResponse)
async def list_exchange_services(
    space: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpaceExchangeService = Depends(get_space_exchange_service),
):
    try:
        rows = await svc.list_services(space, wallet_address)
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    items = [exchange_service_to_out(r, tiers) for r, tiers in rows]
    return ExchangeServiceListResponse(items=items)


@router.post(
    "/{space}/exchange-services",
    response_model=ExchangeServiceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_exchange_service(
    space: str,
    body: CreateExchangeServiceRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpaceExchangeService = Depends(get_space_exchange_service),
):
    payload = body.model_dump(mode="json")
    fee_tiers = payload.pop("fee_tiers", None)
    if fee_tiers:
        fee_tiers = [
            {
                "fiat_min": t["fiat_min"],
                "fiat_max": t["fiat_max"],
                "fee_percent": t["fee_percent"],
                "sort_order": t.get("sort_order", 0),
            }
            for t in fee_tiers
        ]
    try:
        row, tiers = await svc.create_service(
            space,
            wallet_address,
            payload=payload,
            fee_tiers=fee_tiers,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ExchangeServiceValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message},
        ) from e
    return exchange_service_to_out(row, tiers)


@router.get("/{space}/exchange-services/{service_id}", response_model=ExchangeServiceOut)
async def get_exchange_service(
    space: str,
    service_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpaceExchangeService = Depends(get_space_exchange_service),
):
    try:
        result = await svc.get_service(space, service_id, wallet_address)
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    row, tiers = result
    return exchange_service_to_out(row, tiers)


@router.get(
    "/{space}/exchange-services/{service_id}/payment-form",
    response_model=EffectivePaymentFormResponse,
)
async def get_exchange_service_payment_form(
    space: str,
    service_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpaceExchangeService = Depends(get_space_exchange_service),
):
    """Effective-форма реквизитов направления: кастом из БД или space/system из каталога."""
    try:
        result = await svc.get_effective_payment_form(
            space, service_id, wallet_address
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    form, src, payment_code = result
    dumped = form.model_dump(mode="json") if form is not None else None
    return EffectivePaymentFormResponse(
        payment_code=payment_code,
        source=src,
        form=dumped,
    )


@router.patch("/{space}/exchange-services/{service_id}", response_model=ExchangeServiceOut)
async def patch_exchange_service(
    space: str,
    service_id: int,
    body: PatchExchangeServiceRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpaceExchangeService = Depends(get_space_exchange_service),
):
    raw = body.model_dump(exclude_unset=True)
    replace_fee_tiers = bool(raw.pop("replace_fee_tiers", False))
    fee_tiers = raw.pop("fee_tiers", None)
    if fee_tiers is not None:
        fee_tiers = [
            {
                "fiat_min": t["fiat_min"],
                "fiat_max": t["fiat_max"],
                "fee_percent": t["fee_percent"],
                "sort_order": t.get("sort_order", 0),
            }
            for t in fee_tiers
        ]
    try:
        result = await svc.patch_service(
            space,
            service_id,
            wallet_address,
            payload=raw,
            fee_tiers=fee_tiers,
            replace_fee_tiers=replace_fee_tiers,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ExchangeServiceValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message},
        ) from e
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    row, tiers = result
    return exchange_service_to_out(row, tiers)


@router.delete(
    "/{space}/exchange-services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_exchange_service(
    space: str,
    service_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpaceExchangeService = Depends(get_space_exchange_service),
):
    try:
        ok = await svc.delete_service(space, service_id, wallet_address)
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return None
