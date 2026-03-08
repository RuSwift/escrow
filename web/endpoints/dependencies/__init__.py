"""
FastAPI Depends: БД, Redis, Settings, NodeRepository, текущий пользователь (Web3/TRON).
Использование через Annotated в сигнатурах эндпоинтов.
"""
from typing import Annotated, AsyncGenerator, Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import get_user_did
from db import get_db
from repos.node import NodeRepository
from services.billing import BillingService
from services.node import NodeService
from services.tron_auth import TronAuth
from services.wallet_user import WalletUserService
from services.web3_auth import Web3Auth
from settings import Settings

security = HTTPBearer()


class UserInfo(BaseModel):
    """Информация о текущем пользователе."""

    space: Literal["web3", "tron"] = Field(
        ..., description="Пространство авторизации: web3 (Ethereum) или tron"
    )
    wallet_address: str = Field(
        ..., description="Адрес кошелька пользователя"
    )
    did: str = Field(
        ..., description="DID в формате did:method:address"
    )


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


def get_billing_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> BillingService:
    """BillingService для эндпоинтов profile (история биллинга)."""
    return BillingService(session=db, redis=redis, settings=settings)


WalletUserServiceDep = Annotated[WalletUserService, Depends(get_wallet_user_service)]
BillingServiceDep = Annotated[BillingService, Depends(get_billing_service)]
NodeServiceDep = Annotated[NodeService, Depends(get_node_service)]
Web3AuthDep = Annotated[Web3Auth, Depends(get_web3_auth)]
TronAuthDep = Annotated[TronAuth, Depends(get_tron_auth)]


async def get_current_web3_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    web3_auth: Web3Auth = Depends(get_web3_auth),
) -> UserInfo:
    """Зависимость: текущий пользователь из JWT (Ethereum)."""
    token = credentials.credentials
    payload = web3_auth.verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    wallet_address = payload.get("wallet_address")
    if not wallet_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    did = get_user_did(wallet_address, "web3")
    return UserInfo(space="web3", wallet_address=wallet_address, did=did)


async def get_current_tron_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    tron_auth: TronAuth = Depends(get_tron_auth),
) -> UserInfo:
    """Зависимость: текущий TRON-пользователь из JWT."""
    token = credentials.credentials
    payload = tron_auth.verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    wallet_address = payload.get("wallet_address")
    if not wallet_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    if payload.get("blockchain") != "tron":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: not a TRON token",
        )
    did = get_user_did(wallet_address, "tron")
    return UserInfo(space="tron", wallet_address=wallet_address, did=did)


CurrentWeb3User = Annotated[UserInfo, Depends(get_current_web3_user)]
CurrentTronUser = Annotated[UserInfo, Depends(get_current_tron_user)]


__all__ = [
    "get_db",
    "get_redis",
    "get_settings",
    "get_wallet_user_service",
    "get_billing_service",
    "get_node_service",
    "get_web3_auth",
    "get_tron_auth",
    "get_current_web3_user",
    "get_current_tron_user",
    "security",
    "UserInfo",
    "DbSession",
    "RedisClient",
    "AppSettings",
    "WalletUserServiceDep",
    "BillingServiceDep",
    "NodeServiceDep",
    "Web3AuthDep",
    "TronAuthDep",
    "CurrentWeb3User",
    "CurrentTronUser",
]
