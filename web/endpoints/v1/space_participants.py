"""
API участников спейса: список, добавление, редактирование, удаление, invite-link, профиль спейса.
Только owner спейса. Валидация blockchain+address при создании.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from core.exceptions import (
    DuplicateParticipant,
    InvalidWalletAddress,
    MissingNickname,
    SpacePermissionDenied,
)
from i18n.translations import locale_from_accept_language
from repos.wallet_user import WalletUserProfileSchema, WalletUserSubResource
from services.space import SpaceService
from web.endpoints.dependencies import (
    get_required_wallet_address_for_space,
    InviteServiceDep,
    SpaceServiceDep,
)
from web.endpoints.v1.schemas.invite import InviteLinkResponse

router = APIRouter(prefix="/spaces", tags=["space-participants"])


class SignatoryTronLabelItem(BaseModel):
    tron_address: str
    nickname: str


class SignatoryTronLabelsResponse(BaseModel):
    items: List[SignatoryTronLabelItem]


@router.get(
    "/{space}/profile",
    response_model=Optional[WalletUserProfileSchema],
)
async def get_space_profile(
    space: str,
    space_service: SpaceServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """Профиль спейса (description, icon, primary_wallet). Только owner."""
    try:
        profile = await space_service.get_space_profile(space, wallet_address)
        if profile is None:
            profile = {}
        
        # Добавляем primary wallet в ответ
        pw = await space_service.get_primary_wallet(space)
        profile["primary_wallet"] = pw
        
        return WalletUserProfileSchema(**profile)
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner can get space profile",
        )


@router.patch(
    "/{space}/profile",
    response_model=WalletUserProfileSchema,
)
async def patch_space_profile(
    request: Request,
    space: str,
    data: WalletUserProfileSchema,
    space_service: SpaceServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """Обновить профиль спейса. Только owner. Лимит иконки 512 КБ."""
    try:
        accept = locale_from_accept_language(
            request.headers.get("accept-language")
        )
        
        # Если передан primary_wallet, обновляем его отдельно
        if data.primary_wallet:
            await space_service.update_primary_wallet(
                space, 
                wallet_address, 
                data.primary_wallet.address, 
                data.primary_wallet.blockchain
            )

        result = await space_service.update_space_profile(
            space,
            wallet_address,
            data,
            accept_language=accept,
        )
        
        # Добавляем актуальный primary wallet в ответ
        pw = await space_service.get_primary_wallet(space)
        result["primary_wallet"] = pw
        
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner can update space profile",
        )
    except InvalidWalletAddress as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_wallet_address", "message": str(e)},
        )
    except ValueError as e:
        msg = str(e)
        if "512 KB" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile icon size is too large (max 512 KB)",
            )
        if "Profile description" in msg or "description" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=msg,
            )
        raise
    return WalletUserProfileSchema(**result)


@router.get(
    "/{space}/participants",
    response_model=List[WalletUserSubResource.Get],
)
async def list_participants(
    space: str,
    space_service: SpaceServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """Список участников спейса. Owner или operator."""
    try:
        return await space_service.list_subs_for_space(space, wallet_address)
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner or operator can list participants",
        )


@router.get(
    "/{space}/signatory-tron-labels",
    response_model=SignatoryTronLabelsResponse,
)
async def list_signatory_tron_labels(
    space: str,
    space_service: SpaceServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """TRON → отображаемое имя: участники спейса и при отсутствии дубля — владелец (дашборд заявок)."""
    try:
        rows = await space_service.signatory_tron_labels(space, wallet_address)
        return SignatoryTronLabelsResponse(
            items=[SignatoryTronLabelItem(**r) for r in rows]
        )
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner or operator can list signatory labels",
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
            detail={"code": "invalid_wallet_address", "message": str(e)},
        )
    except MissingNickname as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "missing_nickname", "message": str(e)},
        )
    except DuplicateParticipant as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "duplicate_participant", "message": str(e)},
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
    except MissingNickname as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "missing_nickname", "message": str(e)},
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


@router.post(
    "/{space}/participants/{participant_id}/invite-link",
    response_model=InviteLinkResponse,
)
async def create_invite_link(
    request: Request,
    space: str,
    participant_id: int,
    space_service: SpaceServiceDep,
    invite_service: InviteServiceDep,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """Создать одноразовую ссылку приглашения для участника. Только owner. Участник должен быть не верифицирован."""
    try:
        subs = await space_service.list_subs_for_space(space, wallet_address)
    except SpacePermissionDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only space owner can create invite links",
        )
    sub = next((s for s in subs if s.id == participant_id), None)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    if sub.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Participant is already verified",
        )
    if sub.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create invite link for blocked participant",
        )
    token, expires_at = await invite_service.create_token(sub.id, space)
    base = str(request.base_url).rstrip("/")
    invite_link = f"{base}/v/{token}"
    return InviteLinkResponse(invite_link=invite_link, expires_at=expires_at)
