"""
Router кошельков: CRUD операционных кошельков, список менеджеров.
По аналогии с https://github.com/RuSwift/garantex/blob/main/routers/wallets.py
"""
import logging
from fastapi import APIRouter, HTTPException, status

from web.endpoints.dependencies import (
    RequireAdminDepends,
    WalletServiceDep,
    WalletUserServiceDep,
)
from web.endpoints.v1.schemas.admin import ChangeResponse
from web.endpoints.v1.schemas.wallet import (
    CreateWalletRequest,
    ManagerListResponse,
    ManagerItemResponse,
    UpdateWalletNameRequest,
    WalletListResponse,
    WalletResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallets", tags=["wallets"])


def _wallet_to_response(w):
    """WalletResource.Get -> WalletResponse."""
    return WalletResponse(
        id=w.id,
        name=w.name,
        tron_address=w.tron_address,
        ethereum_address=w.ethereum_address,
        account_permissions=w.account_permissions,
        created_at=w.created_at,
        updated_at=w.updated_at,
    )


@router.post("", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
async def create_wallet(
    request: CreateWalletRequest,
    wallet_service: WalletServiceDep,
    _admin: RequireAdminDepends,
):
    """Создать кошелёк из мнемоники (имя + мнемоническая фраза)."""
    try:
        wallet = await wallet_service.create_wallet(
            name=request.name,
            mnemonic=request.mnemonic,
        )
        return _wallet_to_response(wallet)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error creating wallet")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("", response_model=WalletListResponse)
async def list_wallets(
    wallet_service: WalletServiceDep,
    _admin: RequireAdminDepends,
):
    """Список операционных кошельков (role=None)."""
    try:
        wallets = await wallet_service.get_wallets()
        return WalletListResponse(
            wallets=[_wallet_to_response(w) for w in wallets],
            total=len(wallets),
        )
    except Exception as e:
        logger.exception("Error listing wallets")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/managers", response_model=ManagerListResponse)
async def list_managers(
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """Список менеджеров (WalletUser с доступом в админку)."""
    try:
        users = await wallet_user_service.list_managers()
        return ManagerListResponse(
            managers=[
                ManagerItemResponse(
                    id=u.id,
                    nickname=u.nickname,
                    wallet_address=u.wallet_address,
                    blockchain=u.blockchain,
                )
                for u in users
            ],
            total=len(users),
        )
    except Exception as e:
        logger.exception("Error listing managers")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: int,
    wallet_service: WalletServiceDep,
    _admin: RequireAdminDepends,
):
    """Получить кошелёк по id."""
    wallet = await wallet_service.get_wallet(wallet_id)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    return _wallet_to_response(wallet)


@router.put("/{wallet_id}/name", response_model=WalletResponse)
async def update_wallet_name(
    wallet_id: int,
    request: UpdateWalletNameRequest,
    wallet_service: WalletServiceDep,
    _admin: RequireAdminDepends,
):
    """Обновить имя кошелька."""
    wallet = await wallet_service.update_wallet_name(wallet_id, request.name)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    return _wallet_to_response(wallet)


@router.delete("/{wallet_id}", response_model=ChangeResponse)
async def delete_wallet(
    wallet_id: int,
    wallet_service: WalletServiceDep,
    _admin: RequireAdminDepends,
):
    """Удалить кошелёк."""
    deleted = await wallet_service.delete_wallet(wallet_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    return ChangeResponse(success=True, message="Wallet deleted successfully")
