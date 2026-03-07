import json
import base64
import hashlib
import secrets
from abc import ABC
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from settings import Settings


class BaseRepository(ABC):
    """
    Базовый абстрактный класс репозитория с поддержкой Unit of Work (AsyncSession),
    Redis и шифрования данных.
    """

    def __init__(self, session: AsyncSession, redis: Redis, settings: Settings):
        self._session = session
        self._redis = redis
        self._settings = settings

    def _get_secret(self) -> str:
        """
        Получает секретный ключ из настроек.
        """
        return self._settings.secret.get_secret_value()

    def _derive_encryption_key(self, secret: str) -> bytes:
        """
        Получает ключ шифрования из secret (SHA-256).
        """
        return hashlib.sha256(secret.encode('utf-8')).digest()

    def encrypt_data(self, plaintext: str) -> str:
        """
        Шифрует данные через AES-GCM.
        
        Returns:
            Base64-encoded JSON строка с iv, tag и ciphertext
        """
        secret_key = self._get_secret()
        key = self._derive_encryption_key(secret_key)
        
        # Генерируем IV (16 байт)
        iv = secrets.token_bytes(16)
        
        # Шифруем через AES-GCM
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext.encode('utf-8')) + encryptor.finalize()
        tag = encryptor.tag
        
        # Формируем результат
        result = {
            "iv": base64.b64encode(iv).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8'),
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8')
        }
        
        # Возвращаем в виде base64-encoded JSON
        return base64.b64encode(json.dumps(result).encode('utf-8')).decode('utf-8')

    def decrypt_data(self, encrypted: str) -> str:
        """
        Дешифрует данные через AES-GCM.
        
        Args:
            encrypted: Base64-encoded JSON строка с iv, tag и ciphertext
            
        Returns:
            Расшифрованный текст
        """
        secret_key = self._get_secret()
        key = self._derive_encryption_key(secret_key)
        
        # Декодируем JSON
        data = json.loads(base64.b64decode(encrypted).decode('utf-8'))
        iv = base64.b64decode(data["iv"])
        tag = base64.b64decode(data["tag"])
        ciphertext = base64.b64decode(data["ciphertext"])
        
        # Дешифруем через AES-GCM
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        return plaintext.decode('utf-8')
