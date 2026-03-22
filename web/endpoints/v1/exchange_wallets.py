"""
Реквизиты Ramp: Wallet с role external | multisig в разрезе space (только owner).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.exceptions import SpacePermissionDenied
from repos.wallet import ExchangeWalletResource
from services.exchange_wallets import ExchangeWalletService
from web.endpoints.dependencies import (
    get_exchange_wallet_service,
    get_required_wallet_address_for_space,
)
from web.endpoints.v1.schemas.exchange_wallets import (
    CreateExchangeWalletRequest,
    ExchangeWalletItem,
    ExchangeWalletListResponse,
    PatchExchangeWalletRequest,
)

router = APIRouter(prefix="/spaces", tags=["exchange-wallets"])


def _to_item(row: ExchangeWalletResource.Get) -> ExchangeWalletItem:
    r = row.role if row.role in ("external", "multisig") else "external"
    return ExchangeWalletItem(
        id=row.id,
        name=row.name,
        tron_address=row.tron_address,
        ethereum_address=row.ethereum_address,
        role=r,  # type: ignore[arg-type]
        owner_did=row.owner_did,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


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
    return ExchangeWalletListResponse(items=[_to_item(x) for x in rows])


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
        created = await svc.create_wallet_with_plain_mnemonic(
            space,
            wallet_address,
            name=body.name,
            role=body.role,
            tron_address=body.tron_address,
            ethereum_address=body.ethereum_address,
            mnemonic=body.mnemonic,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return _to_item(created)


@router.patch("/{space}/exchange-wallets/{wallet_id}", response_model=ExchangeWalletItem)
async def patch_exchange_wallet(
    space: str,
    wallet_id: int,
    body: PatchExchangeWalletRequest,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    raw = body.model_dump(exclude_unset=True)
    kwargs = {}
    for key in ("name", "tron_address", "ethereum_address", "mnemonic"):
        if key in raw:
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
    return _to_item(updated)


@router.delete("/{space}/exchange-wallets/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exchange_wallet(
    space: str,
    wallet_id: int,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
    svc: ExchangeWalletService = Depends(get_exchange_wallet_service),
):
    try:
        ok = await svc.delete_wallet(space, wallet_address, wallet_id)
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
