"""
Router кошельков: CRUD операционных кошельков, список менеджеров.
По аналогии с https://github.com/RuSwift/garantex/blob/main/routers/wallets.py
"""
import logging
from fastapi import APIRouter, HTTPException, status

from didcomm.did import create_peer_did_from_keypair
from core.utils import get_user_did, get_wallet_did
from web.endpoints.dependencies import (
    NodeKeypairOptionalDep,
    RequireAdminDepends,
    WalletServiceDep,
    WalletUserServiceDep,
)
from web.endpoints.v1.schemas.admin import ChangeResponse
from web.endpoints.v1.schemas.wallet import (
    AddManagerRequest,
    CreateWalletRequest,
    ManagerDidDocumentResponse,
    ManagerListResponse,
    ManagerItemResponse,
    UpdateManagerRequest,
    UpdateWalletNameRequest,
    WalletDidDocumentResponse,
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


@router.post("/managers", response_model=ManagerItemResponse, status_code=status.HTTP_201_CREATED)
async def add_manager(
    request: AddManagerRequest,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """Добавить менеджера: выдать доступ в админку по адресу кошелька и никнейму."""
    try:
        user = await wallet_user_service.add_manager(
            wallet_address=request.wallet_address.strip(),
            blockchain=request.blockchain.strip().lower(),
            nickname=request.nickname.strip(),
        )
        return ManagerItemResponse(
            id=user.id,
            nickname=user.nickname,
            wallet_address=user.wallet_address,
            blockchain=user.blockchain,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Error adding manager")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def _minimal_did_document_for_address(did: str) -> dict:
    """Минимальный DID Document для одного адреса (менеджер)."""
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


@router.get("/managers/{user_id}/did-document", response_model=ManagerDidDocumentResponse)
async def get_manager_did_document(
    user_id: int,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """DID и DID Document менеджера (по id пользователя)."""
    user = await wallet_user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found",
        )
    if not user.access_to_admin_panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a manager",
        )
    did = get_user_did(user.wallet_address, user.blockchain)
    did_document = _minimal_did_document_for_address(did)
    return ManagerDidDocumentResponse(
        manager_nickname=user.nickname,
        did=did,
        did_document=did_document,
    )


@router.patch("/managers/{user_id}", response_model=ManagerItemResponse)
async def update_manager(
    user_id: int,
    request: UpdateManagerRequest,
    wallet_user_service: WalletUserServiceDep,
    _admin: RequireAdminDepends,
):
    """Обновить менеджера (доступ в админку). Для отзыва доступа передать access_to_admin_panel: false."""
    updated = await wallet_user_service.update_admin_access(
        user_id, request.access_to_admin_panel
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found",
        )
    return ManagerItemResponse(
        id=updated.id,
        nickname=updated.nickname,
        wallet_address=updated.wallet_address,
        blockchain=updated.blockchain,
    )


def _build_wallet_did_document(
    wallet_did: str,
    tron_address: str | None,
    ethereum_address: str | None,
) -> dict:
    """Один DID Document кошелька с verificationMethod для TRON и Ethereum."""
    verification_method = []
    also_known_as = []
    if tron_address:
        did_tron = get_user_did(tron_address, "tron")
        also_known_as.append(did_tron)
        verification_method.append({
            "id": f"{wallet_did}#tron",
            "type": "EcdsaSecp256k1VerificationKey2019",
            "controller": wallet_did,
        })
    if ethereum_address:
        did_eth = get_user_did(ethereum_address, "ethereum")
        also_known_as.append(did_eth)
        verification_method.append({
            "id": f"{wallet_did}#ethereum",
            "type": "EcdsaSecp256k1VerificationKey2019",
            "controller": wallet_did,
        })
    doc = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": wallet_did,
        "verificationMethod": verification_method,
    }
    if also_known_as:
        doc["alsoKnownAs"] = also_known_as
    return doc


@router.get("/{wallet_id}/did-documents", response_model=WalletDidDocumentResponse)
async def get_wallet_did_documents(
    wallet_id: int,
    wallet_service: WalletServiceDep,
    keypair: NodeKeypairOptionalDep,
    _admin: RequireAdminDepends,
):
    """Один DID и один DID Document кошелька (все адреса TRON и Ethereum внутри)."""
    wallet = await wallet_service.get_wallet(wallet_id)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )
    node_did = None
    if keypair is not None:
        did_obj = create_peer_did_from_keypair(keypair)
        node_did = did_obj.did
    wallet_did = get_wallet_did(wallet_id, node_did or "")
    did_document = _build_wallet_did_document(
        wallet_did,
        wallet.tron_address,
        wallet.ethereum_address,
    )
    return WalletDidDocumentResponse(
        wallet_name=wallet.name,
        did=wallet_did,
        did_document=did_document,
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
