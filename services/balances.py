"""
Балансы TRON: TRC-20 (raw base-units) и нативный TRX (SUN).

Сервис:
1) TRC-20: ``balanceOf(address)`` через TronGrid ``/wallet/triggerconstantcontract``.
2) TRX: баланс аккаунта через ``/wallet/getaccount`` (поле balance в SUN).
3) Кеш в Redis на 60 секунд (отдельные ключи для набора контрактов и для TRX).
4) При ошибке API для кошелька — fallback из БД ``token_balance_cache`` и запись снимка в Redis.
   Для TRX в БД используется псевдо-контракт ``NATIVE:TRX``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

import aiohttp
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from tronpy import keys as tron_keys

from repos.token_balance_cache import TokenBalanceCacheRepository
from settings import Settings
from services.tron.utils import is_valid_tron_address


_CACHE_TTL_SEC = 60
_TRON_BLOCKCHAIN_NAME = "TRON"
"""Ключ в token_balance_cache / ответах API — не контракт, а маркер нативного TRX (SUN)."""
TRON_NATIVE_TRX_CACHE_KEY = "NATIVE:TRX"
TRON_NATIVE_SYMBOL = "TRX"


def collateral_contract_addresses_for_network(
    settings: Settings,
    *,
    network_label: str,
) -> List[str]:
    """
    Адреса контрактов из collateral_stablecoin.tokens для сети (TRON / ETH / ETHEREUM).
    """
    want = (network_label or "").strip().upper()
    if want == "ETHEREUM":
        want = "ETH"
    out: List[str] = []
    for t in settings.collateral_stablecoin.tokens:
        net = (t.network or "").strip().upper()
        if net == "ETHEREUM":
            net = "ETH"
        if net == want and (t.contract_address or "").strip():
            out.append(t.contract_address.strip())
    return out


def _tron_base_url(network: str) -> str:
    n = (network or "").strip().lower()
    if n == "mainnet":
        return "https://api.trongrid.io"
    if n == "shasta":
        return "https://api.shasta.trongrid.io"
    if n == "nile":
        return "https://api.nile.trongrid.io"
    raise ValueError(f"Unsupported TRON network: {network}")


class BalancesService:
    """TRON: TRC-20 по контрактам и нативный TRX (SUN)."""

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings) -> None:
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = TokenBalanceCacheRepository(session=session)

    @staticmethod
    def _encode_abi_address_param(address: str) -> str:
        """
        ABI-encoding для ``address`` параметра в EVM-like формате:
        - ``balanceOf(address)`` ожидает 20 bytes адрес
        - ABI адрес занимает 32 bytes => left-pad до 64 hex chars
        """

        tvm_bytes = tron_keys.to_tvm_address(address.strip())
        tvm_hex = tvm_bytes.hex()  # 40 chars
        return tvm_hex.rjust(64, "0")

    @staticmethod
    def _contracts_hash(contract_addresses: List[str]) -> str:
        raw = "|".join(sorted((c or "").strip() for c in contract_addresses if c))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]

    def _resolve_tron_api_key(self, tron_api_key: Optional[str]) -> Optional[str]:
        """Ключ TronGrid опционален: запросы всё равно идут в API, заголовок ключа — только если задан."""
        key = (tron_api_key or "").strip() or (self._settings.tron.api_key or "").strip()
        return key if key else None

    def _cache_key(self, *, wallet_address: str, contracts_hash: str) -> str:
        addr = (wallet_address or "").strip()
        return f"balances:tron:trc20:raw:{contracts_hash}:{addr}"

    def _cache_key_native_trx(self, *, wallet_address: str) -> str:
        addr = (wallet_address or "").strip()
        return f"balances:tron:native:trx:{addr}"

    async def _tron_getaccount_balance_sun(
        self,
        *,
        owner_wallet_address: str,
        tron_api_key: Optional[str],
        session: aiohttp.ClientSession,
    ) -> int:
        """Баланс TRX в SUN (целое с TronGrid ``/wallet/getaccount``)."""

        url = _tron_base_url(self._settings.tron.network) + "/wallet/getaccount"
        payload: Dict[str, Any] = {"address": owner_wallet_address, "visible": True}

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        key = (tron_api_key or "").strip()
        if key:
            headers["TRON-PRO-API-KEY"] = key

        async with session.post(url, json=payload, headers=headers, timeout=20) as resp:
            raw_text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(
                    f"TronGrid getaccount error status={resp.status}: {raw_text[:300]}"
                )
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"TronGrid getaccount invalid JSON: {e!s}") from e

        tr_err = data.get("Error")
        if isinstance(tr_err, str) and tr_err.strip():
            raise RuntimeError(f"TronGrid getaccount error: {tr_err.strip()[:300]}")

        bal = data.get("balance")
        if bal is None:
            return 0
        try:
            return int(bal)
        except (TypeError, ValueError):
            return 0

    async def _trigger_constant_balance_of(
        self,
        *,
        owner_wallet_address: str,
        contract_address: str,
        tron_api_key: Optional[str],
        session: aiohttp.ClientSession,
    ) -> int:
        """Возвращает raw uint256 баланс: contract.balanceOf(owner_wallet_address)."""

        function_selector = "balanceOf(address)"
        parameter = self._encode_abi_address_param(owner_wallet_address)

        url = (
            _tron_base_url(self._settings.tron.network)
            + "/wallet/triggerconstantcontract"
        )
        payload: Dict[str, Any] = {
            "owner_address": owner_wallet_address,
            "contract_address": contract_address,
            "function_selector": function_selector,
            "parameter": parameter,
            "call_value": 0,
            # Как в tronpy: без visible=True нода ожидает другой формат и часто отвечает
            # OTHER_ERROR / пустой constant_result → ложный нулевой баланс.
            "visible": True,
        }

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        key = (tron_api_key or "").strip()
        if key:
            headers["TRON-PRO-API-KEY"] = key

        async with session.post(url, json=payload, headers=headers, timeout=20) as resp:
            raw_text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(
                    f"TronGrid error status={resp.status}: {raw_text[:300]}"
                )
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"TronGrid invalid JSON: {e!s}") from e

        tr_err = data.get("Error")
        if isinstance(tr_err, str) and tr_err.strip():
            raise RuntimeError(f"TronGrid error: {tr_err.strip()[:300]}")

        res_block = data.get("result")
        if isinstance(res_block, dict):
            if res_block.get("result") is False:
                msg = res_block.get("message") or res_block.get("code") or "contract call failed"
                if isinstance(msg, str):
                    msg = msg[:400]
                raise RuntimeError(f"TronGrid contract call failed: {msg}")
            # Ошибка вида {"result":{"code":"OTHER_ERROR","message":"..."}} без result:true
            if res_block.get("result") is not True and res_block.get("code"):
                code = str(res_block.get("code", "")).strip().upper()
                if code and code != "SUCCESS":
                    msg = res_block.get("message") or code
                    if isinstance(msg, str) and len(msg) > 2 and all(
                        c in "0123456789abcdefABCDEF" for c in msg
                    ):
                        try:
                            msg = bytes.fromhex(msg).decode("utf-8", errors="replace")[:400]
                        except ValueError:
                            msg = msg[:400]
                    elif isinstance(msg, str):
                        msg = msg[:400]
                    raise RuntimeError(f"TronGrid error {code}: {msg}")

        constant_result = data.get("constant_result") or []
        if not constant_result:
            return 0
        # constant_result[0] is hex string without 0x prefix
        return int(str(constant_result[0]), 16)

    async def _read_balances_from_db_raw(
        self,
        *,
        wallet_address: str,
        contract_addresses: List[str],
    ) -> Dict[str, int]:
        """
        Возвращает fallback из БД (и всегда отдаёт ключи contract_addresses, пропущенные -> 0).
        """

        from collections import defaultdict

        cached: Dict[str, Any] = await self._repo.get_balances_raw(
            address=wallet_address,
            blockchain=_TRON_BLOCKCHAIN_NAME,
            contract_addresses=contract_addresses,
        )
        out: Dict[str, int] = defaultdict(int)  # missing => 0
        for c in contract_addresses:
            v = cached.get(c)
            out[c] = int(v) if v is not None else 0
        return dict(out)

    async def _upsert_balances_to_db_raw(
        self,
        *,
        wallet_address: str,
        balances_raw: Dict[str, int],
    ) -> None:
        await self._repo.upsert_balances_raw(
            address=wallet_address,
            blockchain=_TRON_BLOCKCHAIN_NAME,
            balances_raw=balances_raw,
        )
        await self._session.commit()

    async def list_tron_trc20_balances_raw(
        self,
        wallet_addresses: List[str],
        contract_addresses: List[str],
        *,
        tron_api_key: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Dict[str, Dict[str, int]]:
        """
        Args:
            wallet_addresses: TRON wallet base58 addresses (T...)
            contract_addresses: TRC-20 contract base58 addresses
            tron_api_key: TronGrid API key (если None — settings.tron.api_key); без ключа запрос
                к TronGrid всё равно выполняется, без заголовка TRON-PRO-API-KEY.
            refresh_cache: если True — обойти Redis и сходить в TronGrid (или fallback при ошибке).

        Returns:
            { wallet_address: { contract_address: balance_raw_int, ... }, ... }
        """

        addrs = [(a or "").strip() for a in (wallet_addresses or [])]
        addrs = [a for a in addrs if a]
        contracts = [(c or "").strip() for c in (contract_addresses or [])]
        contracts = [c for c in contracts if c]

        if not addrs or not contracts:
            return {}

        for a in addrs:
            if not is_valid_tron_address(a):
                raise ValueError(f"Invalid TRON address: {a}")
        for c in contracts:
            if not is_valid_tron_address(c):
                raise ValueError(f"Invalid TRC-20 contract address: {c}")

        contracts_hash = self._contracts_hash(contracts)
        api_key = self._resolve_tron_api_key(tron_api_key)

        result: Dict[str, Dict[str, int]] = {}
        missing: List[str] = []

        for a in addrs:
            key = self._cache_key(wallet_address=a, contracts_hash=contracts_hash)
            if not refresh_cache:
                cached = await self._redis.get(key)
                if cached:
                    try:
                        payload = json.loads(cached)
                        result[a] = {c: int(payload.get(c, 0)) for c in contracts}
                        continue
                    except Exception:
                        pass
            missing.append(a)

        if not missing:
            return result

        async def _apply_db_fallback_to_cache(wallet: str) -> Dict[str, int]:
            cache_key = self._cache_key(
                wallet_address=wallet, contracts_hash=contracts_hash
            )
            fallback = await self._read_balances_from_db_raw(
                wallet_address=wallet,
                contract_addresses=contracts,
            )
            await self._redis.setex(
                cache_key,
                _CACHE_TTL_SEC,
                json.dumps(fallback, ensure_ascii=False),
            )
            return fallback

        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for a in missing:
                cache_key = self._cache_key(wallet_address=a, contracts_hash=contracts_hash)
                try:
                    balances_raw: Dict[str, int] = {}
                    # По одному кошельку запросы последовательно; любое исключение (HTTP, JSON,
                    # ошибка в теле Tron) → для этого адреса целиком fallback из БД + Redis.
                    for c in contracts:
                        balances_raw[c] = await self._trigger_constant_balance_of(
                            owner_wallet_address=a,
                            contract_address=c,
                            tron_api_key=api_key,
                            session=session,
                        )

                    await self._upsert_balances_to_db_raw(
                        wallet_address=a, balances_raw=balances_raw
                    )

                    # Cache for address
                    await self._redis.setex(
                        cache_key,
                        _CACHE_TTL_SEC,
                        json.dumps(balances_raw, ensure_ascii=False),
                    )
                    result[a] = balances_raw
                except Exception:
                    result[a] = await _apply_db_fallback_to_cache(a)

        return result

    async def list_tron_native_trx_balances_raw(
        self,
        wallet_addresses: List[str],
        *,
        tron_api_key: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Dict[str, int]:
        """
        Нативный TRX в SUN на кошелёк (не TRC-20).

        Returns:
            { wallet_address: balance_sun_int, ... }
        """

        addrs = [(a or "").strip() for a in (wallet_addresses or [])]
        addrs = [a for a in addrs if a]
        if not addrs:
            return {}

        for a in addrs:
            if not is_valid_tron_address(a):
                raise ValueError(f"Invalid TRON address: {a}")

        api_key = self._resolve_tron_api_key(tron_api_key)
        result: Dict[str, int] = {}
        missing: List[str] = []

        for a in addrs:
            rkey = self._cache_key_native_trx(wallet_address=a)
            if not refresh_cache:
                cached = await self._redis.get(rkey)
                if cached:
                    try:
                        result[a] = int(json.loads(cached))
                        continue
                    except Exception:
                        pass
            missing.append(a)

        if not missing:
            return result

        async def _native_db_fallback_to_cache(wallet: str) -> int:
            rkey = self._cache_key_native_trx(wallet_address=wallet)
            fb = await self._read_balances_from_db_raw(
                wallet_address=wallet,
                contract_addresses=[TRON_NATIVE_TRX_CACHE_KEY],
            )
            sun = int(fb.get(TRON_NATIVE_TRX_CACHE_KEY, 0))
            await self._redis.setex(rkey, _CACHE_TTL_SEC, json.dumps(sun, ensure_ascii=False))
            return sun

        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for a in missing:
                rkey = self._cache_key_native_trx(wallet_address=a)
                try:
                    sun = await self._tron_getaccount_balance_sun(
                        owner_wallet_address=a,
                        tron_api_key=api_key,
                        session=session,
                    )
                    await self._upsert_balances_to_db_raw(
                        wallet_address=a,
                        balances_raw={TRON_NATIVE_TRX_CACHE_KEY: sun},
                    )
                    await self._redis.setex(
                        rkey,
                        _CACHE_TTL_SEC,
                        json.dumps(sun, ensure_ascii=False),
                    )
                    result[a] = sun
                except Exception:
                    result[a] = await _native_db_fallback_to_cache(a)

        return result


__all__ = [
    "BalancesService",
    "TRON_NATIVE_SYMBOL",
    "TRON_NATIVE_TRX_CACHE_KEY",
    "collateral_contract_addresses_for_network",
]