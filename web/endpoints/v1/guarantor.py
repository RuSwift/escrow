"""
Панель гаранта: GET/PATCH профиль, список/создание/удаление направлений.
Только owner спейса (как /spaces/{space}/profile).
"""
from fastapi import APIRouter, Depends, HTTPException, status

from core.exceptions import SpacePermissionDenied
from services.guarantor import GuarantorService
from web.endpoints.dependencies import (
    get_guarantor_service,
    get_required_wallet_address_for_space,
)
from web.endpoints.v1.schemas.guarantor import (
    CreateGuarantorDirectionRequest,
    GuarantorDirectionResponse,
    GuarantorProfileResponse,
    GuarantorStateResponse,
    PatchGuarantorProfileRequest,
)

router = APIRouter(prefix="/spaces", tags=["guarantor"])


def _profile_to_response(row) -> GuarantorProfileResponse:
    return GuarantorProfileResponse(
        id=int(row.id),
        wallet_user_id=int(row.wallet_user_id),
        space=row.space,
        commission_percent=row.commission_percent,
        conditions_text=row.conditions_text,
    )


def _direction_to_response(row) -> GuarantorDirectionResponse:
    return GuarantorDirectionResponse(
        id=int(row.id),
        space=row.space,
        currency_code=row.currency_code,
        payment_code=row.payment_code,
        payment_name=row.payment_name,
        conditions_text=row.conditions_text,
        commission_percent=row.commission_percent,
        sort_order=int(row.sort_order),
    )


@router.get("/{space}/guarantor", response_model=GuarantorStateResponse)
async def get_guarantor_state(
    space: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: GuarantorService = Depends(get_guarantor_service),
):
    """Профиль гаранта (автосоздание с комиссией 0.1%), направления, верификация."""
    try:
        profile, directions, is_verified = await svc.get_state(space, wallet_address)
    except SpacePermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return GuarantorStateResponse(
        profile=_profile_to_response(profile),
        directions=[_direction_to_response(d) for d in directions],
        is_verified=is_verified,
    )


@router.patch("/{space}/guarantor/profile", response_model=GuarantorProfileResponse)
async def patch_guarantor_profile(
    space: str,
    body: PatchGuarantorProfileRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: GuarantorService = Depends(get_guarantor_service),
):
    """Обновить базовую комиссию / общие условия профиля гаранта."""
    raw = body.model_dump(exclude_unset=True)
    comm = ... if "commission_percent" not in raw else raw["commission_percent"]
    cond = ... if "conditions_text" not in raw else raw["conditions_text"]
    try:
        profile = await svc.patch_profile(
            space,
            wallet_address,
            commission_percent=comm,
            conditions_text=cond,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _profile_to_response(profile)


@router.post("/{space}/guarantor/directions", response_model=GuarantorDirectionResponse)
async def create_guarantor_direction(
    space: str,
    body: CreateGuarantorDirectionRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: GuarantorService = Depends(get_guarantor_service),
):
    """Добавить направление (валюта + платёжный метод) для space."""
    try:
        row = await svc.create_direction(
            space,
            wallet_address,
            currency_code=body.currency_code,
            payment_code=body.payment_code,
            payment_name=body.payment_name,
            conditions_text=body.conditions_text,
            commission_percent=body.commission_percent,
            sort_order=body.sort_order,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _direction_to_response(row)


@router.delete("/{space}/guarantor/directions/{direction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guarantor_direction(
    space: str,
    direction_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: GuarantorService = Depends(get_guarantor_service),
):
    """Удалить направление."""
    try:
        ok = await svc.delete_direction(space, direction_id, wallet_address)
    except SpacePermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Direction not found")
    return None
