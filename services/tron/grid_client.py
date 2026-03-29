"""TronGrid HTTP-клиент."""

from __future__ import annotations

import json as _json
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from tronpy.keys import PrivateKey as TronPrivateKey

from settings import Settings

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
    """

    # ---- class-level URL map -----------------------------------------------

    _NETWORKS: Dict[str, str] = {
        "mainnet": "https://api.trongrid.io",
        "shasta":  "https://api.shasta.trongrid.io",
        "nile":    "https://api.nile.trongrid.io",
    }

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
        if r in ("FAILED", "REVERT", "OUT_OF_TIME"):
            return False
        if data.get("id") and not receipt:
            return None
        return None

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
