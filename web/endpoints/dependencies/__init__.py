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
from services.node import NodeService
from services.tron_auth import TronAuth
from services.wallet_user import WalletUserService
from services.web3_auth import Web3Auth
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


def get_wallet_user_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> WalletUserService:
    """WalletUserService для эндпоинтов auth и profile."""
    return WalletUserService(session=db, redis=redis, settings=settings)


def get_web3_auth(redis: RedisClient, settings: AppSettings) -> Web3Auth:
    """Web3Auth для Ethereum-авторизации."""
    return Web3Auth(redis=redis, settings=settings)


def get_tron_auth(redis: RedisClient, settings: AppSettings) -> TronAuth:
    """TronAuth для TRON-авторизации."""
    return TronAuth(redis=redis, settings=settings)


def get_node_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> NodeService:
    """NodeService для эндпоинтов ноды."""
    return NodeService(session=db, redis=redis, settings=settings)


WalletUserServiceDep = Annotated[WalletUserService, Depends(get_wallet_user_service)]
NodeServiceDep = Annotated[NodeService, Depends(get_node_service)]
Web3AuthDep = Annotated[Web3Auth, Depends(get_web3_auth)]
TronAuthDep = Annotated[TronAuth, Depends(get_tron_auth)]


__all__ = [
    "get_db",
    "get_redis",
    "get_settings",
    "get_wallet_user_service",
    "get_node_service",
    "get_web3_auth",
    "get_tron_auth",
    "DbSession",
    "RedisClient",
    "AppSettings",
    "WalletUserServiceDep",
    "NodeServiceDep",
    "Web3AuthDep",
    "TronAuthDep",
]
