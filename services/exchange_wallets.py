"""
Реквизиты onRamp/offRamp: записи Wallet с role external | multisig и owner_did = DID владельца спейса
(WalletUser.nickname == space → owner.did).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from didcomm.crypto import EthCrypto

from core.exceptions import SpacePermissionDenied

from repos.exchange_service import ExchangeServiceRepository
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
    MULTISIG_DEFAULT_PERMISSION_NAME,
    MULTISIG_STATUS_ACTIVE,
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_FAILED,
    MULTISIG_STATUS_PERMISSIONS_SUBMITTED,
    MULTISIG_STATUS_READY_FOR_PERMISSIONS,
    MULTISIG_STATUS_RECONFIGURE,
)
from services.multisig_wallet.maintenance import MultisigWalletMaintenanceService
from services.multisig_wallet.meta import (
    merge_meta,
    validate_actors_threshold,
    validate_owners_list,
)
from services.balances import BalancesService, collateral_contract_addresses_for_network
from services.notify import NotifyService, RampNotifyEvent
from services.ratios.cache import RatioCacheAdapter
from services.ratios.forex import ForexEngine
from services.space import SpaceService
from services.tron.grid_client import TronGridClient
from services.tron.utils import account_permissions_snapshot, is_valid_tron_address
from settings import Settings

logger = logging.getLogger(__name__)

ExchangeBlockchain = Literal["tron"]

BalanceChain = Literal["TRON", "ETH"]

# Лимиты перед удалением multisig (корпоративный кошелёк)
MULTISIG_DELETE_MAX_STABLE_USD = 5.0
MULTISIG_DELETE_MAX_TRX_SUN = 10 * 1_000_000


class MultisigDeleteBlockedError(Exception):
    """Нельзя удалить multisig: остаток стейблов (экв. USD) или TRX выше порога."""

    def __init__(self, code: str, **extra: Any):
        self.code = code
        self.extra = extra
        super().__init__(code)


class RampWalletDeleteBlockedError(Exception):
    """Нельзя удалить корп. кошелёк: используется в направлениях offRamp."""

    def __init__(self, code: str, **extra: Any):
        self.code = code
        self.extra = extra
        super().__init__(code)


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
        self._exchange_services = ExchangeServiceRepository(
            session=session, redis=redis, settings=settings
        )
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
        await self._space.ensure_owner_or_operator(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        return await self._repo.list_exchange_wallets(owner_did, role=role)

    async def get_wallet(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
    ) -> Optional[ExchangeWalletResource.Get]:
        await self._space.ensure_owner_or_operator(space, actor_wallet_address)
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

    async def _assert_multisig_balances_allow_delete(self, tron_address: str) -> None:
        """
        USDT + A7A5 в эквиваленте USD (A7A5 → USD через Forex USD/RUB).
        TRX — не более 10 TRX (нативный баланс в SUN).
        """
        addr = (tron_address or "").strip()
        if not addr:
            return

        balances_svc = BalancesService(self._session, self._redis, self._settings)
        contracts = collateral_contract_addresses_for_network(
            self._settings, network_label="TRON"
        )
        if not contracts:
            return

        trc20_map = await balances_svc.list_tron_trc20_balances_raw(
            [addr], contracts, refresh_cache=True
        )
        native_map = await balances_svc.list_tron_native_trx_balances_raw(
            [addr], refresh_cache=True
        )
        raw_by_contract = trc20_map.get(addr, {})
        trx_sun = int(native_map.get(addr, 0))

        rub_to_usd: Optional[float] = None
        total_usd = 0.0

        for t in self._settings.collateral_stablecoin.tokens:
            if (t.network or "").strip().upper() != "TRON":
                continue
            sym = (t.symbol or "").strip().upper()
            if sym not in ("USDT", "A7A5"):
                continue
            c = (t.contract_address or "").strip()
            if not c:
                continue
            raw = int(raw_by_contract.get(c, 0))
            dec = int(t.decimals) if t.decimals is not None else 6
            human = raw / (10**dec)
            base = (t.base_currency or "").strip().upper()
            if base == "USD":
                total_usd += human
            elif base == "RUB":
                if rub_to_usd is None:
                    cache = RatioCacheAdapter(self._redis, "ForexEngine")
                    forex = ForexEngine(
                        cache, self._settings.ratios.forex, refresh_cache=False
                    )
                    pair = await forex.ratio("USD", "RUB")
                    if pair is None:
                        raise MultisigDeleteBlockedError("forex_unavailable")
                    # 1 USD = pair.ratio RUB → 1 RUB = 1/pair.ratio USD
                    rub_to_usd = 1.0 / float(pair.ratio)
                total_usd += human * rub_to_usd
            else:
                continue

        if total_usd > MULTISIG_DELETE_MAX_STABLE_USD + 1e-9:
            raise MultisigDeleteBlockedError(
                "stable_balance_too_high",
                total_usd_approx=round(total_usd, 4),
            )
        if trx_sun > MULTISIG_DELETE_MAX_TRX_SUN:
            raise MultisigDeleteBlockedError("trx_balance_too_high", trx_sun=trx_sun)

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
        titles = await self._exchange_services.list_titles_for_space_wallet(
            space, wallet_id
        )
        if titles:
            raise RampWalletDeleteBlockedError(
                "used_by_exchange_services",
                direction_titles=titles,
            )
        if (existing.role or "") == "multisig":
            tron = (existing.tron_address or "").strip()
            if tron:
                await self._assert_multisig_balances_allow_delete(tron)
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
        multisig_owners: Optional[List[str]] = None,
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

        if multisig_owners is not None:
            cleaned = validate_owners_list(list(multisig_owners))
            meta["owners"] = cleaned
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
            meta = merge_meta(meta, {})
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

    async def _ensure_actor_is_tron_owner_key_for_wallet(
        self,
        actor_wallet_address: str,
        row: ExchangeWalletResource.Get,
    ) -> None:
        """Только ключи из list_tron_owner_addresses (родитель + субы owner на TRON)."""
        odid = (row.owner_did or "").strip()
        if not odid:
            raise ValueError("Wallet has no owner")
        wu = await self._users.get_by_did(odid)
        if not wu:
            raise ValueError("Wallet owner not found")
        addrs = await self._users.list_tron_owner_addresses_for_wallet_user(wu.id)
        want = (actor_wallet_address or "").strip()
        if want not in {a.strip() for a in addrs}:
            raise SpacePermissionDenied(
                "Only a TRON space owner key can sign this multisig permission update"
            )

    async def multisig_can_sign_permission_tronlink(
        self,
        row: ExchangeWalletResource.Get,
        viewer_wallet_address: str,
    ) -> bool:
        meta = row.multisig_setup_meta or {}
        if row.role != "multisig":
            return False
        if not meta.get("permission_sign_via_tronlink"):
            return False
        try:
            await self._ensure_actor_is_tron_owner_key_for_wallet(
                viewer_wallet_address, row
            )
            return True
        except SpacePermissionDenied:
            return False

    async def build_multisig_permission_transaction(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
    ) -> Dict[str, Any]:
        """Unsigned AccountPermissionUpdate для подписи в TronLink (при permission_sign_via_tronlink)."""
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        row = await self.get_wallet(space, actor_wallet_address, wallet_id)
        if row is None:
            raise ValueError("Wallet not found")
        if row.role != "multisig":
            raise ValueError("Not a multisig wallet")
        meta = row.multisig_setup_meta or {}
        if row.multisig_setup_status != MULTISIG_STATUS_READY_FOR_PERMISSIONS:
            raise ValueError("Wallet is not ready for permission update")
        if not meta.get("permission_sign_via_tronlink"):
            raise ValueError("TronLink permission signing is not required for this wallet")
        if (meta.get("permission_tx_id") or "").strip():
            raise ValueError("Permission transaction already submitted")
        actors = meta.get("actors") or []
        tn, tm = meta.get("threshold_n"), meta.get("threshold_m")
        if not actors or tn is None or tm is None:
            raise ValueError("Incomplete multisig configuration")
        tron = (row.tron_address or "").strip()
        if not tron:
            raise ValueError("Missing TRON address")

        await self._ensure_actor_is_tron_owner_key_for_wallet(actor_wallet_address, row)

        wu = await self._users.get_by_did((row.owner_did or "").strip())
        if not wu:
            raise ValueError("Space owner not found")
        owner_tron_addrs = await self._users.list_tron_owner_addresses_for_wallet_user(
            wu.id
        )
        if not owner_tron_addrs:
            raise ValueError("No TRON owner addresses for space")

        perm_name = str(meta.get("permission_name") or MULTISIG_DEFAULT_PERMISSION_NAME)[
            :32
        ]

        async with TronGridClient(settings=self._settings) as client:
            body = TronGridClient.build_permission_body(
                owner_address=tron,
                owner_tron_addresses=owner_tron_addrs,
                actor_addresses=list(actors),
                threshold=int(tn),
                permission_name=perm_name,
            )
            resp = await client.create_permission_update_tx(body)
            tx = TronGridClient._unwrap_tx(resp)
            return {"transaction": tx}

    async def broadcast_multisig_permission_transaction(
        self,
        space: str,
        actor_wallet_address: str,
        wallet_id: int,
        signed: Dict[str, Any],
    ) -> Optional[ExchangeWalletResource.Get]:
        """Broadcast подписанной AccountPermissionUpdate с клиента (TronLink)."""
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        row = await self.get_wallet(space, actor_wallet_address, wallet_id)
        if row is None:
            raise ValueError("Wallet not found")
        if row.role != "multisig":
            raise ValueError("Not a multisig wallet")
        meta = row.multisig_setup_meta or {}
        if row.multisig_setup_status != MULTISIG_STATUS_READY_FOR_PERMISSIONS:
            raise ValueError("Wallet is not ready for permission update")
        if not meta.get("permission_sign_via_tronlink"):
            raise ValueError("TronLink permission signing is not required for this wallet")
        if (meta.get("permission_tx_id") or "").strip():
            raise ValueError("Permission transaction already submitted")

        await self._ensure_actor_is_tron_owner_key_for_wallet(actor_wallet_address, row)

        model = await self._repo.get_exchange_wallet_model(wallet_id, owner_did)
        if model is None:
            raise ValueError("Wallet not found")

        async with TronGridClient(settings=self._settings) as client:
            out = await client.broadcast_transaction(signed)
            if not out.get("result"):
                raise ValueError(
                    str(out.get("message") or out.get("code") or out)[:500]
                )

        txid = str(signed.get("txID") or signed.get("txid") or "").strip()
        if not txid:
            raise ValueError("Signed transaction missing txID")

        meta_m = merge_meta(
            model.multisig_setup_meta or {},
            {
                "permission_tx_id": txid,
                "broadcast_at": datetime.now(timezone.utc).isoformat(),
                "last_error": None,
                "permission_sign_via_tronlink": False,
            },
        )
        model.multisig_setup_meta = meta_m
        model.multisig_setup_status = MULTISIG_STATUS_PERMISSIONS_SUBMITTED
        await self._session.commit()
        return await self.get_wallet(space, actor_wallet_address, wallet_id)
