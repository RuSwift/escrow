"""Переопределения форм payment_code в спейсе и effective-форма (owner only)."""

from __future__ import annotations

from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, status

from core.exceptions import SpacePermissionDenied
from services.space_payment_form_admin import (
    SpacePaymentFormAdminError,
    SpacePaymentFormAdminService,
)
from web.endpoints.dependencies import (
    get_required_wallet_address_for_space,
    get_space_payment_form_admin_service,
)
from web.endpoints.v1.schemas.space_payment_forms import (
    EffectivePaymentFormResponse,
    PutSpacePaymentFormRequest,
    SpacePaymentFormOverrideListResponse,
    SpacePaymentFormOverrideSummary,
)

router = APIRouter(prefix="/spaces", tags=["space-payment-forms"])


@router.get(
    "/{space}/payment-forms/{payment_code}",
    response_model=EffectivePaymentFormResponse,
)
async def get_effective_payment_form(
    space: str,
    payment_code: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpacePaymentFormAdminService = Depends(get_space_payment_form_admin_service),
):
    code = unquote((payment_code or "").strip())
    try:
        form, src = await svc.get_effective(space, wallet_address, code)
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    dumped = form.model_dump(mode="json") if form is not None else None
    return EffectivePaymentFormResponse(
        payment_code=code,
        source=src,
        form=dumped,
    )


@router.get(
    "/{space}/payment-forms",
    response_model=SpacePaymentFormOverrideListResponse,
)
async def list_payment_form_overrides(
    space: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpacePaymentFormAdminService = Depends(get_space_payment_form_admin_service),
):
    try:
        rows = await svc.list_overrides(space, wallet_address)
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    items = [
        SpacePaymentFormOverrideSummary(
            id=int(r.id),
            payment_code=r.payment_code,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return SpacePaymentFormOverrideListResponse(items=items)


@router.put(
    "/{space}/payment-forms/{payment_code}",
    response_model=SpacePaymentFormOverrideSummary,
)
async def put_payment_form_override(
    space: str,
    payment_code: str,
    body: PutSpacePaymentFormRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpacePaymentFormAdminService = Depends(get_space_payment_form_admin_service),
):
    code = unquote((payment_code or "").strip())
    try:
        row = await svc.put_override(
            space,
            wallet_address,
            code,
            body.model_dump(mode="json"),
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except SpacePaymentFormAdminError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message},
        ) from e
    return SpacePaymentFormOverrideSummary(
        id=int(row.id),
        payment_code=row.payment_code,
        updated_at=row.updated_at,
    )


@router.delete(
    "/{space}/payment-forms/{payment_code}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_payment_form_override(
    space: str,
    payment_code: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: SpacePaymentFormAdminService = Depends(get_space_payment_form_admin_service),
):
    code = unquote((payment_code or "").strip())
    try:
        ok = await svc.delete_override(space, wallet_address, code)
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return None
