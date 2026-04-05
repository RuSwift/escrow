"""TronGrid HTTP-клиент."""

from __future__ import annotations

import json as _json
import logging
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from tronpy import keys as tron_keys
from tronpy.keys import PrivateKey as TronPrivateKey

from settings import Settings

logger = logging.getLogger(__name__)

from services.multisig_wallet.constants import DEFAULT_ACTIVE_OPERATIONS_HEX

# Tron owner permission: 1-of-N по ключам спейса (см. AccountPermissionUpdate).
OWNER_PERMISSION_THRESHOLD = 1

class TronGridClient:
    """
    Async context manager для работы с TronGrid API в рамках одного aiohttp-сеанса.

    Использование:
        async with TronGridClient(settings=settings) as client:
            acc = await client.get_account("T...")
            ok  = await client.get_transaction_success(tx_id)
            err = await client.get_transaction_failure_detail(tx_id)  # при провале on-chain
    """

    # ---- class-level URL map -----------------------------------------------

    _NETWORKS: Dict[str, str] = {
        "mainnet": "https://api.trongrid.io",
        "shasta":  "https://api.shasta.trongrid.io",
        "nile":    "https://api.nile.trongrid.io",
    }

    _FAILURE_DETAIL_MAX = 2000
    _TRC20_REVERT_HINT = (
        "Для вызова контракта (TRC-20 и др.) частая причина REVERT — недостаточный баланс "
        "токена на адресе отправителя, заморозка адреса (USDT) или иные ограничения контракта."
    )

    # ---- construction / context manager ------------------------------------

    def __init__(
        self,
        *,
        settings: Settings,
        tron_api_key: Optional[str] = None,
        timeout_sec: float = 25,
    ) -> None:
        network = (settings.tron.network or "").strip().lower()
        if network not in self._NETWORKS:
            raise ValueError(f"Unsupported TRON network: {settings.tron.network!r}")
        self._base_url = self._NETWORKS[network]
        api_key = (tron_api_key or "").strip() or (settings.tron.api_key or "").strip()
        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["TRON-PRO-API-KEY"] = api_key
        self._timeout = aiohttp.ClientTimeout(total=timeout_sec)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "TronGridClient":
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
            headers=self._headers,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    # ---- low-level HTTP -----------------------------------------------------

    async def post(
        self,
        path: str,
        payload: Dict[str, Any],
        *,
        timeout_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        """POST {base}{path} с JSON-телом; возвращает dict."""
        if self._session is None:
            raise RuntimeError("TronGridClient must be used as async context manager")
        url = self._base_url + path
        kw: Dict[str, Any] = {}
        if timeout_sec is not None:
            kw["timeout"] = aiohttp.ClientTimeout(total=timeout_sec)
        async with self._session.post(url, json=payload, **kw) as resp:
            raw = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"TronGrid {path} HTTP {resp.status}: {raw[:400]}")
            try:
                return _json.loads(raw) if raw else {}
            except _json.JSONDecodeError as e:
                raise RuntimeError(f"TronGrid invalid JSON: {e!s}") from e

    # ---- pure static helpers (без I/O) -------------------------------------

    @staticmethod
    def build_permission_body(
        *,
        owner_address: str,
        owner_tron_addresses: List[str],
        actor_addresses: List[str],
        threshold: int,
        permission_name: str,
    ) -> Dict[str, Any]:
        """Тело для /wallet/accountpermissionupdate.

        Блок ``owner``: адреса owner-ролей спейса (не адрес multisig), ``threshold`` = 1.
        """
        owner_keys_raw = [a.strip() for a in owner_tron_addresses if (a or "").strip()]
        if not owner_keys_raw:
            raise ValueError("owner_tron_addresses must be non-empty")
        owner_keys = [{"address": a, "weight": 1} for a in owner_keys_raw]
        if len(owner_keys) < OWNER_PERMISSION_THRESHOLD:
            raise ValueError("owner threshold exceeds number of owner keys")
        active_keys = [{"address": a.strip(), "weight": 1} for a in actor_addresses]
        if len(active_keys) < threshold:
            raise ValueError("threshold exceeds number of keys")
        name = (permission_name or "multisig_active")[:32]
        return {
            "owner_address": owner_address.strip(),
            "owner": {
                "type": 0,
                "permission_name": "owner",
                "threshold": OWNER_PERMISSION_THRESHOLD,
                "keys": owner_keys,
            },
            "actives": [
                {
                    "type": 2,
                    "permission_name": name,
                    "threshold": threshold,
                    "operations": DEFAULT_ACTIVE_OPERATIONS_HEX,
                    "keys": active_keys,
                }
            ],
            "visible": True,
        }

    @staticmethod
    def sign_tx(*, raw_tx: Dict[str, Any], private_key_hex: str) -> Dict[str, Any]:
        """Подпись txID одним owner-ключом (нативный TRON, без TVM)."""
        tx_id = raw_tx.get("txID") or raw_tx.get("txid") or ""
        raw_hex = raw_tx.get("raw_data_hex") or ""
        if not tx_id or not raw_hex:
            raise ValueError("transaction missing txID or raw_data_hex")
        priv = TronPrivateKey(bytes.fromhex(private_key_hex.strip()))
        sig = priv.sign_msg_hash(bytes.fromhex(tx_id))
        signed: Dict[str, Any] = {
            "txID": tx_id,
            "raw_data_hex": raw_hex,
            "signature": [sig.hex()],
        }
        if isinstance(raw_tx.get("raw_data"), dict):
            signed["raw_data"] = raw_tx["raw_data"]
        return signed

    @staticmethod
    def _unwrap_tx(resp: Dict[str, Any]) -> Dict[str, Any]:
        for key in ("transaction", "Transaction"):
            tx = resp.get(key)
            if isinstance(tx, dict) and (tx.get("txID") or tx.get("txid")):
                return tx
        if resp.get("txID") or resp.get("txid"):
            return resp
        raise RuntimeError(f"No transaction in response: {list(resp.keys())}")

    # ---- account / chain ---------------------------------------------------

    async def get_account(self, address: str) -> Dict[str, Any]:
        """Данные аккаунта (getaccount). Поднимает RuntimeError при ошибке TronGrid."""
        data = await self.post(
            "/wallet/getaccount",
            {"address": address.strip(), "visible": True},
        )
        err = data.get("Error")
        if isinstance(err, str) and err.strip():
            raise RuntimeError(f"TronGrid getaccount: {err.strip()[:300]}")
        return data

    async def get_account_trx_balance_sun(self, address_base58: str) -> Optional[int]:
        """Баланс TRX в SUN (getaccount.balance) или None при ошибке."""
        addr = (address_base58 or "").strip()
        if not addr:
            return None
        try:
            data = await self.get_account(addr)
        except Exception as e:
            logger.warning("get_account_trx_balance_sun %s: %s", addr[:12], e)
            return None
        b = data.get("balance")
        if b is None:
            return 0
        try:
            return int(b)
        except (TypeError, ValueError):
            return None

    async def trigger_constant_balance_of(
        self,
        owner_base58: str,
        contract_base58: str,
    ) -> Optional[int]:
        """TRC-20 balanceOf(owner) raw uint256 или None при ошибке вызова."""
        owner = (owner_base58 or "").strip()
        contract = (contract_base58 or "").strip()
        if not owner or not contract:
            return None
        try:
            param = tron_keys.to_tvm_address(owner).hex().rjust(64, "0")
            data = await self.post(
                "/wallet/triggerconstantcontract",
                {
                    "owner_address": owner,
                    "contract_address": contract,
                    "function_selector": "balanceOf(address)",
                    "parameter": param,
                    "call_value": 0,
                    "visible": True,
                },
            )
        except Exception as e:
            logger.warning("trigger_constant_balance_of: %s", e)
            return None
        constant_result = data.get("constant_result") or []
        if not constant_result:
            return None
        try:
            return int(str(constant_result[0]), 16)
        except (TypeError, ValueError):
            return None

    async def get_transaction_info(self, tx_id: str) -> Dict[str, Any]:
        """gettransactioninfobyid."""
        return await self.post(
            "/wallet/gettransactioninfobyid",
            {"value": tx_id.strip()},
        )

    async def get_transaction_success(self, tx_id: str) -> Optional[bool]:
        """None — не финализирована; True — SUCCESS; False — провал."""
        tid = (tx_id or "").strip()
        if not tid:
            return None
        data = await self.get_transaction_info(tid)
        if not data:
            return None
        receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
        r = receipt.get("result")
        if r == "SUCCESS":
            return True
        if r in ("FAILED", "REVERT", "OUT_OF_TIME", "OUT_OF_ENERGY"):
            return False
        if data.get("id") and not receipt:
            return None
        # Нативный TransferContract: gettransactioninfobyid часто даёт receipt только с net_usage /
        # energy_usage, без receipt["result"]. Итог — в gettransactionbyid → ret[].contractRet.
        if data.get("blockNumber") and r is None:
            try:
                txwrap = await self.post("/wallet/gettransactionbyid", {"value": tid})
            except Exception:
                return None
            ret = txwrap.get("ret")
            if isinstance(ret, list) and ret and isinstance(ret[0], dict):
                cr = ret[0].get("contractRet")
                if cr == "SUCCESS":
                    return True
                if cr in ("REVERT", "OUT_OF_TIME", "FAILED", "OUT_OF_ENERGY"):
                    return False
        return None

    @staticmethod
    def describe_trx_resource_failure(
        info: Dict[str, Any],
        txwrap: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Текст про нехватку энергии / TRX на оплату ресурсов (OUT_OF_ENERGY и аналоги).
        """
        receipt = info.get("receipt") if isinstance(info.get("receipt"), dict) else {}
        rr = receipt.get("result")
        if rr == "OUT_OF_ENERGY":
            return (
                "Ресурсы сети: не хватило энергии (OUT_OF_ENERGY). "
                "Нужен TRX для оплаты энергии или заморозка TRX под Energy."
            )
        cr = None
        if txwrap and isinstance(txwrap.get("ret"), list) and txwrap["ret"]:
            r0 = txwrap["ret"][0]
            if isinstance(r0, dict):
                cr = r0.get("contractRet")
        if cr == "OUT_OF_ENERGY":
            return (
                "Ресурсы сети: не хватило энергии (OUT_OF_ENERGY). "
                "Пополните TRX или заморозьте TRX для получения Energy."
            )
        node = TronGridClient._decode_res_message_hex(info.get("resMessage"))
        if node and "OUT OF ENERGY" in node.upper():
            return (
                "Сообщение сети указывает на нехватку энергии; пополните TRX "
                "или заморозьте TRX под Energy."
            )
        return None

    @staticmethod
    def _decode_res_message_hex(raw: Any) -> Optional[str]:
        """Декодирует resMessage из gettransactioninfobyid (часто hex → ASCII)."""
        if raw is None:
            return None
        if not isinstance(raw, str):
            raw = str(raw)
        s = raw.strip()
        if len(s) < 2 or len(s) % 2 != 0:
            return None
        try:
            b = bytes.fromhex(s)
        except ValueError:
            return None
        if not b:
            return None
        try:
            text = b.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if not text.strip():
            return None
        for ch in text:
            o = ord(ch)
            if o < 32 and ch not in "\t\n\r":
                return None
        return text.strip()

    @staticmethod
    def build_transaction_failure_message(
        info: Dict[str, Any],
        txwrap: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Человекочитаемое описание неуспешной tx по ответам gettransactioninfobyid
        и опционально gettransactionbyid.
        """
        parts: List[str] = []
        receipt = info.get("receipt") if isinstance(info.get("receipt"), dict) else {}
        rr = receipt.get("result")
        if isinstance(rr, str) and rr.strip():
            parts.append(f"Итог в чеке: {rr.strip()}")

        node_msg = TronGridClient._decode_res_message_hex(info.get("resMessage"))
        if node_msg:
            parts.append(f"Сообщение ноды: {node_msg}")
        elif isinstance(info.get("resMessage"), str) and info.get("resMessage", "").strip():
            parts.append(f"resMessage: {str(info.get('resMessage')).strip()[:300]}")

        top = info.get("result")
        if isinstance(top, str) and top.strip():
            parts.append(f"Статус: {top.strip()}")

        if txwrap and isinstance(txwrap.get("ret"), list) and txwrap["ret"]:
            r0 = txwrap["ret"][0]
            if isinstance(r0, dict):
                cr = r0.get("contractRet")
                if isinstance(cr, str) and cr.strip() and cr.strip() != "SUCCESS":
                    parts.append(f"contractRet: {cr.strip()}")

        cr_list = info.get("contract_result")
        if isinstance(cr_list, list) and cr_list:
            non_empty = [x for x in cr_list if isinstance(x, str) and x.strip()]
            if non_empty:
                parts.append(f"contract_result: {non_empty[0][:200]}")

        ca = info.get("contract_address")
        if isinstance(ca, str) and ca.strip() and rr == "REVERT":
            parts.append(TronGridClient._TRC20_REVERT_HINT)

        if not parts:
            return "Транзакция не выполнена в сети (подробности недоступны)."

        return "\n".join(parts)[: TronGridClient._FAILURE_DETAIL_MAX]

    async def get_transaction_failure_detail(self, tx_id: str) -> str:
        """Текст для last_error при failed on-chain (gettransactioninfobyid + при необходимости gettransactionbyid)."""
        tid = (tx_id or "").strip()
        if not tid:
            return "Транзакция не выполнена в сети."
        data = await self.get_transaction_info(tid)
        if not isinstance(data, dict) or not data:
            return "Транзакция не выполнена в сети (ответ от узла пустой)."
        txwrap: Optional[Dict[str, Any]] = None
        receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}
        r = receipt.get("result")
        if data.get("blockNumber") and r is None:
            try:
                txwrap = await self.post("/wallet/gettransactionbyid", {"value": tid})
            except Exception:
                txwrap = None
        return self.build_transaction_failure_message(data, txwrap)

    async def get_chain_parameters(self) -> Dict[str, Any]:
        """getchainparameters."""
        return await self.post("/wallet/getchainparameters", {})

    async def get_tx_fee_per_byte_sun(self) -> int:
        """Transaction fee per byte (SUN) из chain parameters. Фоллбэк: 1000."""
        try:
            data = await self.get_chain_parameters()
            rows = data.get("chainParameter") or data.get("chain_parameter") or []
            if isinstance(rows, list):
                for row in rows:
                    if str(row.get("key") or "") == "getTransactionFee":
                        val = int(row.get("value") or 0)
                        if val > 0:
                            return val
        except Exception:
            pass
        return 1000

    # ---- permission update --------------------------------------------------

    async def create_permission_update_tx(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """POST /wallet/accountpermissionupdate."""
        data = await self.post("/wallet/accountpermissionupdate", body)
        err = data.get("Error")
        if isinstance(err, str) and err.strip():
            raise RuntimeError(f"accountpermissionupdate: {err.strip()[:400]}")
        return data

    async def broadcast_transaction(self, signed: Dict[str, Any]) -> Dict[str, Any]:
        """POST /wallet/broadcasttransaction."""
        if "visible" not in signed:
            signed = {**signed, "visible": True}
        return await self.post("/wallet/broadcasttransaction", signed)

    async def permission_update_sign_and_broadcast(
        self,
        *,
        owner_address: str,
        owner_tron_addresses: List[str],
        actor_addresses: List[str],
        threshold: int,
        permission_name: str,
        owner_private_key_hex: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """Полный цикл: build → create tx → sign → broadcast. Returns (tx_id, broadcast_response)."""
        body = self.build_permission_body(
            owner_address=owner_address,
            owner_tron_addresses=owner_tron_addresses,
            actor_addresses=actor_addresses,
            threshold=threshold,
            permission_name=permission_name,
        )
        resp = await self.create_permission_update_tx(body)
        raw_tx = self._unwrap_tx(resp)
        signed = self.sign_tx(raw_tx=raw_tx, private_key_hex=owner_private_key_hex)
        out = await self.broadcast_transaction(signed)
        txid = str(raw_tx.get("txID") or raw_tx.get("txid") or "")
        return txid, out

    async def estimate_permission_update_sun(
        self,
        *,
        owner_address: str,
        owner_tron_addresses: List[str],
        actor_addresses: List[str],
        threshold: int,
        permission_name: str,
        margin: float = 0.10,
    ) -> int:
        """
        Оценка требуемых SUN для AccountPermissionUpdate (+margin).

        1. Dry-run tx через create_permission_update_tx.
        2. Размер raw_data_hex → байты.
        3. fee_per_byte из chain params.
        4. base * (1 + margin).
        """
        body = self.build_permission_body(
            owner_address=owner_address,
            owner_tron_addresses=owner_tron_addresses,
            actor_addresses=actor_addresses,
            threshold=threshold,
            permission_name=permission_name,
        )
        tx_resp = await self.create_permission_update_tx(body)
        raw_tx = tx_resp.get("transaction") if isinstance(tx_resp.get("transaction"), dict) else tx_resp
        raw_hex = str(raw_tx.get("raw_data_hex") or "")
        tx_size_bytes = max(1, len(raw_hex) // 2) if raw_hex else 300
        fee_per_byte = await self.get_tx_fee_per_byte_sun()
        base_sun = max(1, tx_size_bytes * fee_per_byte)
        return max(1, int(base_sun * (1 + margin)))
