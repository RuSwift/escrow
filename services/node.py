"""
Node service для инициализации и управления ключами ноды.
Использует NodeRepository для работы с БД и шифрованием.
"""
import logging
from typing import Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from didcomm.crypto import EthCrypto, EthKeyPair, KeyPair as BaseKeyPair
from didcomm.did import create_peer_did_from_keypair
from i18n import _
from repos.node import NodeRepository, NodeResource
from settings import Settings

logger = logging.getLogger(__name__)


# --- Response Schemas (Pydantic), используемые сервисом ---


class NodeInitResponseSchema(BaseModel):
    """Ответ после успешной инициализации ноды (mnemonic или PEM)."""

    did: str = Field(..., description="Peer DID ноды")
    address: Optional[str] = Field(None, max_length=42, description="Ethereum-адрес (для mnemonic/secp256k1)")
    key_type: Literal["mnemonic", "pem"] = Field(..., description="Тип ключа")
    public_key: str = Field(..., description="Публичный ключ в hex")
    did_document: Dict[str, Any] = Field(..., description="DID Document (JSON)")


class ServiceEndpointResponseSchema(BaseModel):
    """Ответ с текущим service_endpoint."""

    service_endpoint: Optional[str] = Field(None, max_length=255, description="URL эндпоинта или None")


class NodeService:
    """Сервис для управления инициализацией ноды и криптографическими ключами."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ):
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = NodeRepository(session=session, redis=redis, settings=settings)

    async def init_from_mnemonic(self, mnemonic: str) -> NodeInitResponseSchema:
        """
        Инициализирует ноду из мнемонической фразы.

        Args:
            mnemonic: Мнемоническая фраза.

        Returns:
            NodeInitResponseSchema с данными созданного ключа и DID.

        Raises:
            ValueError: Если мнемоника невалидна или нода уже инициализирована.
        """
        if await self.has_key():
            raise ValueError(_("errors.node_already_init"))

        if not EthCrypto.validate_mnemonic(mnemonic):
            raise ValueError(_("errors.invalid_mnemonic"))

        keypair = EthKeyPair.from_mnemonic(mnemonic)
        ethereum_address = keypair.address
        did_obj = create_peer_did_from_keypair(keypair)

        await self._repo.create(
            NodeResource.Create(
                key_type="mnemonic",
                ethereum_address=ethereum_address,
            ),
            mnemonic=mnemonic,
        )
        await self._session.commit()

        node = await self._repo.get()
        logger.critical(
            "NodeSettings record created in database: id=%d, key_type=mnemonic, ethereum_address=%s, did=%s",
            node.id if node else 0,
            ethereum_address or "None",
            did_obj.did,
        )

        return NodeInitResponseSchema(
            did=did_obj.did,
            address=ethereum_address,
            key_type="mnemonic",
            public_key=keypair.public_key.hex(),
            did_document=did_obj.to_dict(),
        )

    async def init_from_pem(
        self,
        pem_data: str,
        password: Optional[str] = None,
    ) -> NodeInitResponseSchema:
        """
        Инициализирует ноду из PEM ключа.

        Args:
            pem_data: PEM данные ключа.
            password: Пароль для расшифровки PEM (опционально).

        Returns:
            NodeInitResponseSchema с данными созданного ключа и DID.

        Raises:
            ValueError: Если PEM невалиден или нода уже инициализирована.
        """
        if await self.has_key():
            raise ValueError(_("errors.node_already_init"))

        pem_upper = pem_data.upper()
        has_private_marker = (
            "BEGIN PRIVATE KEY" in pem_upper
            or "BEGIN RSA PRIVATE KEY" in pem_upper
            or "BEGIN EC PRIVATE KEY" in pem_upper
            or "BEGIN ENCRYPTED PRIVATE KEY" in pem_upper
        )
        if not has_private_marker:
            raise ValueError(_("errors.pem_no_private_key"))

        password_bytes = password.encode("utf-8") if password else None
        try:
            keypair = BaseKeyPair.from_pem(pem_data, password_bytes)
        except ValueError as e:
            raise ValueError(_("errors.pem_invalid_private_key", detail=str(e))) from e

        did_obj = create_peer_did_from_keypair(keypair)
        ethereum_address = keypair.address if isinstance(keypair, EthKeyPair) else None

        await self._repo.create(
            NodeResource.Create(
                key_type="pem",
                ethereum_address=ethereum_address,
            ),
            pem=pem_data,
        )
        await self._session.commit()

        node = await self._repo.get()
        logger.critical(
            "NodeSettings record created in database: id=%d, key_type=pem, ethereum_address=%s, did=%s",
            node.id if node else 0,
            ethereum_address or "None",
            did_obj.did,
        )

        return NodeInitResponseSchema(
            did=did_obj.did,
            address=ethereum_address,
            key_type="pem",
            public_key=keypair.public_key.hex(),
            did_document=did_obj.to_dict(),
        )

    async def get_active_keypair(self) -> Optional[Union[EthKeyPair, BaseKeyPair]]:
        """
        Возвращает активную ключевую пару ноды.

        Returns:
            EthKeyPair, BaseKeyPair или None, если нода не инициализирована.
        """
        return await self._repo.get_active_keypair()

    async def has_key(self) -> bool:
        """Проверяет, существует ли ключ ноды (активная запись)."""
        return (await self._repo.get()) is not None

    async def is_node_initialized(self) -> bool:
        """
        Проверяет, полностью ли инициализирована нода:
        есть ключ, настроен админ (из env), задан service_endpoint.
        """
        if not await self.has_key():
            return False
        if not self._settings.is_admin_configured_from_env:
            return False
        node = await self._repo.get()
        if not node or not (node.service_endpoint or "").strip():
            return False
        return True

    async def set_service_endpoint(self, service_endpoint: str) -> bool:
        """
        Устанавливает service_endpoint для активной ноды.

        Returns:
            True если обновление выполнено, False если ноды нет.
        """
        updated = await self._repo.patch_active(
            NodeResource.Patch(service_endpoint=service_endpoint)
        )
        if updated is None:
            return False
        await self._session.commit()
        return True

    async def get_service_endpoint(self) -> Optional[str]:
        """Возвращает текущий service_endpoint активной ноды или None."""
        node = await self._repo.get()
        return node.service_endpoint if node else None

    async def is_service_endpoint_configured(self) -> bool:
        """Проверяет, что service_endpoint задан и не пустой."""
        endpoint = await self.get_service_endpoint()
        return bool(endpoint and endpoint.strip())

    async def get_service_endpoint_response(self) -> ServiceEndpointResponseSchema:
        """Возвращает текущий service_endpoint в виде Pydantic-схемы."""
        endpoint = await self.get_service_endpoint()
        return ServiceEndpointResponseSchema(service_endpoint=endpoint)


__all__ = [
    "NodeInitResponseSchema",
    "ServiceEndpointResponseSchema",
    "NodeService",
]
