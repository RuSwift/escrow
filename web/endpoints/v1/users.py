"""
Router пользователей (admin): список, CRUD, баланс, история, DID Document.
"""
import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status

from core.utils import get_user_did
from web.endpoints.dependencies import (
    BillingServiceDep,
    RequireAdminDepends,
    WalletUserServiceDep,
)
from web.endpoints.v1.schemas.profile import BillingItem, BillingList
from web.endpoints.v1.schemas.users import (
    BalanceOperationRequest,
    CreateUserRequest,
    UpdateUserRequest,
    UserDidDocumentResponse,
    UserItem,
    UserListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


def _user_to_item(u) -> UserItem:
    """WalletUserResource.Get -> UserItem."""
    balance = u.balance_usdt
    if hasattr(balance, "__float__"):
        balance = float(balance)
    return UserItem(
        id=u.id,
        wallet_address=u.wallet_address,
        blockchain=u.blockchain,
        nickname=u.nickname,
        is_verified=u.is_verified,
        access_to_admin_panel=u.access_to_admin_panel,
        balance_usdt=balance,
        created_at=u.created_at,
        updated_at=u.updated_at,
    )


def _minimal_did_document_for_address(did: str) -> dict:
    """Минимальный DID Document для одного адреса (для diddoc-modal)."""
    return {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did,
        "verificationMethod": [
            {
                "id": f"{did}#controller",
                "type": "EcdsaSecp256k1VerificationKey2019",
                "controller": did,
            }
        ],
    }


@router.get("", response_model=UserListResponse)
async def list_users(
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
    search: str | None = Query(None, description="Поиск по адресу, никнейму или ID"),
    blockchain: str | None = Query(None, description="Фильтр по блокчейну"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Список пользователей с пагинацией и фильтрами."""
    users, total = await wallet_user_service.list_users_for_admin(
        search=search,
        blockchain=blockchain,
        page=page,
        page_size=page_size,
    )
    return UserListResponse(
        users=[_user_to_item(u) for u in users],
        total=total,
    )


@router.post("", response_model=UserItem, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """Создать пользователя (админ)."""
    try:
        created = await wallet_user_service.create_user(
            wallet_address=request.wallet_address,
            blockchain=request.blockchain,
            nickname=request.nickname,
            access_to_admin_panel=request.access_to_admin_panel,
            is_verified=request.is_verified,
        )
        return _user_to_item(created)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{user_id}", response_model=UserItem)
async def get_user(
    user_id: int,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """Один пользователь по id."""
    user = await wallet_user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return _user_to_item(user)


@router.patch("/{user_id}", response_model=UserItem)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """Обновить пользователя (nickname, is_verified, access_to_admin_panel)."""
    try:
        updated = await wallet_user_service.update_user_admin(
            user_id,
            nickname=request.nickname,
            is_verified=request.is_verified,
            access_to_admin_panel=request.access_to_admin_panel,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return _user_to_item(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """Удалить пользователя."""
    deleted = await wallet_user_service.delete_user(user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


@router.post("/{user_id}/balance", response_model=UserItem)
async def balance_operation(
    user_id: int,
    request: BalanceOperationRequest,
    wallet_user_service: WalletUserServiceDep,
    billing_service: BillingServiceDep,
    _admin: RequireAdminDepends,
):
    """Пополнить или списать баланс пользователя."""
    if request.operation_type not in ("replenish", "withdraw"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="operation_type must be 'replenish' or 'withdraw'",
        )
    amount = request.amount
    if request.operation_type == "withdraw":
        amount = -amount
    try:
        await billing_service.add_transaction(user_id, amount)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    user = await wallet_user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return _user_to_item(user)


@router.get("/{user_id}/billing", response_model=BillingList)
async def get_user_billing(
    user_id: int,
    billing_service: BillingServiceDep,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """История операций пользователя (биллинг)."""
    user = await wallet_user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    items, total = await billing_service.get_history(
        wallet_user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return BillingList(
        transactions=[
            BillingItem(
                id=x.id,
                wallet_user_id=x.wallet_user_id,
                usdt_amount=float(x.usdt_amount),
                created_at=x.created_at,
            )
            for x in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}/did-document", response_model=UserDidDocumentResponse)
async def get_user_did_document(
    user_id: int,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """DID и DID Document пользователя (для diddoc-modal)."""
    user = await wallet_user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    did = get_user_did(user.wallet_address, user.blockchain)
    did_document = _minimal_did_document_for_address(did)
    return UserDidDocumentResponse(did=did, did_document=did_document)
