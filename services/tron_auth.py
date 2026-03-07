"""
TRON auth: nonce, signature verification, JWT.
Ориентир: garantex routers/auth.py (TRON branch).
"""
import secrets
import time
from typing import Any, Optional

import jwt
from redis.asyncio import Redis

from settings import Settings

try:
    from tronpy.keys import Signature
except ImportError:
    Signature = None  # type: ignore

NONCE_PREFIX = "auth:nonce:tron:"
NONCE_TTL_SEC = 300
JWT_ALGORITHM = "HS256"
JWT_EXP_SEC = 7 * 24 * 3600  # 7 days
TRON_ADDRESS_LEN = 34


def _validate_tron_address_static(address: str) -> bool:
    """Проверка формата: начинается с T, длина 34, base58."""
    if not address or len(address) != TRON_ADDRESS_LEN or not address.startswith("T"):
        return False
    try:
        from base58 import b58decode
        b58decode(address)
        return True
    except Exception:
        return False


class TronAuth:
    """Nonce, verify signature, JWT для TRON-кошельков."""

    def __init__(self, redis: Redis, settings: Settings):
        self._redis = redis
        self._settings = settings

    @staticmethod
    def validate_tron_address(address: str) -> bool:
        """Проверяет формат TRON-адреса (T + 34 символа base58)."""
        return _validate_tron_address_static((address or "").strip())

    async def get_nonce(self, wallet_address: str) -> str:
        """Генерирует и сохраняет nonce для адреса."""
        nonce = secrets.token_hex(16)
        key = f"{NONCE_PREFIX}{wallet_address.strip()}"
        await self._redis.setex(key, NONCE_TTL_SEC, nonce)
        return nonce

    def verify_signature(
        self,
        wallet_address: str,
        signature: str,
        message: Optional[str] = None,
    ) -> bool:
        """
        Проверяет подпись (TronLink personal_sign). signature — hex.
        message — то, что подписывал пользователь.
        """
        if not wallet_address or not signature or not message:
            return False
        if Signature is None:
            return False
        try:
            sig_bytes = bytes.fromhex(signature.removeprefix("0x"))
            if len(sig_bytes) != 65:
                return False
            msg_bytes = message.encode("utf-8")
            sig_obj = Signature(sig_bytes)
            pub_key = sig_obj.recover_public_key_from_msg(msg_bytes)
            recovered = pub_key.to_base58check_address()
            return recovered == wallet_address.strip()
        except Exception:
            return False

    def generate_jwt_token(self, wallet_address: str) -> str:
        """Выдаёт JWT с payload wallet_address, blockchain=tron."""
        secret = self._settings.secret.get_secret_value()
        payload: dict[str, Any] = {
            "wallet_address": wallet_address.strip(),
            "blockchain": "tron",
            "exp": int(time.time()) + JWT_EXP_SEC,
        }
        return jwt.encode(
            payload,
            secret,
            algorithm=JWT_ALGORITHM,
        )

    def verify_jwt_token(self, token: str) -> Optional[dict]:
        """Верифицирует JWT и возвращает payload или None."""
        try:
            secret = self._settings.secret.get_secret_value()
            return jwt.decode(
                token,
                secret,
                algorithms=[JWT_ALGORITHM],
            )
        except Exception:
            return None
