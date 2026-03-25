"""
Балансы залоговых стейблкоинов по Ramp-кошелькам спейса (Wallet external|multisig).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from services.balances import collateral_contract_addresses_for_network
from services.exchange_wallets import normalize_balance_blockchain
from services.wallet_user import WalletUserService
from web.endpoints.dependencies import (
    AppSettings,
    BalancesServiceDep,
    ExchangeWalletServiceDep,
    WalletUserServiceDep,
    get_required_wallet_address_for_space,
)
from web.endpoints.v1.schemas.space_balances import (
    SpaceBalancesQueryRequest,
    SpaceBalancesQueryResponse,
    SpaceBalanceItemResult,
)

router = APIRouter(prefix="/spaces", tags=["space-balances"])


async def _ensure_actor_can_use_space(
    wallet_user_service: WalletUserService,
    actor_wallet_address: str,
    space: str,
) -> None:
    key = (space or "").strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid space",
        )
    for bc in ("tron", "ethereum"):
        allowed = await wallet_user_service.get_spaces_for_address(
            actor_wallet_address, bc
        )
        if key in allowed:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No access to this space",
    )


@router.post(
    "/{space}/balances",
    response_model=SpaceBalancesQueryResponse,
    summary="Балансы по адресам Ramp-кошельков спейса",
)
async def query_space_token_balances(
    space: str,
    body: SpaceBalancesQueryRequest,
    wallet_user_service: WalletUserServiceDep,
    exchange_svc: ExchangeWalletServiceDep,
    balances_svc: BalancesServiceDep,
    settings: AppSettings,
    wallet_address: str = Depends(get_required_wallet_address_for_space),
):
    """
    JWT (TRON/Web3) или cookie ``main_auth_token``. Адрес из тела должен быть
    в списке реквизитов спейса (Wallet с owner DID владельца спейса).

    Возвращает ``balances_raw`` для контрактов из ``collateral_stablecoin.tokens``
    выбранной сети. ETH пока не реализован (поле ``error``).
    """
    await _ensure_actor_can_use_space(wallet_user_service, wallet_address, space)

    tron_refresh: list[str] = []
    tron_cached: list[str] = []
    ordered: list[tuple[str, str, bool]] = []

    for it in body.items:
        chain_norm = normalize_balance_blockchain(it.blockchain)
        if chain_norm is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported blockchain: {it.blockchain!r}",
            )
        addr = (it.address or "").strip()
        if not addr:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty address",
            )
        if not await exchange_svc.is_ramp_wallet_address(
            space,
            address=addr,
            blockchain=it.blockchain,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "address_not_in_space_wallets",
                    "address": addr,
                    "blockchain": it.blockchain,
                },
            )
        ordered.append((addr, chain_norm, it.force_update))
        if chain_norm == "TRON":
            if it.force_update:
                tron_refresh.append(addr)
            else:
                tron_cached.append(addr)

    force_set = set(tron_refresh)
    tron_cached = [a for a in tron_cached if a not in force_set]

    contracts = collateral_contract_addresses_for_network(
        settings.settings,
        network_label="TRON",
    )
    tron_results: dict[str, dict[str, int]] = {}
    if contracts:
        if tron_refresh:
            tron_results.update(
                await balances_svc.list_tron_trc20_balances_raw(
                    tron_refresh,
                    contracts,
                    refresh_cache=True,
                )
            )
        if tron_cached:
            tron_results.update(
                await balances_svc.list_tron_trc20_balances_raw(
                    tron_cached,
                    contracts,
                    refresh_cache=False,
                )
            )

    out_items: list[SpaceBalanceItemResult] = []
    for addr, chain_norm, _force in ordered:
        if chain_norm == "TRON":
            raw = tron_results.get(addr, {})
            out_items.append(
                SpaceBalanceItemResult(
                    address=addr,
                    blockchain=chain_norm,
                    balances_raw={k: str(v) for k, v in raw.items()},
                )
            )
        else:
            out_items.append(
                SpaceBalanceItemResult(
                    address=addr,
                    blockchain=chain_norm,
                    balances_raw={},
                    error="eth_balances_not_implemented",
                )
            )

    return SpaceBalancesQueryResponse(items=out_items)
