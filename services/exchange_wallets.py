"""
Реквизиты onRamp/offRamp: записи Wallet с role external | multisig и owner_did = DID владельца спейса
(WalletUser.nickname == space → owner.did).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

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
from services.multisig_wallet.chain_config import (
    chain_config_matches_submission,
    chain_snapshots_equal,
    extract_chain_multisig_config,
    meta_multisig_snapshot,
)
from services.multisig_wallet.constants import (
    MULTISIG_STATUS_ACTIVE,
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_FAILED,
    MULTISIG_STATUS_PERMISSIONS_SUBMITTED,
    MULTISIG_STATUS_READY_FOR_PERMISSIONS,
    MULTISIG_STATUS_RECONFIGURE,
)
from services.multisig_wallet.maintenance import MultisigWalletMaintenanceService
from services.multisig_wallet.meta import merge_meta, validate_actors_threshold
from services.notify import NotifyService, RampNotifyEvent
from services.space import SpaceService
from services.tron.grid_client import TronGridClient
from services.tron.utils import account_permissions_snapshot, is_valid_tron_address
from settings import Settings

logger = logging.getLogger(__name__)

ExchangeBlockchain = Literal["tron"]

BalanceChain = Literal["TRON", "ETH"]


def normalize_balance_blockchain(blockchain: str) -> Optional[BalanceChain]:
    """Нормализация имени сети для запросов баланса (как в token_balance_cache.blockchain)."""
    b = (blockchain or "").strip().upper()
    if b == "TRON":
        return "TRON"
    if b in ("ETH", "ETHEREUM"):
        return "ETH"
    return None


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

    async def _notify_owners_event(
        self, space: str, event: str, payload: Dict[str, Any]
    ) -> None:
        try:
            ns = NotifyService(self._session, self._redis, self._settings)
            await ns.notify_roles_event((space or "").strip(), ["owner"], event, payload)
        except Exception:
            logger.exception(
                "Ramp notify failed: event=%s space=%s payload_keys=%s",
                event,
                space,
                list(payload.keys()),
            )

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
        if data.role in ("external", "multisig"):
            await self._notify_owners_event(
                space,
                RampNotifyEvent.RAMP_WALLET_CREATED,
                {
                    "wallet_name": created.name,
                    "wallet_id": created.id,
                    "role": created.role,
                    "tron_address": (created.tron_address or "").strip(),
                },
            )
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
        existing = await self._repo.get_exchange_wallet(wallet_id, owner_did)
        if not existing:
            return False
        ok = await self._repo.delete_exchange_wallet(wallet_id, owner_did)
        if ok:
            await self._session.commit()
            await self._notify_owners_event(
                space,
                RampNotifyEvent.RAMP_WALLET_DELETED,
                {
                    "wallet_name": existing.name,
                    "wallet_id": existing.id,
                    "role": existing.role,
                    "tron_address": (existing.tron_address or "").strip(),
                },
            )
        return ok

    async def is_ramp_wallet_address(
        self,
        space: str,
        *,
        address: str,
        blockchain: str,
    ) -> bool:
        """
        True, если (address, сеть) совпадает с одной из записей Wallet спейса
        (role external|multisig, owner_did владельца спейса).
        """
        try:
            owner_did = await self._owner_did_for_space(space)
        except ValueError:
            return False
        chain = normalize_balance_blockchain(blockchain)
        if chain is None:
            return False
        return await self._repo.exchange_wallet_has_address(
            owner_did,
            address=address,
            chain=chain,
        )

    async def patch_multisig_setup(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
        *,
        multisig_actors: Optional[List[str]] = None,
        multisig_threshold_n: Optional[int] = None,
        multisig_threshold_m: Optional[int] = None,
        multisig_retry: Optional[bool] = None,
        multisig_min_trx_sun: Optional[int] = None,
        multisig_permission_name: Optional[str] = None,
        multisig_begin_reconfigure: Optional[bool] = None,
        multisig_cancel_reconfigure: Optional[bool] = None,
    ) -> Optional[ExchangeWalletResource.Get]:
        """PATCH полей настройки Ramp multisig (только owner спейса)."""
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        model = await self._repo.get_exchange_wallet_model(wallet_id, owner_did)
        if model is None:
            return None
        if model.role != "multisig":
            raise ValueError("Not a multisig wallet")
        if model.multisig_setup_status is None:
            raise ValueError("Legacy multisig wallet has no setup flow in the app")

        if multisig_cancel_reconfigure is True:
            meta = dict(merge_meta(model.multisig_setup_meta, {}))
            prev = meta.get("reconfigure_previous_status")
            st = model.multisig_setup_status
            allowed_prev = (MULTISIG_STATUS_ACTIVE, MULTISIG_STATUS_FAILED)
            cancelable_st = (
                MULTISIG_STATUS_RECONFIGURE,
                MULTISIG_STATUS_AWAITING_FUNDING,
                MULTISIG_STATUS_READY_FOR_PERMISSIONS,
                MULTISIG_STATUS_PERMISSIONS_SUBMITTED,
            )
            if prev not in allowed_prev or st not in cancelable_st:
                raise ValueError("Not in cancelable reconfigure flow")
            tr = (model.tron_address or "").strip()
            if not tr:
                raise ValueError("Multisig wallet has no TRON address yet")
            async with TronGridClient(settings=self._settings) as client:
                raw_acc = await client.get_account(tr)
            chain_cfg = extract_chain_multisig_config(raw_acc)
            meta.pop("reconfigure_previous_status", None)
            meta.pop("reconfigure_unchanged", None)
            if chain_cfg:
                meta["actors"] = list(chain_cfg["actors"])
                meta["threshold_n"] = chain_cfg["threshold_n"]
                meta["threshold_m"] = chain_cfg["threshold_m"]
                if chain_cfg.get("permission_name"):
                    meta["permission_name"] = chain_cfg["permission_name"]
            meta["permission_tx_id"] = None
            meta["broadcast_at"] = None
            meta["last_error"] = None
            meta["retry_desired"] = False
            model.multisig_setup_status = prev
            model.multisig_setup_meta = merge_meta(meta, {})
            model.account_permissions = account_permissions_snapshot(raw_acc)
            await self._session.commit()
            return await self.get_wallet(space, actor_wallet_address, wallet_id)

        if multisig_begin_reconfigure is True:
            if model.multisig_setup_status not in (
                MULTISIG_STATUS_ACTIVE,
                MULTISIG_STATUS_FAILED,
            ):
                raise ValueError(
                    "Reconfigure is only allowed from active or failed status",
                )
            meta = merge_meta(
                model.multisig_setup_meta,
                {
                    "reconfigure_previous_status": model.multisig_setup_status,
                },
            )
            meta.pop("reconfigure_unchanged", None)
            model.multisig_setup_status = MULTISIG_STATUS_RECONFIGURE
            model.multisig_setup_meta = meta
            await self._session.commit()
            return await self.get_wallet(space, actor_wallet_address, wallet_id)

        if model.multisig_setup_status == MULTISIG_STATUS_ACTIVE:
            raise ValueError("Multisig wallet is already active")

        meta = merge_meta(model.multisig_setup_meta, {})
        touched = False

        if multisig_min_trx_sun is not None:
            meta["min_trx_sun"] = int(multisig_min_trx_sun)
            touched = True
        if multisig_permission_name is not None:
            pn = (multisig_permission_name or "").strip()[:32]
            if pn:
                meta["permission_name"] = pn
                touched = True
        if multisig_retry is True:
            meta["retry_desired"] = True
            touched = True

        if multisig_actors is not None:
            if multisig_threshold_n is None or multisig_threshold_m is None:
                raise ValueError(
                    "multisig_threshold_n and multisig_threshold_m are required with multisig_actors",
                )
            tr = (model.tron_address or "").strip()
            if not tr:
                raise ValueError("Multisig wallet has no TRON address yet")
            validate_actors_threshold(
                list(multisig_actors),
                int(multisig_threshold_n),
                int(multisig_threshold_m),
                main_tron_address=tr,
            )
            meta = merge_meta(model.multisig_setup_meta, {})
            submitted = [a.strip() for a in multisig_actors]
            sn = int(multisig_threshold_n)
            sm = int(multisig_threshold_m)

            if model.multisig_setup_status == MULTISIG_STATUS_RECONFIGURE:
                async with TronGridClient(settings=self._settings) as client:
                    raw_acc = await client.get_account(tr)
                chain_cfg = extract_chain_multisig_config(raw_acc)
                db_snap = meta_multisig_snapshot(meta)
                chain_core = (
                    {k: chain_cfg[k] for k in ("actors", "threshold_n", "threshold_m")}
                    if chain_cfg
                    else None
                )
                if chain_cfg and db_snap and chain_core and not chain_snapshots_equal(
                    db_snap, chain_core
                ):
                    logger.critical(
                        "multisig reconfigure wallet_id=%s DB meta != TRON chain; "
                        "overwriting meta from chain. db=%s chain=%s",
                        wallet_id,
                        db_snap,
                        chain_core,
                    )
                    meta["actors"] = list(chain_cfg["actors"])
                    meta["threshold_n"] = chain_cfg["threshold_n"]
                    meta["threshold_m"] = chain_cfg["threshold_m"]
                    if chain_cfg.get("permission_name"):
                        meta["permission_name"] = chain_cfg["permission_name"]
                    model.multisig_setup_meta = merge_meta(meta, {})
                    meta = merge_meta(model.multisig_setup_meta, {})

                pnm = (meta.get("permission_name") or "").strip()
                if chain_cfg and chain_config_matches_submission(
                    chain_cfg, submitted, sn, sm, permission_name=pnm or None
                ):
                    meta.pop("reconfigure_previous_status", None)
                    meta["reconfigure_unchanged"] = True
                    meta["actors"] = submitted
                    meta["threshold_n"] = sn
                    meta["threshold_m"] = sm
                    meta.pop("permission_tx_id", None)
                    meta.pop("broadcast_at", None)
                    meta["last_error"] = None
                    meta["retry_desired"] = False
                    model.multisig_setup_status = MULTISIG_STATUS_ACTIVE
                    model.multisig_setup_meta = merge_meta(meta, {})
                    model.account_permissions = account_permissions_snapshot(raw_acc)
                    await self._session.commit()
                    await self._notify_owners_event(
                        space,
                        RampNotifyEvent.MULTISIG_RECONFIGURED_NOOP,
                        {
                            "wallet_name": model.name,
                            "wallet_id": model.id,
                            "role": model.role or "multisig",
                            "tron_address": tr,
                        },
                    )
                    return await self.get_wallet(space, actor_wallet_address, wallet_id)

                if chain_cfg is None:
                    logger.warning(
                        "multisig reconfigure wallet_id=%s: no custom multisig on chain",
                        wallet_id,
                    )
                meta.pop("reconfigure_unchanged", None)
                meta["actors"] = submitted
                meta["threshold_n"] = sn
                meta["threshold_m"] = sm
                meta["permission_tx_id"] = None
                meta["broadcast_at"] = None
                meta["last_error"] = None
                meta["retry_desired"] = False
                model.multisig_setup_status = MULTISIG_STATUS_AWAITING_FUNDING
                meta = merge_meta(meta, {})
                model.multisig_setup_meta = meta
                touched = True
            else:
                meta["actors"] = submitted
                meta["threshold_n"] = sn
                meta["threshold_m"] = sm
                meta["permission_tx_id"] = None
                meta["broadcast_at"] = None
                meta["last_error"] = None
                meta["retry_desired"] = False
                model.multisig_setup_status = MULTISIG_STATUS_AWAITING_FUNDING
                model.multisig_setup_meta = meta
                touched = True

        if not touched:
            return await self.get_wallet(space, actor_wallet_address, wallet_id)

        model.multisig_setup_meta = meta
        await self._session.commit()
        return await self.get_wallet(space, actor_wallet_address, wallet_id)

    async def refresh_multisig_maintenance(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
    ) -> Optional[ExchangeWalletResource.Get]:
        """Немедленный прогон state machine для multisig (баланс, broadcast, проверка tx)."""
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        ms = MultisigWalletMaintenanceService(
            self._session, self._redis, self._settings
        )
        changed = await ms.process_wallet_by_id(
            wallet_id, owner_did, force_balance_refresh=True
        )
        if changed:
            await self._session.commit()
        return await self.get_wallet(space, actor_wallet_address, wallet_id)
