"""
FastAPI Depends: БД, Redis, Settings, NodeRepository.
Использование через Annotated в сигнатурах эндпоинтов.
"""
from typing import Annotated, AsyncGenerator

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from repos.node import NodeRepository
from settings import Settings


def get_settings() -> Settings:
    """Возвращает настройки приложения (из env)."""
    return Settings()


async def get_redis(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[Redis, None]:
    """Отдаёт клиент Redis на запрос; после ответа соединение закрывается."""
    client = Redis.from_url(settings.redis.url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


# Annotated-алиасы для эндпоинтов (избавляет от явного Depends в каждом роуте)
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
AppSettings = Annotated[Settings, Depends(get_settings)]


__all__ = [
    "get_db",
    "get_redis",
    "get_settings",
    "get_node_repo",
    "DbSession",
    "RedisClient",
    "AppSettings",
]
