"""
Profile router: GET/PUT /web3/me, /tron/me, GET /user/{identifier}, GET .../me/billing.
Ориентир: https://github.com/RuSwift/garantex/blob/main/routers/wallet_users.py (profile_router).
"""
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status

from services.space import SpaceService
from web.endpoints.dependencies import (
    BillingServiceDep,
    CurrentTronUser,
    CurrentWeb3User,
    SpaceServiceDep,
    WalletUserServiceDep,
)
from web.endpoints.v1.schemas.profile import (
    BillingItem,
    BillingList,
    ProfileResponse,
    UpdateProfileRequest,
)

router = APIRouter(prefix="/profile", tags=["profile"])


def _user_to_profile_response(
    user,
    *,
    primary_wallet_address: str,
    primary_wallet_blockchain: str,
) -> ProfileResponse:
    """Собрать ProfileResponse из WalletUserResource.Get."""
    balance = user.balance_usdt
    if isinstance(balance, Decimal):
        balance = float(balance)
    return ProfileResponse(
        wallet_address=user.wallet_address,
        blockchain=user.blockchain,
        did=user.did,
        nickname=user.nickname,
        company_name=user.profile.company_name if user.profile else None,
        avatar=user.avatar,
        access_to_admin_panel=user.access_to_admin_panel,
        is_verified=user.is_verified,
        balance_usdt=balance,
        primary_wallet_address=primary_wallet_address,
        primary_wallet_blockchain=primary_wallet_blockchain,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


async def _profile_response_for_user(
    user,
    space_service: SpaceService,
) -> ProfileResponse:
    pw = await space_service.get_primary_wallet(user.nickname)
    paddr = (pw.get("address") or "").strip() or user.wallet_address
    pbc = (str(pw.get("blockchain") or user.blockchain or "tron")).strip().lower()
    return _user_to_profile_response(
        user,
        primary_wallet_address=paddr,
        primary_wallet_blockchain=pbc,
    )


# --- Web3 ---


@router.get("/web3/me", response_model=ProfileResponse)
async def get_web3_me(
    current_user: CurrentWeb3User,
    wallet_service: WalletUserServiceDep,
    space_service: SpaceServiceDep,
):
    """Профиль текущего Web3-пользователя."""
    user = await wallet_service.get_by_wallet_address(current_user.wallet_address)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    return await _profile_response_for_user(user, space_service)


@router.put("/web3/me", response_model=ProfileResponse)
async def update_web3_me(
    current_user: CurrentWeb3User,
    wallet_service: WalletUserServiceDep,
    space_service: SpaceServiceDep,
    request: UpdateProfileRequest,
):
    """Обновить профиль (nickname, avatar) текущего Web3-пользователя."""
    try:
        updated = await wallet_service.update_profile(
            wallet_address=current_user.wallet_address,
            nickname=request.nickname,
            avatar=request.avatar,
            company_name=request.company_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await _profile_response_for_user(updated, space_service)


@router.get("/web3/me/billing", response_model=BillingList)
async def get_web3_me_billing(
    current_user: CurrentWeb3User,
    wallet_service: WalletUserServiceDep,
    billing_service: BillingServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """История биллинга текущего Web3-пользователя."""
    user = await wallet_service.get_by_wallet_address(current_user.wallet_address)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    items, total = await billing_service.get_history(user.id, page=page, page_size=page_size)
    return BillingList(
        transactions=[
            BillingItem(id=x.id, wallet_user_id=x.wallet_user_id, usdt_amount=float(x.usdt_amount), created_at=x.created_at)
            for x in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# --- TRON ---


@router.get("/tron/me", response_model=ProfileResponse)
async def get_tron_me(
    current_user: CurrentTronUser,
    wallet_service: WalletUserServiceDep,
    space_service: SpaceServiceDep,
):
    """Профиль текущего TRON-пользователя."""
    user = await wallet_service.get_by_wallet_address(current_user.wallet_address)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    return await _profile_response_for_user(user, space_service)


@router.put("/tron/me", response_model=ProfileResponse)
async def update_tron_me(
    current_user: CurrentTronUser,
    wallet_service: WalletUserServiceDep,
    space_service: SpaceServiceDep,
    request: UpdateProfileRequest,
):
    """Обновить профиль текущего TRON-пользователя."""
    try:
        updated = await wallet_service.update_profile(
            wallet_address=current_user.wallet_address,
            nickname=request.nickname,
            avatar=request.avatar,
            company_name=request.company_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return await _profile_response_for_user(updated, space_service)


@router.get("/tron/me/billing", response_model=BillingList)
async def get_tron_me_billing(
    current_user: CurrentTronUser,
    wallet_service: WalletUserServiceDep,
    billing_service: BillingServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """История биллинга текущего TRON-пользователя."""
    user = await wallet_service.get_by_wallet_address(current_user.wallet_address)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    items, total = await billing_service.get_history(user.id, page=page, page_size=page_size)
    return BillingList(
        transactions=[
            BillingItem(id=x.id, wallet_user_id=x.wallet_user_id, usdt_amount=float(x.usdt_amount), created_at=x.created_at)
            for x in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# --- Public ---


@router.get("/user/{identifier}", response_model=ProfileResponse)
async def get_user_profile(
    identifier: str,
    wallet_service: WalletUserServiceDep,
    space_service: SpaceServiceDep,
):
    """Публичный профиль по id (число) или DID (строка, начинается с 'did:')."""
    try:
        user = await wallet_service.get_by_identifier(identifier)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="identifier must be user id (integer) or DID (string starting with 'did:')",
        )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await _profile_response_for_user(user, space_service)
