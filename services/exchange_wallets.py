"""
Реквизиты onRamp/offRamp: записи Wallet с role external | multisig и owner_did = DID владельца спейса
(WalletUser.nickname == space → owner.did).
"""
from __future__ import annotations

import logging
from typing import List, Literal, Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from didcomm.crypto import EthCrypto

from repos.wallet import (
    ExchangeRole,
    ExchangeWalletResource,
    WalletRepository,
    WalletResource,
)
from repos.wallet_user import WalletUserRepository
from services.space import SpaceService
from services.tron.utils import is_valid_tron_address
from settings import Settings

logger = logging.getLogger(__name__)

ExchangeBlockchain = Literal["tron"]


class ExchangeWalletService:
    """CRUD реквизитов обмена в разрезе space (только owner спейса)."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = WalletRepository(session=session, redis=redis, settings=settings)
        self._users = WalletUserRepository(session=session, redis=redis, settings=settings)
        self._space = SpaceService(session=session, redis=redis, settings=settings)

    async def _owner_did_for_space(self, space: str) -> str:
        owner = await self._users.get_by_nickname((space or "").strip())
        if not owner:
            raise ValueError("Space not found")
        return owner.did

    async def list_wallets(
        self,
        space: str,
        actor_wallet_address: str,
        role: Optional[ExchangeRole] = None,
    ) -> List[ExchangeWalletResource.Get]:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        return await self._repo.list_exchange_wallets(owner_did, role=role)

    async def get_wallet(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
    ) -> Optional[ExchangeWalletResource.Get]:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        return await self._repo.get_exchange_wallet(wallet_id, owner_did)

    async def _commit_exchange_wallet(
        self,
        space: str,
        actor_wallet_address: str,
        data: WalletResource.Create,
    ) -> ExchangeWalletResource.Get:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        created = await self._repo.create_exchange_wallet(data, owner_did)
        await self._session.commit()
        return created

    async def create_wallet(
        self,
        space: str,
        actor_wallet_address: str,
        *,
        role: ExchangeRole,
        blockchain: ExchangeBlockchain = "tron",
        name: Optional[str] = None,
        tron_address: Optional[str] = None,
        participant_sub_id: Optional[int] = None,
    ) -> ExchangeWalletResource.Get:
        """
        Создать Ramp-кошелёк: multisig (авто-мнемоника), external по sub или произвольному TRON.
        Контракт согласован с валидацией CreateExchangeWalletRequest на роутере.
        """
        owner_wallet_user_id = await self._space._ensure_owner_and_owner_id(
            space, actor_wallet_address
        )
        owner_did = await self._owner_did_for_space(space)

        if role == "multisig":
            nm = (name or "").strip()
            if not nm:
                raise ValueError("name is required for multisig")
            if await self._repo.exists_exchange_wallet_with_name(owner_did, nm):
                raise ValueError("Wallet name already exists")
            mnemonic = EthCrypto.generate_mnemonic(strength=128)
            normalized = " ".join(mnemonic.split())
            enc = self._repo.encrypt_data(normalized)
            data = WalletResource.Create(
                name=nm,
                role="multisig",
                encrypted_mnemonic=enc,
                tron_address=None,
                ethereum_address=None,
                owner_did=None,
            )
            return await self._commit_exchange_wallet(
                space, actor_wallet_address, data
            )

        # external
        if participant_sub_id is not None:
            sub = await self._users.get_sub(
                owner_wallet_user_id, participant_sub_id
            )
            if not sub:
                raise ValueError("Participant not found")
            if sub.blockchain.strip().lower() != blockchain:
                raise ValueError("Participant blockchain does not match")
            tron = sub.wallet_address.strip()
            if not is_valid_tron_address(tron):
                raise ValueError("Invalid TRON address")
            if await self._repo.exists_exchange_wallet_with_tron(owner_did, tron):
                raise ValueError("This address is already a Ramp wallet")
            display_name = (sub.nickname or "").strip() or tron
            if await self._repo.exists_exchange_wallet_with_name(
                owner_did, display_name
            ):
                raise ValueError("Wallet name already exists")
            data = WalletResource.Create(
                name=display_name,
                role="external",
                encrypted_mnemonic=None,
                tron_address=tron,
                ethereum_address=None,
                owner_did=None,
            )
            return await self._commit_exchange_wallet(
                space, actor_wallet_address, data
            )

        nm = (name or "").strip()
        tr = (tron_address or "").strip()
        if not nm:
            raise ValueError("name is required for external wallet with custom address")
        if not tr:
            raise ValueError(
                "tron_address is required for external wallet without participant_sub_id",
            )
        if not is_valid_tron_address(tr):
            raise ValueError("Invalid TRON address")
        if await self._repo.exists_exchange_wallet_with_name(owner_did, nm):
            raise ValueError("Wallet name already exists")
        if await self._repo.exists_exchange_wallet_with_tron(owner_did, tr):
            raise ValueError("This address is already a Ramp wallet")
        data = WalletResource.Create(
            name=nm,
            role="external",
            encrypted_mnemonic=None,
            tron_address=tr,
            ethereum_address=None,
            owner_did=None,
        )
        return await self._commit_exchange_wallet(space, actor_wallet_address, data)

    async def create_wallet_with_plain_mnemonic(
        self,
        space: str,
        actor_wallet_address: str,
        *,
        name: str,
        role: ExchangeRole,
        tron_address: str,
        ethereum_address: str,
        mnemonic: Optional[str] = None,
    ) -> ExchangeWalletResource.Get:
        """Создание из формы API: мнемоника опционально шифруется (для multisig обязательна через валидацию Create)."""
        enc: Optional[str] = None
        if mnemonic and mnemonic.strip():
            enc = self._repo.encrypt_data(" ".join(mnemonic.split()))
        if role == "multisig":
            data = WalletResource.Create(
                name=name.strip(),
                role=role,
                encrypted_mnemonic=enc,
                tron_address=None,
                ethereum_address=None,
                owner_did=None,
            )
        else:
            ts = (tron_address or "").strip() or None
            es = (ethereum_address or "").strip() or None
            data = WalletResource.Create(
                name=name.strip(),
                role=role,
                encrypted_mnemonic=enc,
                tron_address=ts,
                ethereum_address=es,
                owner_did=None,
            )
        return await self._commit_exchange_wallet(space, actor_wallet_address, data)

    async def patch_wallet(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
        data: WalletResource.Patch,
    ) -> Optional[ExchangeWalletResource.Get]:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        updated = await self._repo.patch_exchange_wallet(wallet_id, owner_did, data)
        if updated:
            await self._session.commit()
        return updated

    async def patch_wallet_with_plain_fields(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
        *,
        name: Optional[str] = None,
        tron_address: Optional[str] = None,
        ethereum_address: Optional[str] = None,
        mnemonic: Optional[str] = None,
    ) -> Optional[ExchangeWalletResource.Get]:
        """PATCH из API: опционально перешифровать мнемонику; пустая строка — сброс (только с role=external в Patch)."""
        payload: dict = {}
        if name is not None:
            payload["name"] = name.strip()
        if tron_address is not None:
            payload["tron_address"] = tron_address.strip()
        if ethereum_address is not None:
            payload["ethereum_address"] = ethereum_address.strip()
        if mnemonic is not None:
            if mnemonic.strip():
                payload["encrypted_mnemonic"] = self._repo.encrypt_data(
                    " ".join(mnemonic.split())
                )
            else:
                payload["encrypted_mnemonic"] = None
                payload["role"] = "external"
        if not payload:
            return await self.get_wallet(space, actor_wallet_address, wallet_id)
        data = WalletResource.Patch(**payload)
        return await self.patch_wallet(space, actor_wallet_address, wallet_id, data)

    async def delete_wallet(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
    ) -> bool:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        ok = await self._repo.delete_exchange_wallet(wallet_id, owner_did)
        if ok:
            await self._session.commit()
        return ok
