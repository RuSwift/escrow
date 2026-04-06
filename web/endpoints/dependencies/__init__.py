"""
FastAPI Depends: БД, Redis, Settings, NodeRepository, текущий пользователь (Web3/TRON).
Использование через Annotated в сигнатурах эндпоинтов.
"""
import jwt
from typing import Annotated, AsyncGenerator, List, Literal, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.utils import get_user_did
from db import get_db
from db.models import AdminUser
from repos.bestchange import BestchangeYamlRepository, PaymentFormsYamlRepository
from repos.dashboard import DashboardStateRepository
from repos.guarantor_direction import GuarantorDirectionRepository
from repos.node import NodeRepository
from services.admin import AdminService
from services.arbiter import ArbiterService
from services.balances import BalancesService
from services.billing import BillingService
from services.node import NodeService
from services.tron_auth import TronAuth
from services.wallet import WalletService
from services.invite import InviteService
from services.exchange_wallets import ExchangeWalletService
from services.order import OrderService
from services.guarantor import GuarantorService
from services.space import SpaceService
from services.dashboard import DashboardService
from services.wallet_user import WalletUserService
from services.web3_auth import Web3Auth
from settings import Settings

security = HTTPBearer()
optional_bearer = HTTPBearer(auto_error=False)
ADMIN_JWT_ALGORITHM = "HS256"
ADMIN_TOKEN_COOKIE = "admin_token"
MAIN_AUTH_TOKEN_COOKIE = "main_auth_token"


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

    standard: Literal["web3", "tron"] = Field(
        ..., description="Стандарт/сеть авторизации: web3 (Ethereum) или tron"
    )
    wallet_address: str = Field(
        ..., description="Адрес кошелька пользователя"
    )
    did: str = Field(
        ..., description="DID в формате did:method:address"
    )
    space_nickname: Optional[str] = Field(
        default=None,
        description="Текущий space (nickname) контекста приложения",
    )
    spaces: Optional[List[str]] = Field(
        default=None,
        description="Список доступных space (nickname) для этого кошелька",
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


def get_space_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> SpaceService:
    """SpaceService для роли в спейсе и управления участниками."""
    return SpaceService(session=db, redis=redis, settings=settings)


def get_guarantor_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> GuarantorService:
    """Панель гаранта: профиль и направления."""
    return GuarantorService(session=db, redis=redis, settings=settings)


def get_exchange_wallet_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> ExchangeWalletService:
    """Реквизиты Ramp (Wallet external | multisig) в разрезе space."""
    return ExchangeWalletService(session=db, redis=redis, settings=settings)


def get_order_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> OrderService:
    """Ордера дашборда (эфемерные и др.)."""
    return OrderService(session=db, redis=redis, settings=settings)


def get_balances_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> BalancesService:
    """Балансы TRC-20 (TronGrid + кеш)."""
    return BalancesService(session=db, redis=redis, settings=settings)


def get_invite_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> InviteService:
    """InviteService для создания и резолва invite-токенов."""
    return InviteService(session=db, redis=redis, settings=settings)


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


def get_wallet_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> WalletService:
    """WalletService для эндпоинтов кошельков."""
    return WalletService(session=db, redis=redis, settings=settings.settings)


def get_arbiter_service(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> ArbiterService:
    """ArbiterService для эндпоинтов арбитра."""
    return ArbiterService(session=db, redis=redis, settings=settings.settings)


def get_bestchange_repository(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> BestchangeYamlRepository:
    """BestchangeYamlRepository: снимок bc.yaml в БД, кеш Redis."""
    return BestchangeYamlRepository(session=db, redis=redis, settings=settings.settings)


def get_payment_forms_repository(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> PaymentFormsYamlRepository:
    """PaymentFormsYamlRepository: fields по payment_code из forms.yaml, кеш Redis."""
    return PaymentFormsYamlRepository(session=db, redis=redis, settings=settings.settings)


def get_dashboard_service(
    redis: RedisClient,
    settings: AppSettings,
) -> DashboardService:
    """DashboardService: спотовые котировки (без BestChange)."""
    return DashboardService(redis=redis, settings=settings.settings)


def get_dashboard_state_repository(db: DbSession) -> DashboardStateRepository:
    """Снимок котировок дашборда в ``dashboard_state`` (id=1)."""
    return DashboardStateRepository(session=db)


def get_guarantor_direction_repository(
    db: DbSession,
    redis: RedisClient,
    settings: AppSettings,
) -> GuarantorDirectionRepository:
    """Направления гаранта по space (таблица ``guarantor_directions``)."""
    return GuarantorDirectionRepository(session=db, redis=redis, settings=settings.settings)


async def get_admin(
    request: Request,
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(optional_bearer),
    ],
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
    settings: AppSettings,
) -> Optional[AdminUser]:
    """
    Опциональная зависимость: текущий авторизованный админ или None.
    Читает JWT из Authorization: Bearer или из cookie admin_token; payload должен содержать "admin": True.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif request.cookies.get(ADMIN_TOKEN_COOKIE):
        token = request.cookies.get(ADMIN_TOKEN_COOKIE)
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
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
SpaceServiceDep = Annotated[SpaceService, Depends(get_space_service)]
GuarantorServiceDep = Annotated[GuarantorService, Depends(get_guarantor_service)]
ExchangeWalletServiceDep = Annotated[
    ExchangeWalletService, Depends(get_exchange_wallet_service)
]
BalancesServiceDep = Annotated[BalancesService, Depends(get_balances_service)]
InviteServiceDep = Annotated[InviteService, Depends(get_invite_service)]
WalletServiceDep = Annotated[WalletService, Depends(get_wallet_service)]
ArbiterServiceDep = Annotated[ArbiterService, Depends(get_arbiter_service)]
BestchangeRepoDep = Annotated[BestchangeYamlRepository, Depends(get_bestchange_repository)]
PaymentFormsRepoDep = Annotated[
    PaymentFormsYamlRepository,
    Depends(get_payment_forms_repository),
]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
DashboardStateRepoDep = Annotated[
    DashboardStateRepository,
    Depends(get_dashboard_state_repository),
]
GuarantorDirectionRepoDep = Annotated[
    GuarantorDirectionRepository,
    Depends(get_guarantor_direction_repository),
]
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
    return UserInfo(standard="web3", wallet_address=wallet_address, did=did)


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
    return UserInfo(standard="tron", wallet_address=wallet_address, did=did)


async def get_current_wallet_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
    tron_auth: TronAuth = Depends(get_tron_auth),
    web3_auth: Web3Auth = Depends(get_web3_auth),
) -> UserInfo:
    """
    Текущий пользователь main app: JWT TRON или Web3.
    Токен — Authorization: Bearer или cookie ``main_auth_token`` (как GET /{space}).
    """
    token = credentials.credentials if credentials else None
    if not token:
        token = request.cookies.get(MAIN_AUTH_TOKEN_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = tron_auth.verify_jwt_token(token)
    if payload:
        wallet_address = payload.get("wallet_address")
        if wallet_address and payload.get("blockchain") == "tron":
            return UserInfo(
                standard="tron",
                wallet_address=wallet_address,
                did=get_user_did(wallet_address, "tron"),
            )
    payload = web3_auth.verify_jwt_token(token)
    if payload:
        wallet_address = payload.get("wallet_address")
        if wallet_address:
            return UserInfo(
                standard="web3",
                wallet_address=wallet_address,
                did=get_user_did(wallet_address, "web3"),
            )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )


CurrentWeb3User = Annotated[UserInfo, Depends(get_current_web3_user)]
CurrentTronUser = Annotated[UserInfo, Depends(get_current_tron_user)]
CurrentWalletUser = Annotated[UserInfo, Depends(get_current_wallet_user)]


async def get_required_wallet_address_for_space(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
    tron_auth: TronAuth = Depends(get_tron_auth),
    web3_auth: Web3Auth = Depends(get_web3_auth),
) -> str:
    """
    Для main app GET /{space}: возвращает wallet_address из JWT (TRON или Web3).
    Токен берётся из Authorization: Bearer или из cookie main_auth_token.
    Raises 401 если токен отсутствует или невалиден.
    """
    token = credentials.credentials if credentials else None
    if not token:
        token = request.cookies.get(MAIN_AUTH_TOKEN_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = tron_auth.verify_jwt_token(token)
    if not payload:
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
    return wallet_address


__all__ = [
    "MAIN_AUTH_TOKEN_COOKIE",
    "get_db",
    "get_redis",
    "get_settings",
    "get_wallet_user_service",
    "get_space_service",
    "get_guarantor_service",
    "get_exchange_wallet_service",
    "get_order_service",
    "get_balances_service",
    "BalancesServiceDep",
    "get_invite_service",
    "get_billing_service",
    "get_node_service",
    "get_admin_service",
    "get_bestchange_repository",
    "get_payment_forms_repository",
    "get_dashboard_service",
    "get_dashboard_state_repository",
    "get_guarantor_direction_repository",
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
    "SpaceServiceDep",
    "GuarantorServiceDep",
    "ExchangeWalletServiceDep",
    "InviteServiceDep",
    "ArbiterServiceDep",
    "BestchangeRepoDep",
    "PaymentFormsRepoDep",
    "DashboardServiceDep",
    "DashboardStateRepoDep",
    "GuarantorDirectionRepoDep",
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
    "CurrentWalletUser",
    "get_current_wallet_user",
    "get_required_wallet_address_for_space",
]
