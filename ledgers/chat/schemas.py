"""
Pydantic модели для хранения и передачи объектов сообщений в чате

Поддерживает:
- Текстовые сообщения
- Передачу файлов (кодируются в base64) + размеры файлов и имена
- Аудио/видео (кодируются в base64) + размеры файлов и имена
- Подписи текстовых сообщений или сообщений с файлами
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


def validate_did_format(v: str) -> str:
    """
    Универсальная валидация формата DID

    Поддерживаемые форматы:
    - did:tron:{address}
    - did:ethr:{address} (для Ethereum)
    - did:bitcoin:{address}
    - did:polkadot:{address} (для Polkadot/Substrate)

    Args:
        v: Строка для валидации

    Returns:
        Валидированная строка

    Raises:
        ValueError: Если формат DID невалиден
    """
    if not v:
        raise ValueError("DID cannot be empty")

    # Проверяем что строка начинается с "did:"
    if not v.startswith("did:"):
        raise ValueError(f"Invalid DID format: must start with 'did:' (got: {v})")

    # Разбиваем на части: did:{method}:{address}
    parts = v.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid DID format: expected 'did:method:address' (got: {v})")

    did_prefix, method, address = parts

    # Проверяем что первая часть - "did"
    if did_prefix != "did":
        raise ValueError(f"Invalid DID format: must start with 'did:' (got: {v})")

    # Проверяем что method не пустой
    if not method or not method.strip():
        raise ValueError(f"Invalid DID format: method cannot be empty (got: {v})")

    # Проверяем что address не пустой
    if not address or not address.strip():
        raise ValueError(f"Invalid DID format: address cannot be empty (got: {v})")

    return v


class MessageType(str, Enum):
    """Тип сообщения"""
    TEXT = "text"
    FILE = "file"
    AUDIO = "audio"
    VIDEO = "video"
    MIXED = "mixed"  # Текст + файлы/медиа
    REPLY = "reply"  # Ответ на сообщение
    DEAL = "deal"  # Индикация начала сделки
    SERVICE = "service"  # Служебное сообщение


class AttachmentType(str, Enum):
    """Тип вложения"""
    DOCUMENT = "document"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"


class MessageSignature(BaseModel):
    """Подпись сообщения"""
    signature: str = Field(..., description="Подпись в hex формате (начинается с 0x)")
    signer_address: str = Field(..., description="Адрес подписавшего (wallet address)")
    signed_at: datetime = Field(default_factory=datetime.utcnow, description="Время подписи")
    message_hash: Optional[str] = Field(None, description="Хеш подписанного сообщения (опционально)")

    @field_validator('signature')
    @classmethod
    def validate_signature_format(cls, v):
        """Проверка формата подписи"""
        if not v.startswith('0x'):
            raise ValueError("Signature must start with '0x'")
        if len(v) < 10:
            raise ValueError("Signature too short")
        return v


class FileAttachmentMetadata(BaseModel):
    """Метаданные файла БЕЗ данных (для списков сообщений)"""
    id: str = Field(..., description="Уникальный идентификатор вложения")
    type: AttachmentType = Field(..., description="Тип вложения: document, photo, video, audio")
    name: str = Field(..., description="Имя файла")
    size: int = Field(..., description="Размер файла в байтах")
    mime_type: str = Field(..., description="MIME тип файла (например, image/png, application/pdf)")
    thumbnail: Optional[str] = Field(None, description="Превью в base64 (для изображений/видео, небольшой размер)")
    download_url: Optional[str] = Field(None, description="URL для загрузки полного файла")

    @field_validator('size')
    @classmethod
    def validate_size(cls, v):
        """Проверка размера файла (максимум 50MB)"""
        max_size = 50 * 1024 * 1024  # 50MB
        if v > max_size:
            raise ValueError(f"File size exceeds maximum allowed size of {max_size} bytes")
        if v <= 0:
            raise ValueError("File size must be positive")
        return v


class FileAttachment(BaseModel):
    """Модель файлового вложения (полная версия с данными)"""
    id: str = Field(..., description="Уникальный идентификатор вложения")
    type: AttachmentType = Field(..., description="Тип вложения: document, photo, video, audio")
    name: str = Field(..., description="Имя файла")
    size: int = Field(..., description="Размер файла в байтах")
    mime_type: str = Field(..., description="MIME тип файла (например, image/png, application/pdf)")
    data: Optional[str] = Field(None, description="Содержимое файла в base64 (может быть пустым при постраничной загрузке)")
    download_url: Optional[str] = Field(None, description="URL для загрузки полного файла (когда data исключён)")
    thumbnail: Optional[str] = Field(None, description="Превью в base64 (для изображений/видео)")
    width: Optional[int] = Field(None, description="Ширина изображения/видео в пикселях")
    height: Optional[int] = Field(None, description="Высота изображения/видео в пикселях")

    @field_validator('size')
    @classmethod
    def validate_size(cls, v):
        """Проверка размера файла (максимум 50MB)"""
        max_size = 50 * 1024 * 1024  # 50MB
        if v > max_size:
            raise ValueError(f"File size exceeds maximum allowed size of {max_size} bytes")
        if v <= 0:
            raise ValueError("File size must be positive")
        return v

    @field_validator('data')
    @classmethod
    def validate_base64(cls, v):
        """Базовая проверка base64 формата (при наличии data)"""
        if v is None or v == "":
            return v
        try:
            import base64
            base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("Invalid base64 format")
        return v


class ChatMessage(BaseModel):
    """Универсальная модель сообщения чата"""

    # Базовые поля
    uuid: str = Field(..., description="UUID сообщения (уникальный идентификатор)")
    message_type: MessageType = Field(..., description="Тип сообщения")
    sender_id: str = Field(..., description="ID отправителя (DID или wallet address)")
    receiver_id: str = Field(..., description="ID получателя (DID или wallet address)")
    conversation_id: Optional[str] = Field(None, description="ID беседы (для группировки сообщений)")

    # Ссылка на Deal (для типа DEAL)
    deal_uid: Optional[str] = Field(None, description="UID сделки (base58 UUID) для типа DEAL")
    deal_label: Optional[str] = Field(None, description="Label сделки для типа DEAL")

    # Ответ на сообщение (для типа REPLY)
    reply_to_message_uuid: Optional[str] = Field(None, description="UUID сообщения, на которое ссылается ответ")

    # Текстовое содержимое
    text: Optional[str] = Field(None, description="Текст сообщения (может быть пустым для файловых сообщений)")

    # Вложения (файлы, аудио, видео)
    attachments: Optional[List[FileAttachment]] = Field(None, description="Список вложений")

    # Подпись
    signature: Optional[MessageSignature] = Field(None, description="Подпись сообщения (для текста или файлов)")

    # Метаданные
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Время отправки сообщения")
    status: Literal["sent", "delivered", "read", "failed"] = Field("sent", description="Статус доставки")
    edited_at: Optional[datetime] = Field(None, description="Время последнего редактирования")

    # Ссылка на хеш транзакции (для служебных/сделочных сообщений)
    txn_hash: Optional[str] = Field(None, description="Hash транзакции (если сообщение связано с txn)")

    # Дополнительные данные
    metadata: Optional[dict] = Field(None, description="Дополнительные метаданные (JSON)")

    @field_validator('sender_id', 'receiver_id')
    @classmethod
    def validate_sender_receiver_did(cls, v):
        """Валидация DID формата для sender_id и receiver_id"""
        return validate_did_format(v)

    @model_validator(mode='after')
    def validate_content(self):
        """Проверка что сообщение содержит либо текст, либо вложения"""
        message_type = self.message_type
        text = self.text
        attachments = self.attachments

        if message_type == MessageType.TEXT:
            if not text or not text.strip():
                raise ValueError("Text message must contain text")
            if attachments:
                raise ValueError("Text message cannot contain attachments")

        elif message_type == MessageType.FILE:
            if not attachments or len(attachments) == 0:
                raise ValueError("File message must contain at least one attachment")
            for att in attachments:
                if att.type in [AttachmentType.AUDIO, AttachmentType.VIDEO]:
                    raise ValueError("File message cannot contain audio/video attachments")

        elif message_type == MessageType.AUDIO:
            if not attachments or len(attachments) == 0:
                raise ValueError("Audio message must contain at least one audio attachment")
            for att in attachments:
                if att.type != AttachmentType.AUDIO:
                    raise ValueError("Audio message can only contain audio attachments")

        elif message_type == MessageType.VIDEO:
            if not attachments or len(attachments) == 0:
                raise ValueError("Video message must contain at least one video attachment")
            for att in attachments:
                if att.type != AttachmentType.VIDEO:
                    raise ValueError("Video message can only contain video attachments")

        elif message_type == MessageType.MIXED:
            if (not text or not text.strip()) and (not attachments or len(attachments) == 0):
                raise ValueError("Mixed message must contain either text or attachments (or both)")

        elif message_type == MessageType.REPLY:
            reply_to_uuid = self.reply_to_message_uuid
            if not reply_to_uuid:
                raise ValueError("Reply message must contain reply_to_message_uuid")
            if (not text or not text.strip()) and (not attachments or len(attachments) == 0):
                raise ValueError("Reply message must contain either text or attachments (or both)")

        elif message_type == MessageType.DEAL:
            deal_uid = self.deal_uid
            deal_label = self.deal_label
            if not deal_uid:
                raise ValueError("Deal message must contain deal_uid")
            if not deal_label:
                raise ValueError("Deal message must contain deal_label")

        return self

    @model_validator(mode='after')
    def validate_signature_target(self):
        """Проверка что подпись соответствует содержимому"""
        signature = self.signature
        if signature is None:
            return self

        message_type = self.message_type
        text = self.text
        attachments = self.attachments

        if message_type == MessageType.TEXT:
            if not text or not text.strip():
                raise ValueError("Cannot sign empty text message")

        elif message_type in [MessageType.FILE, MessageType.AUDIO, MessageType.VIDEO]:
            if not attachments or len(attachments) == 0:
                raise ValueError("Cannot sign message without attachments")

        elif message_type == MessageType.MIXED:
            if not text and not attachments:
                raise ValueError("Cannot sign empty mixed message")

        elif message_type == MessageType.REPLY:
            if not text and not attachments:
                raise ValueError("Cannot sign empty reply message")

        elif message_type == MessageType.DEAL:
            if signature and not text and not attachments:
                raise ValueError("Cannot sign deal message without text or attachments")

        return self

    model_config = {
        "use_enum_values": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class ChatMessageCreate(BaseModel):
    """Модель для создания нового сообщения"""
    uuid: str = Field(..., description="UUID сообщения (генерируется на клиенте)")
    message_type: MessageType
    sender_id: str
    receiver_id: str
    deal_uid: Optional[str] = Field(None, description="UID сделки (base58 UUID) для типа DEAL")
    deal_label: Optional[str] = Field(None, description="Label сделки для типа DEAL")
    text: Optional[str] = None
    attachments: Optional[List[FileAttachment]] = None
    reply_to_message_uuid: Optional[str] = Field(None, description="UUID сообщения, на которое ссылается ответ")
    metadata: Optional[dict] = None
    txn_hash: Optional[str] = Field(None, description="Hash транзакции (для служебных сообщений со ссылкой на TronScan)")

    signature: Optional[MessageSignature] = None

    @field_validator('sender_id', 'receiver_id')
    @classmethod
    def validate_sender_receiver_did(cls, v):
        """Валидация DID формата для sender_id и receiver_id"""
        return validate_did_format(v)


class ChatMessageResponse(ChatMessage):
    """Модель ответа API (расширенная версия с дополнительными полями)"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
