"""
API участников спейса: список, добавление, редактирование, удаление.
Только owner спейса. Валидация blockchain+address при создании.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from repos.wallet_user import WalletUserSubResource
from services.space import InvalidWalletAddress, SpacePermissionDenied, SpaceService
from web.endpoints.dependencies import (
    get_required_wallet_address_for_space,
    SpaceServiceDep,
)

router = APIRouter(prefix="/spaces", tags=["space-participants"])


@router.get(
    "/{space}/participants",
    response_model=List[WalletUserSubResource.Get],
)
async def list_participants(
    space: str,
    space_service: SpaceServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """Список участников спейса. Только owner."""
    try:
        return await space_service.list_subs_for_space(space, wallet_address)
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner can list participants",
        )


@router.post(
    "/{space}/participants",
    response_model=WalletUserSubResource.Get,
    status_code=status.HTTP_201_CREATED,
)
async def add_participant(
    space: str,
    data: WalletUserSubResource.Create,
    space_service: SpaceServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """Добавить участника в спейс. Только owner. Валидирует blockchain+address."""
    try:
        return await space_service.add_sub_for_space(space, wallet_address, data)
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner can add participants",
        )
    except InvalidWalletAddress as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/{space}/participants/{participant_id}",
    response_model=WalletUserSubResource.Get,
)
async def patch_participant(
    space: str,
    participant_id: int,
    data: WalletUserSubResource.Patch,
    space_service: SpaceServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """Обновить участника (nickname, roles, is_verified). Только owner."""
    try:
        updated = await space_service.patch_sub_for_space(
            space, wallet_address, participant_id, data
        )
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner can update participants",
        )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    return updated


@router.delete(
    "/{space}/participants/{participant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_participant(
    space: str,
    participant_id: int,
    space_service: SpaceServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """Удалить участника из спейса. Только owner."""
    try:
        deleted = await space_service.delete_sub_for_space(
            space, wallet_address, participant_id
        )
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner can delete participants",
        )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
