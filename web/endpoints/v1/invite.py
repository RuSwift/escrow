"""
Публичный API приглашений: данные по токену, nonce, подтверждение подписью.
Без авторизации. TronLink only.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from services.tron_auth import JWT_EXP_SEC
from web.endpoints.dependencies import (
    MAIN_AUTH_TOKEN_COOKIE,
    InviteServiceDep,
    TronAuthDep,
)
from web.endpoints.v1.schemas.invite import (
    InviteConfirmRequest,
    InviteConfirmResponse,
    InviteNonceResponse,
    InvitePayloadResponse,
)

router = APIRouter(prefix="/invite", tags=["invite"])

INVITE_MESSAGE_TEMPLATE = "Please sign this message to authenticate:\n\nNonce: {nonce}"


def _mask_address(addr: str) -> str:
    """Маска адреса для отображения (T…xyz)."""
    if not addr or len(addr) < 8:
        return addr or "—"
    return f"{addr[:2]}…{addr[-4:]}"


@router.get("/{token}", response_model=InvitePayloadResponse)
async def get_invite(
    token: str,
    invite_service: InviteServiceDep,
):
    """Публичные данные приглашения по токену. 404 если токен не найден/истёк/использован."""
    invite = await invite_service.get_invite_by_token(token)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or expired",
        )
    roles_str = [r.value for r in invite.roles]
    return InvitePayloadResponse(
        space_name=invite.space_name,
        inviter_nickname=invite.inviter_nickname,
        roles=roles_str,
        wallet_address=invite.wallet_address,
        wallet_address_mask=_mask_address(invite.wallet_address),
        blockchain=invite.blockchain,
        participant_nickname=invite.participant_nickname,
    )


@router.post("/{token}/nonce", response_model=InviteNonceResponse)
async def get_invite_nonce(
    token: str,
    invite_service: InviteServiceDep,
    tron_auth: TronAuthDep,
):
    """Получить nonce для подписи (адрес берётся из приглашения). 404 при невалидном токене."""
    invite = await invite_service.get_invite_by_token(token)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or expired",
        )
    if (invite.blockchain or "").lower() != "tron":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only TRON is supported for invite verification",
        )
    nonce = await tron_auth.get_nonce(invite.wallet_address)
    message = INVITE_MESSAGE_TEMPLATE.format(nonce=nonce)
    return InviteNonceResponse(nonce=nonce, message=message)


@router.post("/{token}/confirm", response_model=InviteConfirmResponse)
async def confirm_invite(
    request: Request,
    token: str,
    body: InviteConfirmRequest,
    invite_service: InviteServiceDep,
    tron_auth: TronAuthDep,
):
    """
    Проверить подпись, установить is_verified, удалить токен.
    Вернуть JWT и redirect_url; установить cookie для входа в спейс.
    """
    invite = await invite_service.get_invite_by_token(token)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or expired",
        )
    if (invite.blockchain or "").lower() != "tron":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only TRON is supported",
        )
    nonce = await tron_auth.get_stored_nonce(invite.wallet_address)
    if not nonce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nonce expired or already used. Please request a new nonce.",
        )
    message = INVITE_MESSAGE_TEMPLATE.format(nonce=nonce)
    if not tron_auth.verify_signature(
        wallet_address=invite.wallet_address,
        signature=body.signature,
        message=message,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    await tron_auth.consume_nonce(invite.wallet_address)
    updated = await invite_service.set_sub_verified(invite.sub_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update participant",
        )
    await invite_service.consume_token(token)
    await invite_service.commit()
    jwt_token = tron_auth.generate_jwt_token(invite.wallet_address)
    redirect_url = f"/{invite.space_name}"
    host = (request.base_url.hostname or "").lower()
    secure = host not in ("localhost", "127.0.0.1")
    content = InviteConfirmResponse(
        token=jwt_token,
        redirect_url=redirect_url,
        space=invite.space_name,
    )
    response = JSONResponse(content=content.model_dump())
    response.set_cookie(
        key=MAIN_AUTH_TOKEN_COOKIE,
        value=jwt_token,
        httponly=True,
        max_age=JWT_EXP_SEC,
        path="/",
        samesite="lax",
        secure=secure,
    )
    return response
