"""
Web3 (Ethereum) auth: nonce, signature verification, JWT.
Ориентир: garantex routers/auth.py (Ethereum branch).
"""
import secrets
import time
from typing import Any, Optional

import jwt
from eth_account import Account
from eth_account.messages import encode_defunct
from redis.asyncio import Redis

from settings import Settings

NONCE_PREFIX = "auth:nonce:eth:"
NONCE_TTL_SEC = 300
JWT_ALGORITHM = "HS256"
JWT_EXP_SEC = 7 * 24 * 3600  # 7 days


class Web3Auth:
    """Nonce, verify signature, JWT для Ethereum-кошельков."""

    def __init__(self, redis: Redis, settings: Settings):
        self._redis = redis
        self._settings = settings

    async def get_nonce(self, wallet_address: str) -> str:
        """Генерирует и сохраняет nonce для адреса."""
        nonce = secrets.token_hex(16)
        key = f"{NONCE_PREFIX}{wallet_address.lower()}"
        await self._redis.setex(key, NONCE_TTL_SEC, nonce)
        return nonce

    def verify_signature(
        self,
        wallet_address: str,
        signature: str,
        message: Optional[str] = None,
    ) -> bool:
        """
        Проверяет подпись сообщения. signature — hex (с или без 0x).
        message — то, что подписывал пользователь; если None, не проверяем (только формат подписи).
        """
        if not wallet_address or not signature:
            return False
        try:
            sig_bytes = bytes.fromhex(signature.removeprefix("0x"))
            if len(sig_bytes) != 65:
                return False
            if message is None:
                return True
            message_hash = encode_defunct(text=message)
            recovered = Account.recover_message(message_hash, signature=sig_bytes)
            return recovered.lower() == wallet_address.strip().lower()
        except Exception:
            return False

    def generate_jwt_token(self, wallet_address: str) -> str:
        """Выдаёт JWT с payload wallet_address (и exp)."""
        secret = self._settings.secret.get_secret_value()
        payload: dict[str, Any] = {
            "wallet_address": wallet_address.strip().lower(),
            "blockchain": "ethereum",
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
