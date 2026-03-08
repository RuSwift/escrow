"""
FastAPI Depends: БД, Redis, Settings, NodeRepository, текущий пользователь (Web3/TRON).
Использование через Annotated в сигнатурах эндпоинтов.
"""
import jwt
from typing import Annotated, AsyncGenerator, Literal, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import get_user_did
from db import get_db
from db.models import AdminUser
from repos.node import NodeRepository
from services.admin import AdminService
from services.billing import BillingService
from services.node import NodeService
from services.tron_auth import TronAuth
from services.wallet_user import WalletUserService
from services.web3_auth import Web3Auth
from settings import Settings

security = HTTPBearer()
optional_bearer = HTTPBearer(auto_error=False)
ADMIN_JWT_ALGORITHM = "HS256"


class ResolvedSettings:
    """
    Settings resolved in two stages: first from env, then from DB.
    Delegates attribute access to .settings for compatibility.
    """
    def __init__(
        self,
        settings: Settings,
        has_key: bool,
        is_admin_configured: bool,
        is_node_initialized: bool,
    ):
        self.settings = settings
        self.has_key = has_key
        self.is_admin_configured = is_admin_configured
        self.is_node_initialized = is_node_initialized

    def __getattr__(self, name: str):
        return getattr(self.settings, name)


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


async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResolvedSettings:
    """
    Настройки в два этапа: сначала env, затем БД.
    Возвращает ResolvedSettings (has_key, is_admin_configured, is_node_initialized из env или БД).
    """
    settings = Settings()
    redis = Redis.from_url(settings.redis.url, decode_responses=True)
    try:
        node_repo = NodeRepository(session=db, redis=redis, settings=settings)
        admin_svc = AdminService(session=db, redis=redis, settings=settings)
        node = await node_repo.get()
        has_key_env = bool(
            settings.mnemonic.phrase
            or settings.mnemonic.encrypted_phrase
            or settings.pem
        )
        has_keypair_from_db = (
            (node is not None)
            and (await node_repo.get_active_keypair() is not None)
        )
        has_key = has_key_env or has_keypair_from_db
        is_admin = settings.admin.is_configured or await admin_svc.is_admin_configured()
        service_endpoint = (node.service_endpoint or "").strip() if node else ""
        is_node_initialized = has_key and is_admin and bool(service_endpoint)
        return ResolvedSettings(
            settings=settings,
            has_key=has_key,
            is_admin_configured=is_admin,
            is_node_initialized=is_node_initialized,
        )
    finally:
        await redis.aclose()


async def get_redis(
    settings: ResolvedSettings = Depends(get_settings),
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
AppSettings = Annotated[ResolvedSettings, Depends(get_settings)]


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


def get_admin_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> AdminService:
    """AdminService для эндпоинтов админки."""
    return AdminService(session=db, redis=redis, settings=settings.settings)


async def get_admin(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(optional_bearer),
    ],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    settings: AppSettings,
) -> Optional[AdminUser]:
    """
    Опциональная зависимость: текущий авторизованный админ или None.
    Читает JWT из Authorization: Bearer; payload должен содержать "admin": True.
    """
    if not credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret.get_secret_value(),
            algorithms=[ADMIN_JWT_ALGORITHM],
        )
    except Exception:
        return None
    if not payload.get("admin"):
        return None
    admin = await admin_service.get_admin()
    return admin


async def get_require_admin(
    admin: Annotated[Optional[AdminUser], Depends(get_admin)],
) -> AdminUser:
    """Зависимость: текущий админ или 401."""
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
        )
    return admin


WalletUserServiceDep = Annotated[WalletUserService, Depends(get_wallet_user_service)]
BillingServiceDep = Annotated[BillingService, Depends(get_billing_service)]
NodeServiceDep = Annotated[NodeService, Depends(get_node_service)]
AdminServiceDep = Annotated[AdminService, Depends(get_admin_service)]
AdminDepends = Annotated[Optional[AdminUser], Depends(get_admin)]
RequireAdminDepends = Annotated[AdminUser, Depends(get_require_admin)]
Web3AuthDep = Annotated[Web3Auth, Depends(get_web3_auth)]
TronAuthDep = Annotated[TronAuth, Depends(get_tron_auth)]


async def get_node_keypair_optional(
    node_service: NodeServiceDep,
):
    """Зависимость: ключ ноды или None (для публичного GET /endpoint)."""
    return await node_service.get_active_keypair()


async def get_node_keypair_required(
    node_service: NodeServiceDep,
):
    """Зависимость: ключ ноды для DIDComm; 503, если ключа нет (для POST /endpoint)."""
    keypair = await node_service.get_active_keypair()
    if keypair is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Node key not available",
        )
    return keypair


NodeKeypairOptionalDep = Annotated[
    object, Depends(get_node_keypair_optional)
]  # Optional[Union[EthKeyPair, BaseKeyPair]]
NodeKeypairRequiredDep = Annotated[object, Depends(get_node_keypair_required)]


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
    "get_admin_service",
    "get_web3_auth",
    "get_tron_auth",
    "get_current_web3_user",
    "get_current_tron_user",
    "security",
    "UserInfo",
    "ResolvedSettings",
    "DbSession",
    "RedisClient",
    "AppSettings",
    "WalletUserServiceDep",
    "BillingServiceDep",
    "NodeServiceDep",
    "AdminServiceDep",
    "AdminDepends",
    "RequireAdminDepends",
    "get_admin",
    "get_require_admin",
    "optional_bearer",
    "Web3AuthDep",
    "TronAuthDep",
    "get_node_keypair_optional",
    "get_node_keypair_required",
    "NodeKeypairOptionalDep",
    "NodeKeypairRequiredDep",
    "CurrentWeb3User",
    "CurrentTronUser",
]
