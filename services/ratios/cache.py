"""
Адаптер кэша для движков котировок: Redis с namespace-префиксом, get/set с JSON.
"""

import json
from typing import Any, Optional

from redis.asyncio import Redis


class RatioCacheAdapter:
    """
    Кэш котировок: ключи с префиксом ratios:{engine_name}:, значения — JSON.
    Интерфейс: get(key) -> dict | None, set(key, value, ttl).
    """

    def __init__(self, redis: Redis, namespace: str):
        """
        :param redis: клиент Redis (decode_responses=True)
        :param namespace: префикс ключей, например "ForexEngine" или "ratios:ForexEngine"
        """
        self._redis = redis
        self._prefix = f"ratios:{namespace}:"

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Optional[dict]:
        """Получить значение по ключу (десериализация JSON)."""
        full = self._key(key)
        raw = await self._redis.get(full)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Сохранить значение с TTL (секунды). value должен быть JSON-сериализуемым."""
        full = self._key(key)
        payload = json.dumps(value, default=str)
        await self._redis.setex(full, ttl, payload)
