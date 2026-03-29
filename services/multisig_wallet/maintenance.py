"""Фоновая обработка жизненного цикла Ramp multisig (баланс TRX → AccountPermissionUpdate)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from redis.asyncio import Redis

import db as db_module
from db.models import Wallet
from repos.wallet import WalletRepository
from repos.wallet_user import WalletUserRepository
from services.notify import NotifyService, RampNotifyEvent
from services.balances import BalancesService
from services.multisig_wallet.constants import (
    MULTISIG_DEFAULT_MIN_TRX_SUN,
    MULTISIG_DEFAULT_PERMISSION_NAME,
    MULTISIG_STATUS_ACTIVE,
    MULTISIG_STATUS_AWAITING_FUNDING,
    MULTISIG_STATUS_FAILED,
    MULTISIG_STATUS_PENDING_CONFIG,
    MULTISIG_STATUS_PERMISSIONS_SUBMITTED,
    MULTISIG_STATUS_READY_FOR_PERMISSIONS,
    MULTISIG_STATUS_RECONFIGURE,
)
from services.multisig_wallet.meta import merge_meta, validate_actors_threshold
from services.tron.grid_client import TronGridClient
from services.tron.utils import (
    account_permissions_snapshot,
    is_custom_multisig_active_permission,
    keypair_from_mnemonic,
)
from settings import Settings

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MultisigWalletMaintenanceService:
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
        self._wallet_users = WalletUserRepository(
            session=session, redis=redis, settings=settings
        )

    async def _scope_nickname_for_wallet(self, wallet: Wallet) -> Optional[str]:
        odid = (wallet.owner_did or "").strip()
        if not odid:
            return None
        owner = await self._wallet_users.get_by_did(odid)
        if not owner:
            return None
        nick = (owner.nickname or "").strip()
        return nick or None

    def _ramp_notify_payload(self, wallet: Wallet) -> Dict[str, Any]:
        return {
            "wallet_name": wallet.name,
            "wallet_id": wallet.id,
            "role": wallet.role or "multisig",
            "tron_address": (wallet.tron_address or "").strip(),
        }

    async def _notify_owners_multisig_event(self, wallet: Wallet, event: str) -> None:
        scope = await self._scope_nickname_for_wallet(wallet)
        if not scope:
            logger.warning(
                "multisig notify skipped: no scope for wallet id=%s", wallet.id
            )
            return
        try:
            ns = NotifyService(self._session, self._redis, self._settings)
            await ns.notify_roles_event(
                scope,
                ["owner"],
                event,
                self._ramp_notify_payload(wallet),
            )
        except Exception:
            logger.exception(
                "multisig notify failed wallet id=%s event=%s", wallet.id, event
            )

    async def _list_tron_native_trx_balances_isolated(
        self,
        wallet_addresses: list[str],
        *,
        refresh_cache: bool,
    ) -> dict[str, int]:
        """
        Баланс TRX через отдельную сессию БД: upsert кеша балансов делает commit,
        его нельзя смешивать с begin()/begin_nested() в process_batch.
        """
        session_factory = db_module.SessionLocal
        if session_factory is None:
            raise RuntimeError("Database not initialized (SessionLocal is None)")
        async with session_factory() as balance_session:
            svc = BalancesService(
                session=balance_session,
                redis=self._redis,
                settings=self._settings,
            )
            return await svc.list_tron_native_trx_balances_raw(
                wallet_addresses,
                refresh_cache=refresh_cache,
            )

    async def process_batch(self, batch_size: int = 5) -> int:
        """
        Обработать батч незавершённых multisig с лочением строк:
        SELECT ... FOR UPDATE SKIP LOCKED.

        Это позволяет безопасно запускать несколько воркеров cron параллельно.
        Возвращает число кошельков, у которых были изменения.
        """
        limit = max(1, int(batch_size))
        stmt = (
            select(Wallet)
            .where(Wallet.role == "multisig")
            .where(Wallet.multisig_setup_status.isnot(None))
            .where(Wallet.multisig_setup_status != MULTISIG_STATUS_ACTIVE)
            .order_by(Wallet.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        processed = 0
        async with self._session.begin():
            res = await self._session.execute(stmt)
            rows = list(res.scalars().all())
            for row in rows:
                wid = row.id
                try:
                    async with self._session.begin_nested():
                        current = await self._session.get(
                            Wallet, wid, populate_existing=True
                        )
                        if current is None:
                            continue
                        changed = await self.process_wallet(current)
                        if changed:
                            processed += 1
                except Exception:
                    logger.exception("multisig maintenance failed for wallet id=%s", wid)
        return processed

    async def process_wallet(self, wallet: Wallet, *, force_balance_refresh: bool = True) -> bool:
        """
        Один проход по state machine. Возвращает True, если были изменения ORM (нужен commit снаружи).

        Все обращения к TronGrid делаются внутри одного TronGridClient-сеанса
        (один aiohttp.ClientSession), что минимизирует накладные расходы на соединение.
        """
        st = wallet.multisig_setup_status
        if st is None or st == MULTISIG_STATUS_ACTIVE:
            return False
        if st == MULTISIG_STATUS_RECONFIGURE:
            return False
        if st == MULTISIG_STATUS_PENDING_CONFIG:
            return False
        if st == MULTISIG_STATUS_FAILED:
            meta = wallet.multisig_setup_meta or {}
            if not meta.get("retry_desired"):
                return False
            # сброс retry флага и повтор с проверки баланса
            wallet.multisig_setup_meta = merge_meta(
                meta,
                {
                    "retry_desired": False,
                    "last_error": None,
                },
            )
            wallet.multisig_setup_status = MULTISIG_STATUS_AWAITING_FUNDING
            st = wallet.multisig_setup_status

        tron = (wallet.tron_address or "").strip()
        if not tron:
            return False

        async with TronGridClient(settings=self._settings) as client:
            return await self._process_wallet_with_client(
                wallet=wallet,
                tron=tron,
                client=client,
                force_balance_refresh=force_balance_refresh,
            )

    async def _process_wallet_with_client(
        self,
        *,
        wallet: Wallet,
        tron: str,
        client: TronGridClient,
        force_balance_refresh: bool,
    ) -> bool:
        """Внутренняя логика state machine с уже открытым клиентом."""
        st = wallet.multisig_setup_status

        # Уже настроено на цепи (ручной сценарий / внешняя операция)
        try:
            acc = await client.get_account(tron)
            reconfrollback = (wallet.multisig_setup_meta or {}).get(
                "reconfigure_previous_status"
            )
            if (
                wallet.multisig_setup_status != MULTISIG_STATUS_RECONFIGURE
                and not reconfrollback
                and is_custom_multisig_active_permission(acc)
            ):
                wallet.account_permissions = account_permissions_snapshot(acc)
                wallet.multisig_setup_status = MULTISIG_STATUS_ACTIVE
                wallet.multisig_setup_meta = merge_meta(
                    wallet.multisig_setup_meta,
                    {"last_chain_check_at": _utc_iso(), "last_error": None},
                )
                return True
        except Exception as e:
            logger.warning("multisig id=%s chain read: %s", wallet.id, e)

        meta = dict(wallet.multisig_setup_meta or {})
        min_sun = int(meta.get("min_trx_sun") or MULTISIG_DEFAULT_MIN_TRX_SUN)

        if st in (
            MULTISIG_STATUS_AWAITING_FUNDING,
            MULTISIG_STATUS_READY_FOR_PERMISSIONS,
        ):
            try:
                bal = await self._list_tron_native_trx_balances_isolated(
                    [tron],
                    refresh_cache=force_balance_refresh,
                )
                sun = int(bal.get(tron, 0))
            except Exception as e:
                logger.warning("multisig id=%s balance: %s", wallet.id, e)
                return False
            meta = merge_meta(
                meta,
                {"last_trx_balance_sun": sun, "last_chain_check_at": _utc_iso()},
            )
            wallet.multisig_setup_meta = meta
            if sun < min_sun:
                wallet.multisig_setup_status = MULTISIG_STATUS_AWAITING_FUNDING
                return True
            wallet.multisig_setup_status = MULTISIG_STATUS_READY_FOR_PERMISSIONS
            meta = wallet.multisig_setup_meta or {}

        if wallet.multisig_setup_status == MULTISIG_STATUS_READY_FOR_PERMISSIONS:
            tx_existing = (meta.get("permission_tx_id") or "").strip()
            if tx_existing:
                wallet.multisig_setup_status = MULTISIG_STATUS_PERMISSIONS_SUBMITTED
                return True
            actors = meta.get("actors") or []
            tn = meta.get("threshold_n")
            tm = meta.get("threshold_m")
            if not actors or tn is None or tm is None:
                return False
            try:
                validate_actors_threshold(
                    list(actors),
                    int(tn),
                    int(tm),
                    main_tron_address=tron,
                )
            except ValueError as e:
                wallet.multisig_setup_meta = merge_meta(meta, {"last_error": str(e)})
                wallet.multisig_setup_status = MULTISIG_STATUS_FAILED
                return True

            perm_name = str(
                meta.get("permission_name") or MULTISIG_DEFAULT_PERMISSION_NAME
            )[:32]

            # Precheck: оцениваем стоимость tx (+10% margin) и обновляем min_trx_sun
            try:
                estimated_sun = await client.estimate_permission_update_sun(
                    owner_address=tron,
                    actor_addresses=list(actors),
                    threshold=int(tn),
                    permission_name=perm_name,
                    margin=0.10,
                )
            except Exception as e:
                logger.warning("multisig id=%s estimate failed: %s", wallet.id, e)
                estimated_sun = MULTISIG_DEFAULT_MIN_TRX_SUN

            current_sun = int((wallet.multisig_setup_meta or {}).get("last_trx_balance_sun") or 0)
            recalculated_min_sun = max(1, int(estimated_sun))
            wallet.multisig_setup_meta = merge_meta(
                wallet.multisig_setup_meta or {},
                {
                    "min_trx_sun": recalculated_min_sun,
                    "last_chain_check_at": _utc_iso(),
                },
            )
            meta = wallet.multisig_setup_meta or {}
            if current_sun < recalculated_min_sun:
                wallet.multisig_setup_status = MULTISIG_STATUS_AWAITING_FUNDING
                return True

            if not _mnemonic_ok(wallet):
                return False
            plain = self._repo.decrypt_data(wallet.encrypted_mnemonic)
            _addr, pk_hex = keypair_from_mnemonic(plain, account_index=0)
            if _addr != tron:
                wallet.multisig_setup_meta = merge_meta(
                    meta, {"last_error": "mnemonic address mismatch"}
                )
                wallet.multisig_setup_status = MULTISIG_STATUS_FAILED
                return True

            # Broadcast: create → sign → broadcast (все вызовы через один client)
            try:
                txid, bout = await client.permission_update_sign_and_broadcast(
                    owner_address=tron,
                    actor_addresses=list(actors),
                    threshold=int(tn),
                    permission_name=perm_name,
                    owner_private_key_hex=pk_hex,
                )
                if not bout.get("result"):
                    raise RuntimeError(
                        str(bout.get("message") or bout.get("code") or bout)
                    )
            except Exception as e:
                logger.warning("multisig id=%s broadcast failed: %s", wallet.id, e)
                wallet.multisig_setup_meta = merge_meta(
                    meta,
                    {
                        "last_error": str(e)[:500],
                        "last_chain_check_at": _utc_iso(),
                    },
                )
                wallet.multisig_setup_status = MULTISIG_STATUS_FAILED
                return True

            wallet.multisig_setup_meta = merge_meta(
                meta,
                {
                    "permission_tx_id": txid,
                    "broadcast_at": _utc_iso(),
                    "last_error": None,
                },
            )
            wallet.multisig_setup_status = MULTISIG_STATUS_PERMISSIONS_SUBMITTED
            return True

        if wallet.multisig_setup_status == MULTISIG_STATUS_PERMISSIONS_SUBMITTED:
            txid = (meta.get("permission_tx_id") or "").strip()
            if not txid:
                return False
            try:
                ok = await client.get_transaction_success(txid)
            except Exception as e:
                logger.warning("multisig id=%s tx info: %s", wallet.id, e)
                return False
            if ok is None:
                return False
            if ok is False:
                wallet.multisig_setup_meta = merge_meta(
                    wallet.multisig_setup_meta or {},
                    {"last_error": f"transaction failed: {txid}", "last_chain_check_at": _utc_iso()},
                )
                wallet.multisig_setup_status = MULTISIG_STATUS_FAILED
                return True
            try:
                acc = await client.get_account(tron)
                wallet.account_permissions = account_permissions_snapshot(acc)
            except Exception:
                pass
            pre_meta = dict(wallet.multisig_setup_meta or {})
            had_reconfigure = bool(pre_meta.get("reconfigure_previous_status"))
            was_noop = bool(pre_meta.get("reconfigure_unchanged"))
            wallet.multisig_setup_status = MULTISIG_STATUS_ACTIVE
            meta_done = dict(
                merge_meta(
                    wallet.multisig_setup_meta or {},
                    {"last_error": None, "last_chain_check_at": _utc_iso()},
                )
            )
            meta_done.pop("reconfigure_previous_status", None)
            meta_done.pop("reconfigure_unchanged", None)
            wallet.multisig_setup_meta = meta_done
            if had_reconfigure and was_noop:
                evt = RampNotifyEvent.MULTISIG_RECONFIGURED_NOOP
            elif had_reconfigure:
                evt = RampNotifyEvent.MULTISIG_RECONFIGURED_ACTIVE
            else:
                evt = RampNotifyEvent.MULTISIG_CONFIGURED_ACTIVE
            await self._notify_owners_multisig_event(wallet, evt)
            return True

        return False

    async def process_wallet_by_id(
        self,
        wallet_id: int,
        owner_did: str,
        *,
        force_balance_refresh: bool = True,
    ) -> bool:
        """Один кошелёк по id (проверка owner_did через репозиторий)."""
        w = await self._repo.get_exchange_wallet_model(wallet_id, owner_did)
        if w is None:
            return False
        return await self.process_wallet(w, force_balance_refresh=force_balance_refresh)


def _mnemonic_ok(wallet: Wallet) -> bool:
    return bool((wallet.encrypted_mnemonic or "").strip())
