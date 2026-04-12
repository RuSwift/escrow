"""
UI-предпочтения main app: JSON на пару (авторизованный WalletUser + space).
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, status

from core.exceptions import SpacePermissionDenied
from services.wallet_space_ui_prefs import WalletSpaceUIPrefsService
from web.endpoints.dependencies import (
    get_required_wallet_address_for_space,
    get_wallet_space_ui_prefs_service,
)
from web.endpoints.v1.schemas.wallet_space_ui_prefs import WalletSpaceUIPrefsResponse

router = APIRouter(prefix="/spaces", tags=["wallet-space-ui-prefs"])


@router.get("/{space}/ui-prefs", response_model=WalletSpaceUIPrefsResponse)
async def get_ui_prefs(
    space: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: WalletSpaceUIPrefsService = Depends(get_wallet_space_ui_prefs_service),
):
    try:
        payload = await svc.get_prefs(space, wallet_address)
        return WalletSpaceUIPrefsResponse(payload=payload)
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


@router.patch("/{space}/ui-prefs", response_model=WalletSpaceUIPrefsResponse)
async def patch_ui_prefs(
    space: str,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    body: Dict[str, Any] = Body(default_factory=dict),
    svc: WalletSpaceUIPrefsService = Depends(get_wallet_space_ui_prefs_service),
):
    try:
        payload = await svc.patch_prefs(space, wallet_address, body)
        return WalletSpaceUIPrefsResponse(payload=payload)
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
