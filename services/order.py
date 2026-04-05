"""Сервис ордеров дашборда: эфемерные подсказки, заявки на вывод (withdrawal), сделки."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Order as OrderModel
from db.models import Wallet
from repos.order import (
    ORDER_CATEGORY_WITHDRAWAL,
    OrderRepository,
    OrderResource,
    withdrawal_dedupe_key,
)
from repos.wallet_user import WalletUserRepository
from services.multisig_wallet.chain_config import extract_chain_multisig_config
from services.multisig_wallet.constants import (
    SPACE_DRIFT_ELIGIBLE_STATUSES,
    TERMINAL_STATUSES,
)
from services.space import SpaceService
from services.tron.grid_client import TronGridClient
from services.tron.utils import is_valid_tron_address
from settings import Settings

if TYPE_CHECKING:
    from services.exchange_wallets import ExchangeWalletService

logger = logging.getLogger(__name__)

ORDER_KIND_MULTISIG_PIPELINE = "multisig_pipeline"
ORDER_KIND_MULTISIG_SPACE_DRIFT = "multisig_space_drift"

WITHDRAWAL_KIND = "withdrawal_request"

WITHDRAWAL_STATUS_AWAITING_SIGNATURES = "awaiting_signatures"
WITHDRAWAL_STATUS_READY_TO_BROADCAST = "ready_to_broadcast"
WITHDRAWAL_STATUS_BROADCAST_SUBMITTED = "broadcast_submitted"
WITHDRAWAL_STATUS_CONFIRMED = "confirmed"
WITHDRAWAL_STATUS_FAILED = "failed"


def _offchain_times_from_signed_tx(
    signed: Dict[str, Any],
) -> Tuple[Optional[int], Optional[int]]:
    """expiration / timestamp из raw_data Tron (миллисекунды)."""
    raw = signed.get("raw_data")
    if not isinstance(raw, dict):
        return None, None
    exp_ms: Optional[int] = None
    ts_ms: Optional[int] = None
    try:
        ev = raw.get("expiration")
        if ev is not None:
            exp_ms = int(ev)
    except (TypeError, ValueError):
        exp_ms = None
    try:
        tv = raw.get("timestamp")
        if tv is not None:
            ts_ms = int(tv)
    except (TypeError, ValueError):
        ts_ms = None
    return exp_ms, ts_ms


def _best_signed_transaction_from_rows(
    sig_rows: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Транзакция с максимальным числом подписей (как на клиенте)."""
    best: Optional[Dict[str, Any]] = None
    best_len = -1
    for row in sig_rows:
        sd = row.get("signature_data") or {}
        tx = sd.get("signed_transaction")
        if not isinstance(tx, dict):
            continue
        sig = tx.get("signature")
        n = len(sig) if isinstance(sig, list) else 0
        if n > best_len:
            best_len = n
            best = tx
    return best


def _broadcast_error_message(out: Dict[str, Any]) -> str:
    return str(out.get("message") or out.get("code") or out)[:500]


class WithdrawalDeleteForbidden(ValueError):
    """Удаление заявки запрещено после отправки tx в сеть или по завершении."""

    pass


def _dedupe_pipeline(wallet_id: int) -> str:
    return f"ephemeral:multisig_pipeline:{wallet_id}"


def _dedupe_drift(wallet_id: int) -> str:
    return f"ephemeral:multisig_space_drift:{wallet_id}"


class OrderService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._orders = OrderRepository(session=session, redis=redis, settings=settings)
        self._wallet_users = WalletUserRepository(
            session=session, redis=redis, settings=settings
        )
        self._space = SpaceService(session=session, redis=redis, settings=settings)

    async def _owner_did_for_space(self, space: str) -> str:
        owner = await self._wallet_users.get_by_nickname((space or "").strip())
        if not owner:
            raise ValueError("Space not found")
        return owner.did

    async def list_for_space(
        self,
        space: str,
        actor_wallet_address: str,
    ) -> List[OrderResource.Get]:
        await self._space.ensure_actor_in_space(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        ephemeral = await self._orders.list_ephemeral_by_owner_did(owner_did)
        withdrawal = await self._orders.list_withdrawal_by_owner_did(owner_did)
        merged: List[OrderResource.Get] = list(ephemeral) + list(withdrawal)
        merged.sort(key=lambda x: x.updated_at, reverse=True)
        return merged

    async def refresh_ephemeral(self) -> Dict[str, int]:
        """
        Два прохода: вычислить желаемое множество эфемерных ордеров, затем синхронизировать БД.
        multisig_space_drift — только при статусах active | failed (настройка завершена).
        """
        desired: List[OrderResource.EphemeralSync] = []

        stmt = select(Wallet).where(Wallet.role == "multisig")
        res = await self._session.execute(stmt)
        wallets: List[Wallet] = list(res.scalars().all())

        for w in wallets:
            st = w.multisig_setup_status
            if st is not None and st not in TERMINAL_STATUSES:
                desired.append(
                    OrderResource.EphemeralSync(
                        dedupe_key=_dedupe_pipeline(w.id),
                        space_wallet_id=w.id,
                        payload={
                            "kind": ORDER_KIND_MULTISIG_PIPELINE,
                            "wallet_id": w.id,
                            "wallet_name": w.name,
                            "multisig_setup_status": st,
                            "tron_address": (w.tron_address or "").strip() or None,
                        },
                    )
                )

            odid = (w.owner_did or "").strip()
            if not odid:
                continue
            wu = await self._wallet_users.get_by_did(odid)
            if not wu:
                continue
            if st not in SPACE_DRIFT_ELIGIBLE_STATUSES:
                continue
            admin_addrs = await self._wallet_users.list_tron_owner_addresses_for_wallet_user(
                wu.id
            )
            oo_addrs = await self._wallet_users.list_tron_owner_operator_addresses_for_wallet_user(
                wu.id
            )
            admins_set = {a.strip() for a in admin_addrs if (a or "").strip()}
            oo_set = {a.strip() for a in oo_addrs if (a or "").strip()}
            meta = w.multisig_setup_meta or {}
            actors_raw = meta.get("actors") or []
            actors_set: set[str] = set()
            for a in actors_raw:
                if isinstance(a, str) and (a or "").strip():
                    actors_set.add(a.strip())

            owners_drift = False
            owners_set: set[str] = set()
            if "owners" in meta:
                for o in meta.get("owners") or []:
                    if isinstance(o, str) and (o or "").strip():
                        owners_set.add(o.strip())
                owners_drift = owners_set != admins_set

            # Админы: точное совпадение наборов. Actors: достаточно actors ⊆ (owner+operator в спейсе).
            actors_drift = not actors_set.issubset(oo_set)

            if owners_drift or actors_drift:
                owners_only_in_meta: List[str] = []
                owners_only_in_space: List[str] = []
                if owners_drift:
                    owners_only_in_meta = sorted(owners_set - admins_set)
                    owners_only_in_space = sorted(admins_set - owners_set)
                if actors_drift:
                    actors_only_in_meta = sorted(actors_set - oo_set)
                    actors_only_in_space = []
                else:
                    actors_only_in_meta = []
                    actors_only_in_space = []
                desired.append(
                    OrderResource.EphemeralSync(
                        dedupe_key=_dedupe_drift(w.id),
                        space_wallet_id=w.id,
                        payload={
                            "kind": ORDER_KIND_MULTISIG_SPACE_DRIFT,
                            "wallet_id": w.id,
                            "wallet_name": w.name,
                            "multisig_setup_status": st,
                            "tron_address": (w.tron_address or "").strip() or None,
                            "owners_drift": owners_drift,
                            "actors_drift": actors_drift,
                            "meta_owners": sorted(owners_set),
                            "actors": sorted(actors_set),
                            "space_tron_admins": sorted(admins_set),
                            "space_tron_owner_operator": sorted(oo_set),
                            "owners_only_in_meta": owners_only_in_meta,
                            "owners_only_in_space": owners_only_in_space,
                            "actors_only_in_meta": actors_only_in_meta,
                            "actors_only_in_space": actors_only_in_space,
                            "only_in_meta": actors_only_in_meta,
                            "only_in_space": actors_only_in_space,
                            "space_tron_owners": sorted(oo_set),
                        },
                    )
                )

        upserted, deleted = await self._orders.replace_ephemeral_orders(desired)
        return {"upserted": upserted, "deleted": deleted}

    async def create_withdrawal(
        self,
        space: str,
        actor_wallet_address: str,
        exchange_wallet_svc: ExchangeWalletService,
        *,
        wallet_id: int,
        token_type: str,
        symbol: str,
        contract_address: Optional[str],
        amount_raw: int,
        destination_address: str,
        purpose: str,
    ) -> Tuple[OrderResource.Get, str, str]:
        """
        Создаёт ордер withdrawal и токен в Redis; возвращает (order, sign_token, sign_path).
        sign_path = /o/{token} для склейки с base_url на роутере.
        """
        await self._space.ensure_owner_or_operator(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        row = await exchange_wallet_svc.get_wallet(
            space, actor_wallet_address, wallet_id
        )
        if row is None:
            raise ValueError("Wallet not found")
        if row.role not in ("external", "multisig"):
            raise ValueError("Invalid wallet role for withdrawal")

        dest = (destination_address or "").strip()
        if not is_valid_tron_address(dest):
            raise ValueError("Invalid destination TRON address")
        purpose_clean = (purpose or "").strip()
        if not purpose_clean:
            raise ValueError("Purpose is required")
        if len(purpose_clean) > 512:
            raise ValueError("Purpose is too long")
        if amount_raw <= 0:
            raise ValueError("Amount must be positive")

        tt = (token_type or "").strip().lower()
        if tt not in ("native", "trc20"):
            raise ValueError("token_type must be native or trc20")
        if tt == "trc20":
            ca = (contract_address or "").strip()
            if not ca:
                raise ValueError("contract_address required for TRC-20")
            allowed = {
                (t.contract_address or "").strip()
                for t in self._settings.collateral_stablecoin.tokens
                if (t.network or "").upper() == "TRON"
            }
            if ca not in allowed:
                raise ValueError("Unsupported TRC-20 contract")
        else:
            sym = (symbol or "").strip().upper()
            if sym != "TRX":
                raise ValueError("Native token must be TRX")

        tron_addr = (row.tron_address or "").strip()
        meta_raw = row.multisig_setup_meta
        meta = meta_raw if isinstance(meta_raw, dict) else {}
        threshold_n = 1
        threshold_m = 1
        actors: List[str] = []
        if row.role == "multisig":
            threshold_n = int(meta.get("threshold_n") or 1)
            threshold_m = int(meta.get("threshold_m") or 1)
            for a in meta.get("actors") or []:
                if isinstance(a, str) and a.strip():
                    actors.append(a.strip())
        long_expiration = threshold_n > 1

        active_permission_id: Optional[int] = None
        if row.role == "multisig":
            ap = row.account_permissions
            if isinstance(ap, dict):
                cfg = extract_chain_multisig_config(ap)
                if cfg and cfg.get("permission_id") is not None:
                    try:
                        active_permission_id = int(cfg["permission_id"])
                    except (TypeError, ValueError):
                        active_permission_id = None

        token_decimals = 6
        if tt == "trc20":
            ca_lookup = (contract_address or "").strip()
            for t in self._settings.collateral_stablecoin.tokens:
                if (t.network or "").upper() != "TRON":
                    continue
                if (t.contract_address or "").strip() == ca_lookup:
                    token_decimals = int(t.decimals) if t.decimals is not None else 6
                    break

        payload: Dict[str, Any] = {
            "kind": WITHDRAWAL_KIND,
            "status": WITHDRAWAL_STATUS_AWAITING_SIGNATURES,
            "wallet_id": wallet_id,
            "wallet_role": row.role,
            "tron_address": tron_addr or None,
            "token": {
                "type": tt,
                "symbol": (symbol or "").strip().upper(),
                "contract_address": (contract_address or "").strip() or None,
                "decimals": token_decimals,
            },
            "amount_raw": int(amount_raw),
            "destination_address": dest,
            "purpose": purpose_clean,
            "threshold_n": threshold_n,
            "threshold_m": threshold_m,
            "actors_snapshot": sorted(actors),
            "long_expiration_ms": long_expiration,
            "broadcast_tx_id": None,
            "last_error": None,
        }
        if row.role == "multisig":
            payload["active_permission_id"] = active_permission_id

        sign_token = secrets.token_urlsafe(24)
        dedupe = withdrawal_dedupe_key(sign_token)
        created = await self._orders.insert_withdrawal_order(
            dedupe_key=dedupe,
            space_wallet_id=wallet_id,
            payload=payload,
        )
        await self._session.commit()
        return created, sign_token, f"/o/{sign_token}"

    async def resolve_order_by_sign_token(self, token: str) -> Optional[Tuple[int, str]]:
        t = (token or "").strip()
        if not t:
            return None
        try:
            dk = withdrawal_dedupe_key(t)
        except ValueError:
            return None
        row = await self._orders.get_by_dedupe_key(dk)
        if not row or row.category != ORDER_CATEGORY_WITHDRAWAL:
            return None
        return row.id, ""

    async def delete_withdrawal_order(
        self,
        space: str,
        actor_wallet_address: str,
        order_id: int,
    ) -> None:
        await self._space.ensure_owner_or_operator(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        row = await self._orders.get_by_id(order_id)
        if not row or row.category != ORDER_CATEGORY_WITHDRAWAL:
            raise ValueError("Order not found")
        if row.space_wallet_id is None:
            raise ValueError("Order not found")
        w_stmt = select(Wallet).where(Wallet.id == row.space_wallet_id)
        w_res = await self._session.execute(w_stmt)
        wallet = w_res.scalar_one_or_none()
        if not wallet or (wallet.owner_did or "").strip() != owner_did:
            raise ValueError("Order not found")
        p = dict(row.payload or {})
        st = (p.get("status") or "").strip()
        if st in (
            WITHDRAWAL_STATUS_BROADCAST_SUBMITTED,
            WITHDRAWAL_STATUS_CONFIRMED,
            WITHDRAWAL_STATUS_FAILED,
        ):
            raise WithdrawalDeleteForbidden(
                "Cannot delete withdrawal in status broadcast_submitted, confirmed, or failed"
            )
        deleted = await self._orders.delete_withdrawal_by_id(order_id)
        if not deleted:
            raise ValueError("Order not found")
        await self._session.commit()

    async def clear_offchain_signatures(
        self,
        space: str,
        actor_wallet_address: str,
        order_id: int,
    ) -> OrderResource.Get:
        """Сброс off-chain подписей мультисиг-заявки (owner | operator)."""
        await self._space.ensure_owner_or_operator(space, actor_wallet_address)
        owner_did = await self._owner_did_for_space(space)
        row = await self._orders.get_by_id(order_id)
        if not row or row.category != ORDER_CATEGORY_WITHDRAWAL:
            raise ValueError("Order not found")
        if row.space_wallet_id is None:
            raise ValueError("Order not found")
        w_stmt = select(Wallet).where(Wallet.id == row.space_wallet_id)
        w_res = await self._session.execute(w_stmt)
        wallet = w_res.scalar_one_or_none()
        if not wallet or (wallet.owner_did or "").strip() != owner_did:
            raise ValueError("Order not found")
        p = dict(row.payload or {})
        if (p.get("wallet_role") or "").strip() != "multisig":
            raise ValueError("Only multisig withdrawals support signature reset")
        st = (p.get("status") or "").strip()
        if st not in (
            WITHDRAWAL_STATUS_AWAITING_SIGNATURES,
            WITHDRAWAL_STATUS_READY_TO_BROADCAST,
        ):
            raise ValueError("Cannot clear signatures in current status")
        await self._orders.delete_withdrawal_signatures(order_id)
        p["status"] = WITHDRAWAL_STATUS_AWAITING_SIGNATURES
        p["broadcast_tx_id"] = None
        p.pop("last_signer", None)
        p.pop("signed_at", None)
        for k in ("offchain_expiration_ms", "offchain_timestamp_ms", "offchain_signed_addresses"):
            p.pop(k, None)
        await self._orders.update_withdrawal_payload(order_id, p)
        out = await self._orders.get_by_id(order_id)
        if not out:
            raise ValueError("Order not found")
        await self._session.commit()
        return out

    async def get_public_sign_context(self, token: str) -> Optional[Dict[str, Any]]:
        resolved = await self.resolve_order_by_sign_token(token)
        if not resolved:
            return None
        order_id, _owner_did = resolved
        row = await self._orders.get_by_id(order_id)
        if not row or row.category != ORDER_CATEGORY_WITHDRAWAL:
            return None
        p = dict(row.payload or {})
        sigs_raw = await self._orders.list_withdrawal_signatures(order_id)
        sigs: List[Dict[str, Any]] = []
        for s in sigs_raw:
            entry = dict(s)
            ca = entry.get("created_at")
            if ca is not None and hasattr(ca, "isoformat"):
                entry["created_at"] = ca.isoformat()
            sigs.append(entry)
        return {
            "order_id": row.id,
            "status": p.get("status"),
            "wallet_role": p.get("wallet_role"),
            "tron_address": p.get("tron_address"),
            "token": p.get("token"),
            "amount_raw": p.get("amount_raw"),
            "destination_address": p.get("destination_address"),
            "purpose": p.get("purpose"),
            "threshold_n": p.get("threshold_n"),
            "threshold_m": p.get("threshold_m"),
            "actors_snapshot": p.get("actors_snapshot") or [],
            "active_permission_id": p.get("active_permission_id"),
            "long_expiration_ms": bool(p.get("long_expiration_ms")),
            "signatures": sigs,
            "offchain_expiration_ms": p.get("offchain_expiration_ms"),
            "offchain_timestamp_ms": p.get("offchain_timestamp_ms"),
            "offchain_signed_addresses": p.get("offchain_signed_addresses") or [],
            "broadcast_tx_id": p.get("broadcast_tx_id"),
            "last_error": p.get("last_error"),
        }

    async def submit_signed_transaction(
        self,
        token: str,
        signed_transaction: Dict[str, Any],
        signer_address: str,
    ) -> OrderResource.Get:
        resolved = await self.resolve_order_by_sign_token(token)
        if not resolved:
            raise ValueError("Invalid or expired sign token")
        order_id, _ = resolved
        row = await self._orders.get_by_id(order_id)
        if not row or row.category != ORDER_CATEGORY_WITHDRAWAL:
            raise ValueError("Order not found")
        p = dict(row.payload or {})
        st = (p.get("status") or "").strip()
        if st != WITHDRAWAL_STATUS_AWAITING_SIGNATURES:
            raise ValueError("Order is not awaiting signature")

        signer = (signer_address or "").strip()
        if not is_valid_tron_address(signer):
            raise ValueError("Invalid signer address")

        wallet_role = (p.get("wallet_role") or "").strip()
        if wallet_role == "multisig":
            actors_raw = p.get("actors_snapshot") or []
            actors_set: set[str] = set()
            if isinstance(actors_raw, list):
                for a in actors_raw:
                    if isinstance(a, str) and (a or "").strip():
                        actors_set.add(a.strip())
            if signer not in actors_set:
                raise ValueError("Signer is not in the multisig actors list")

        await self._orders.upsert_withdrawal_signature(
            order_id,
            signer,
            {"signed_transaction": signed_transaction},
        )
        sigs = await self._orders.list_withdrawal_signatures(order_id)
        signed_addrs: List[str] = []
        for s in sigs:
            sa = (s.get("signer_address") or "").strip()
            if sa:
                signed_addrs.append(sa)
        p["offchain_signed_addresses"] = signed_addrs
        exp_ms, ts_ms = _offchain_times_from_signed_tx(signed_transaction)
        if exp_ms is not None:
            p["offchain_expiration_ms"] = exp_ms
        if ts_ms is not None:
            p["offchain_timestamp_ms"] = ts_ms
        tn = int(p.get("threshold_n") or 1)
        txid = signed_transaction.get("txID") or signed_transaction.get("txid")
        if wallet_role == "external" or tn <= 1:
            p["status"] = WITHDRAWAL_STATUS_BROADCAST_SUBMITTED
            p["broadcast_tx_id"] = txid
            p.pop("last_error", None)
        else:
            if len(sigs) >= tn:
                p["status"] = WITHDRAWAL_STATUS_READY_TO_BROADCAST
                p["broadcast_tx_id"] = None
                p.pop("last_error", None)
            else:
                p["status"] = WITHDRAWAL_STATUS_AWAITING_SIGNATURES
                p["broadcast_tx_id"] = None
        p["last_signer"] = signer
        p["signed_at"] = datetime.now(timezone.utc).isoformat()
        await self._orders.update_withdrawal_payload(order_id, p)
        out = await self._orders.get_by_id(order_id)
        assert out is not None
        await self._session.commit()
        return out

    async def _withdrawal_onchain_failure_last_error(
        self,
        client: TronGridClient,
        tx_id: str,
        payload: Dict[str, Any],
    ) -> str:
        """
        Текст last_error: ответ ноды по tx + баланс USDT/TRX отправителя + OUT_OF_ENERGY.
        """
        tid = (tx_id or "").strip()
        extras: List[str] = []
        info: Dict[str, Any] = {}
        txwrap: Optional[Dict[str, Any]] = None
        try:
            info = await client.get_transaction_info(tid)
        except Exception as e:
            logger.warning("withdrawal failure get_transaction_info tx=%s: %s", tid[:16], e)
            return "Транзакция не выполнена в сети (не удалось получить детали)."
        if not isinstance(info, dict) or not info:
            return "Транзакция не выполнена в сети."
        receipt = info.get("receipt") if isinstance(info.get("receipt"), dict) else {}
        r = receipt.get("result")
        if info.get("blockNumber") and r is None:
            try:
                txwrap = await client.post(
                    "/wallet/gettransactionbyid", {"value": tid}
                )
            except Exception:
                txwrap = None
        base = TronGridClient.build_transaction_failure_message(info, txwrap)
        res_line = TronGridClient.describe_trx_resource_failure(info, txwrap)
        if res_line:
            extras.append(res_line)
        tok = payload.get("token") if isinstance(payload.get("token"), dict) else {}
        ttype = (tok.get("type") or "").strip().lower()
        owner = (payload.get("tron_address") or "").strip()
        if owner and is_valid_tron_address(owner):
            if ttype == "trc20":
                contract = (tok.get("contract_address") or "").strip()
                sym = (tok.get("symbol") or "USDT").strip().upper() or "USDT"
                try:
                    dec = int(tok.get("decimals") if tok.get("decimals") is not None else 6)
                except (TypeError, ValueError):
                    dec = 6
                if contract:
                    raw_bal = await client.trigger_constant_balance_of(owner, contract)
                    if raw_bal is not None:
                        if dec >= 0:
                            human = raw_bal / (10**dec)
                        else:
                            human = float(raw_bal)
                        extras.append(
                            f"Баланс {sym} на кошельке отправителя: {human} {sym} "
                            f"(минимальные единицы: {raw_bal})."
                        )
                        if raw_bal == 0:
                            extras.append(
                                "Вероятная причина отката контракта — нулевой баланс токена."
                            )
            elif ttype == "native":
                sun = await client.get_account_trx_balance_sun(owner)
                if sun is not None:
                    trx_amt = sun / 1_000_000
                    extras.append(
                        f"Баланс TRX на кошельке отправителя: {trx_amt:.6f} TRX ({sun} SUN)."
                    )
                    if sun == 0:
                        extras.append(
                            "Вероятная причина — недостаточно TRX для комиссии или перевода."
                        )
        parts = [base] + extras
        text = "\n".join(parts).strip()
        return (text or "Транзакция не выполнена в сети.")[:2000]

    async def refresh_withdrawal_statuses(self) -> Dict[str, int]:
        """Cron: опрос Tron по txid для ордеров в broadcast_submitted."""
        stmt = select(OrderModel).where(
            OrderModel.category == ORDER_CATEGORY_WITHDRAWAL,
        )
        res = await self._session.execute(stmt)
        models = list(res.scalars().all())
        updated = 0
        async with TronGridClient(settings=self._settings) as client:
            for m in models:
                p = dict(m.payload or {})
                if p.get("status") != WITHDRAWAL_STATUS_BROADCAST_SUBMITTED:
                    continue
                txid = (p.get("broadcast_tx_id") or "").strip()
                if not txid:
                    continue
                try:
                    ok = await client.get_transaction_success(txid)
                except Exception as e:
                    logger.warning("withdrawal poll tx=%s failed: %s", txid[:16], e)
                    continue
                if ok is None:
                    continue
                if ok is True:
                    p["status"] = WITHDRAWAL_STATUS_CONFIRMED
                else:
                    p["status"] = WITHDRAWAL_STATUS_FAILED
                    try:
                        detail = await self._withdrawal_onchain_failure_last_error(
                            client, txid, p
                        )
                    except Exception as e:
                        logger.warning(
                            "withdrawal failure detail tx=%s: %s", txid[:16], e
                        )
                        detail = ""
                    p["last_error"] = (
                        detail.strip() or "Транзакция не выполнена в сети."
                    )[:2000]
                await self._orders.update_withdrawal_payload(int(m.id), p)
                updated += 1
        return {"updated": updated}

    async def broadcast_ready_withdrawals(self) -> Dict[str, Any]:
        """
        Отправка в сеть заявок multisig в статусе ready_to_broadcast (cron).
        Успех: broadcast_submitted + broadcast_tx_id; ошибка ноды: last_error, статус без изменений.
        """
        stmt = select(OrderModel).where(OrderModel.category == ORDER_CATEGORY_WITHDRAWAL)
        res = await self._session.execute(stmt)
        models = list(res.scalars().all())
        broadcasted = 0
        errors = 0
        async with TronGridClient(settings=self._settings) as client:
            for m in models:
                p = dict(m.payload or {})
                if p.get("status") != WITHDRAWAL_STATUS_READY_TO_BROADCAST:
                    continue
                sigs_raw = await self._orders.list_withdrawal_signatures(int(m.id))
                signed_tx = _best_signed_transaction_from_rows(sigs_raw)
                if not signed_tx:
                    err = "No signed transaction in signatures"
                    p["last_error"] = err[:500]
                    await self._orders.update_withdrawal_payload(int(m.id), p)
                    errors += 1
                    logger.warning(
                        "withdrawal broadcast order_id=%s: %s", int(m.id), err[:200]
                    )
                    continue
                try:
                    out = await client.broadcast_transaction(dict(signed_tx))
                except Exception as e:
                    msg = str(e).strip()[:500] or "broadcast failed"
                    p["last_error"] = msg
                    await self._orders.update_withdrawal_payload(int(m.id), p)
                    errors += 1
                    logger.warning(
                        "withdrawal broadcast order_id=%s exception: %s",
                        int(m.id),
                        msg[:200],
                    )
                    continue
                if not out.get("result"):
                    p["last_error"] = _broadcast_error_message(out)
                    await self._orders.update_withdrawal_payload(int(m.id), p)
                    errors += 1
                    logger.warning(
                        "withdrawal broadcast order_id=%s node: %s",
                        int(m.id),
                        p["last_error"][:200],
                    )
                    continue
                chain_txid = str(
                    signed_tx.get("txID") or signed_tx.get("txid") or ""
                ).strip()
                if not chain_txid:
                    p["last_error"] = "Broadcast ok but signed tx missing txID"
                    await self._orders.update_withdrawal_payload(int(m.id), p)
                    errors += 1
                    continue
                p["status"] = WITHDRAWAL_STATUS_BROADCAST_SUBMITTED
                p["broadcast_tx_id"] = chain_txid
                p.pop("last_error", None)
                await self._orders.update_withdrawal_payload(int(m.id), p)
                broadcasted += 1
        return {"broadcasted": broadcasted, "broadcast_errors": errors}
