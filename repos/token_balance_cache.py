"""
Repository для token_balance_cache: последние известные балансы токена по сети.

Используется как fallback при ошибках внешнего API (например TronGrid).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TokenBalanceCache


class TokenBalanceCacheRepository:
    """
    Чтение/запись балансов в base-units (raw uint256).

    Upsert выполняется через «есть ли строка → update/insert», без ON CONFLICT по диалекту.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_balances_raw(
        self,
        *,
        address: str,
        blockchain: str,
        contract_addresses: List[str],
    ) -> Dict[str, Decimal]:
        if not contract_addresses:
            return {}
        stmt = (
            select(TokenBalanceCache)
            .where(TokenBalanceCache.address == address)
            .where(TokenBalanceCache.blockchain == blockchain)
            .where(TokenBalanceCache.contract_address.in_(contract_addresses))
        )
        res = await self._session.execute(stmt)
        rows = res.scalars().all()
        return {r.contract_address: Decimal(r.balance_raw) for r in rows}

    async def upsert_balances_raw(
        self,
        *,
        address: str,
        blockchain: str,
        balances_raw: Dict[str, int],
    ) -> None:
        """
        balances_raw: { contract_address: balance_raw_int }
        """
        if not balances_raw:
            return
        contract_addresses = list(balances_raw.keys())

        existing_stmt = (
            select(TokenBalanceCache)
            .where(TokenBalanceCache.address == address)
            .where(TokenBalanceCache.blockchain == blockchain)
            .where(TokenBalanceCache.contract_address.in_(contract_addresses))
        )
        res = await self._session.execute(existing_stmt)
        existing_rows = res.scalars().all()
        by_contract: Dict[str, TokenBalanceCache] = {
            r.contract_address: r for r in existing_rows
        }

        for contract_address, balance_int in balances_raw.items():
            if contract_address in by_contract:
                row = by_contract[contract_address]
                row.balance_raw = balance_int
            else:
                row = TokenBalanceCache(
                    address=address,
                    blockchain=blockchain,
                    contract_address=contract_address,
                    balance_raw=balance_int,
                )
                self._session.add(row)

        await self._session.flush()
