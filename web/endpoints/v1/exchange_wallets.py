"""
Реквизиты Ramp: Wallet с role external | multisig в разрезе space (только owner).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.exceptions import SpacePermissionDenied
from repos.wallet import ExchangeWalletResource

from services.exchange_wallets import ExchangeWalletService, MultisigDeleteBlockedError
from services.multisig_wallet.meta import meta_for_api
from web.endpoints.dependencies import (
    get_exchange_wallet_service,
    get_required_wallet_address_for_space,
)
from web.endpoints.v1.schemas.exchange_wallets import (
    CreateExchangeWalletRequest,
    ExchangeWalletItem,
    ExchangeWalletListResponse,
    MultisigPermissionBroadcastRequest,
    MultisigPermissionTransactionResponse,
    PatchExchangeWalletRequest,
)

router = APIRouter(prefix="/spaces", tags=["exchange-wallets"])

_MULTISIG_PATCH_KEYS = frozenset(
    {
        "multisig_actors",
        "multisig_owners",
        "multisig_threshold_n",
        "multisig_threshold_m",
        "multisig_retry",
        "multisig_min_trx_sun",
        "multisig_permission_name",
        "multisig_begin_reconfigure",
        "multisig_cancel_reconfigure",
    }
)


def _to_item(
    row: ExchangeWalletResource.Get,
    *,
    multisig_can_sign_permission_tronlink: Optional[bool] = None,
) -> ExchangeWalletItem:
    r = row.role if row.role in ("external", "multisig") else "external"
    ms_meta = None
    ms_st = None
    can_tron = None
    if r == "multisig":
        ms_st = getattr(row, "multisig_setup_status", None)
        ms_meta = meta_for_api(getattr(row, "multisig_setup_meta", None)) or None
        can_tron = multisig_can_sign_permission_tronlink
    return ExchangeWalletItem(
        id=row.id,
        name=row.name,
        tron_address=row.tron_address,
        ethereum_address=row.ethereum_address,
        role=r,  # type: ignore[arg-type]
        owner_did=row.owner_did,
        created_at=row.created_at,
        updated_at=row.updated_at,
        multisig_setup_status=ms_st,
        multisig_setup_meta=ms_meta,
        multisig_can_sign_permission_tronlink=can_tron,
    )


async def _to_item_with_tronlink_flag(
    svc: ExchangeWalletService,
    row: ExchangeWalletResource.Get,
    viewer_wallet_address: str,
) -> ExchangeWalletItem:
    can = None
    if row.role == "multisig":
        can = await svc.multisig_can_sign_permission_tronlink(row, viewer_wallet_address)
    return _to_item(row, multisig_can_sign_permission_tronlink=can)


@router.get("/{space}/exchange-wallets", response_model=ExchangeWalletListResponse)
async def list_exchange_wallets(
    space: str,
    role: Optional[str] = Query(
        default=None,
        description="Фильтр: external или multisig",
    ),
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    try:
        r = None
        if role in ("external", "multisig"):
            r = role  # type: ignore[assignment]
        rows: List[ExchangeWalletResource.Get] = await svc.list_wallets(
            space, wallet_address, role=r
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    out: List[ExchangeWalletItem] = []
    for x in rows:
        out.append(await _to_item_with_tronlink_flag(svc, x, wallet_address))
    return ExchangeWalletListResponse(items=out)


@router.post(
    "/{space}/exchange-wallets",
    response_model=ExchangeWalletItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_exchange_wallet(
    space: str,
    body: CreateExchangeWalletRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    try:
        created = await svc.create_wallet(
            space,
            wallet_address,
            role=body.role,
            blockchain=body.blockchain,
            name=body.name,
            tron_address=body.tron_address,
            participant_sub_id=body.participant_sub_id,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return await _to_item_with_tronlink_flag(svc, created, wallet_address)


@router.patch("/{space}/exchange-wallets/{wallet_id}", response_model=ExchangeWalletItem)
async def patch_exchange_wallet(
    space: str,
    wallet_id: int,
    body: PatchExchangeWalletRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    raw = body.model_dump(exclude_unset=True)
    ms_kw = {k: raw[k] for k in _MULTISIG_PATCH_KEYS if k in raw}
    if ms_kw:
        try:
            ms_out = await svc.patch_multisig_setup(
                space,
                wallet_address,
                wallet_id,
                **ms_kw,
            )
            if ms_out is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
                )
        except SpacePermissionDenied as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e
    kwargs = {}
    for key in ("name", "tron_address", "ethereum_address", "mnemonic"):
        if key in raw and key not in _MULTISIG_PATCH_KEYS:
            kwargs[key] = raw[key]
    try:
        updated = await svc.patch_wallet_with_plain_fields(
            space,
            wallet_address,
            wallet_id,
            **kwargs,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return await _to_item_with_tronlink_flag(svc, updated, wallet_address)


@router.delete("/{space}/exchange-wallets/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exchange_wallet(
    space: str,
    wallet_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    try:
        ok = await svc.delete_wallet(space, wallet_address, wallet_id)
    except MultisigDeleteBlockedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": e.code, **e.extra},
        ) from e
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return None


@router.post(
    "/{space}/exchange-wallets/{wallet_id}/multisig-maintenance",
    response_model=ExchangeWalletItem,
)
async def post_multisig_maintenance(
    space: str,
    wallet_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    """Немедленный тик обслуживания multisig (баланс TRX, broadcast, проверка tx)."""
    try:
        updated = await svc.refresh_multisig_maintenance(
            space, wallet_address, wallet_id
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return await _to_item_with_tronlink_flag(svc, updated, wallet_address)


@router.post(
    "/{space}/exchange-wallets/{wallet_id}/multisig-permission-transaction",
    response_model=MultisigPermissionTransactionResponse,
)
async def post_multisig_permission_transaction(
    space: str,
    wallet_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    try:
        data = await svc.build_multisig_permission_transaction(
            space, wallet_address, wallet_id
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return MultisigPermissionTransactionResponse(transaction=data["transaction"])


@router.post(
    "/{space}/exchange-wallets/{wallet_id}/multisig-permission-broadcast",
    response_model=ExchangeWalletItem,
)
async def post_multisig_permission_broadcast(
    space: str,
    wallet_id: int,
    body: MultisigPermissionBroadcastRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    try:
        updated = await svc.broadcast_multisig_permission_transaction(
            space, wallet_address, wallet_id, body.signed
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return await _to_item_with_tronlink_flag(svc, updated, wallet_address)
