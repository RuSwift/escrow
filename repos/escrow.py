"""Репозиторий EscrowModel — поиск и создание мультисиг-эскроу для сделок."""

from __future__ import annotations

from typing import Any, Dict, Optional

from redis.asyncio import Redis
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import EscrowModel
from repos.base import BaseRepository
from settings import Settings


class EscrowRepository(BaseRepository):
    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        super().__init__(session=session, redis=redis, settings=settings)

    async def find_active_for_participants(
        self,
        *,
        sender_addr: str,
        receiver_addr: str,
        arbiter_addr: str,
        blockchain: str = "tron",
        network: str = "mainnet",
    ) -> Optional[EscrowModel]:
        """Найти последний активный/ожидающий EscrowModel для тройки участников.

        Порядок sender/receiver не важен — поиск симметричен.
        Возвращает None если активного эскроу нет.
        """
        excluded = ("inactive", "failed")
        stmt = (
            select(EscrowModel)
            .where(
                EscrowModel.blockchain == blockchain,
                EscrowModel.network == network,
                EscrowModel.arbiter_address == arbiter_addr,
                EscrowModel.status.notin_(excluded),
                or_(
                    and_(
                        EscrowModel.participant1_address == sender_addr,
                        EscrowModel.participant2_address == receiver_addr,
                    ),
                    and_(
                        EscrowModel.participant1_address == receiver_addr,
                        EscrowModel.participant2_address == sender_addr,
                    ),
                ),
            )
            .order_by(EscrowModel.id.desc())
            .limit(1)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_deal_escrow(
        self,
        *,
        sender_addr: str,
        receiver_addr: str,
        arbiter_addr: str,
        escrow_address: str,
        encrypted_mnemonic: str,
        owner_did: str,
        blockchain: str = "tron",
        network: str = "mainnet",
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> EscrowModel:
        """Создать новый EscrowModel для сделки со статусом awaiting_funding."""
        multisig_config: Dict[str, Any] = {
            "actors": [sender_addr, receiver_addr, arbiter_addr],
            "threshold_n": 2,
            "threshold_m": 3,
        }
        if extra_config:
            multisig_config.update(extra_config)

        address_roles = {
            sender_addr: "participant",
            receiver_addr: "participant",
            arbiter_addr: "arbiter",
        }
        escrow = EscrowModel(
            blockchain=blockchain,
            network=network,
            escrow_type="multisig",
            escrow_address=escrow_address,
            owner_did=owner_did,
            participant1_address=sender_addr,
            participant2_address=receiver_addr,
            arbiter_address=arbiter_addr,
            multisig_config=multisig_config,
            address_roles=address_roles,
            encrypted_mnemonic=encrypted_mnemonic,
            status="awaiting_funding",
        )
        self._session.add(escrow)
        await self._session.flush()
        await self._session.refresh(escrow)
        return escrow

    async def get_by_id(self, escrow_id: int) -> Optional[EscrowModel]:
        res = await self._session.execute(
            select(EscrowModel).where(EscrowModel.id == escrow_id).limit(1)
        )
        return res.scalar_one_or_none()
