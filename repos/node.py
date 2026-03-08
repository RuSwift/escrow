import logging
from typing import Optional, Union
from datetime import datetime

from pydantic import Field
from sqlalchemy import select, update, insert, exists
from sqlalchemy.sql import literal
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from didcomm.crypto import EthKeyPair, KeyPair as BaseKeyPair
from core.entities import BaseResource
from db.models import NodeSettings
from repos.base import BaseRepository
from settings import Settings

logger = logging.getLogger(__name__)


class NodeResource(BaseResource):
    """Resource-схемы для операций с настройками ноды."""

    class Create(BaseResource.Create):
        key_type: str = Field(default="mnemonic", description="mnemonic | pem")
        ethereum_address: Optional[str] = Field(default=None, max_length=42)
        did: Optional[str] = Field(default=None, max_length=255, description="Peer DID (set at init)")
        service_endpoint: Optional[str] = Field(default=None, max_length=255)

    class Patch(BaseResource.Patch):
        service_endpoint: Optional[str] = Field(default=None, max_length=255)
        is_active: Optional[bool] = None

    class Get(BaseResource.Get):
        id: int
        key_type: str
        ethereum_address: Optional[str] = None
        did: Optional[str] = None
        service_endpoint: Optional[str] = None
        is_active: bool
        created_at: datetime
        updated_at: datetime


def _model_to_get(model: NodeSettings) -> NodeResource.Get:
    """Преобразует модель NodeSettings в NodeResource.Get."""
    return NodeResource.Get(
        id=model.id,
        key_type=model.key_type,
        ethereum_address=model.ethereum_address,
        did=getattr(model, "did", None),
        service_endpoint=model.service_endpoint,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class NodeRepository(BaseRepository):
    """
    Репозиторий для управления настройками ноды и криптографическими ключами.
    Интерфейс построен на NodeResource (Create, Update, Patch, Get).
    """

    async def get(self) -> Optional[NodeResource.Get]:
        """
        Получает активную запись настроек ноды в виде NodeResource.Get.
        """
        stmt = select(NodeSettings).where(NodeSettings.is_active == True)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return _model_to_get(model) if model else None

    async def create(
        self,
        data: NodeResource.Create,
        *,
        mnemonic: Optional[str] = None,
        pem: Optional[str] = None,
    ) -> NodeResource.Get:
        """
        Создает новую запись настроек ноды из NodeResource.Create (атомарная вставка).
        Мнемоника и PEM передаются в открытом виде; репозиторий шифрует их перед сохранением.
        Raises:
            ValueError: если уже существует активная запись ноды.
        """
        encrypted_mnemonic = self.encrypt_data(mnemonic) if mnemonic else None
        encrypted_pem = self.encrypt_data(pem) if pem else None
        no_active = ~exists(select(1).where(NodeSettings.is_active == True))
        stmt = insert(NodeSettings).from_select(
            [
                NodeSettings.encrypted_mnemonic,
                NodeSettings.encrypted_pem,
                NodeSettings.key_type,
                NodeSettings.ethereum_address,
                NodeSettings.did,
                NodeSettings.service_endpoint,
                NodeSettings.is_active,
            ],
            select(
                literal(encrypted_mnemonic),
                literal(encrypted_pem),
                literal(data.key_type),
                literal(data.ethereum_address),
                literal(data.did),
                literal(data.service_endpoint),
                literal(True),
            ).where(no_active),
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise ValueError("Нода инициализируется только один раз")
        await self._session.flush()
        out = await self.get()
        assert out is not None, "insert succeeded but get() returned None"
        return out

    async def get_plain_mnemonic(self) -> Optional[str]:
        """
        Возвращает расшифрованную мнемоническую фразу активной ноды или None.
        """
        stmt = select(NodeSettings.encrypted_mnemonic).where(
            NodeSettings.is_active == True,
            NodeSettings.encrypted_mnemonic.isnot(None),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self.decrypt_data(row) if row else None

    async def get_plain_pem(self) -> Optional[str]:
        """
        Возвращает расшифрованный PEM активной ноды или None.
        """
        stmt = select(NodeSettings.encrypted_pem).where(
            NodeSettings.is_active == True,
            NodeSettings.encrypted_pem.isnot(None),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self.decrypt_data(row) if row else None

    async def get_active_keypair(
        self,
    ) -> Optional[Union[EthKeyPair, BaseKeyPair]]:
        """
        Возвращает ключевую пару активной ноды (расшифровывает и собирает EthKeyPair или KeyPair).
        """
        stmt = select(
            NodeSettings.key_type,
            NodeSettings.encrypted_mnemonic,
            NodeSettings.encrypted_pem,
        ).where(NodeSettings.is_active == True)
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if not row:
            return None
        key_type, encrypted_mnemonic, encrypted_pem = row
        if key_type == "mnemonic" and encrypted_mnemonic:
            plain = self.decrypt_data(encrypted_mnemonic)
            return EthKeyPair.from_mnemonic(plain)
        if key_type == "pem" and encrypted_pem:
            plain = self.decrypt_data(encrypted_pem)
            return BaseKeyPair.from_pem(plain)
        return None

    async def patch_active(self, data: NodeResource.Patch) -> Optional[NodeResource.Get]:
        """
        Частично обновляет активную запись (только явно переданные поля).
        """
        payload = data.model_dump(exclude_unset=True)
        allowed = {"service_endpoint", "is_active"}
        values = {k: v for k, v in payload.items() if k in allowed}
        if not values:
            return await self.get()
        stmt = (
            update(NodeSettings)
            .where(NodeSettings.is_active == True)
            .values(**values)
        )
        await self._session.execute(stmt)
        return await self.get()

