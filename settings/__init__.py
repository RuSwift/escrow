"""
Настройки приложения с использованием pydantic_settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr
from typing import Optional
from pathlib import Path


class DatabaseSettings(BaseSettings):
    """Настройки подключения к PostgreSQL"""
    
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Настройки подключения
    host: str = Field(
        default="localhost",
        description="Хост базы данных PostgreSQL"
    )
    
    port: int = Field(
        default=5432,
        description="Порт базы данных PostgreSQL"
    )
    
    user: str = Field(
        default="escrow",
        description="Имя пользователя базы данных"
    )
    
    password: SecretStr = Field(
        default=SecretStr("escrow"),
        description="Пароль базы данных"
    )
    
    database: str = Field(
        default="escrow",
        description="Имя базы данных"
    )
    
    # Дополнительные настройки
    pool_size: int = Field(
        default=5,
        description="Размер пула соединений"
    )
    
    max_overflow: int = Field(
        default=10,
        description="Максимальное количество переполнений пула"
    )
    
    pool_timeout: int = Field(
        default=30,
        description="Таймаут ожидания соединения из пула (секунды)"
    )
    
    echo: bool = Field(
        default=False,
        description="Логировать SQL запросы"
    )
    
    @property
    def url(self) -> str:
        """Возвращает URL подключения к базе данных"""
        password_value = self.password.get_secret_value() if self.password else ""
        return f"postgresql://{self.user}:{password_value}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_url(self) -> str:
        """Возвращает async URL подключения к базе данных"""
        password_value = self.password.get_secret_value() if self.password else ""
        return f"postgresql+asyncpg://{self.user}:{password_value}@{self.host}:{self.port}/{self.database}"


class RedisSettings(BaseSettings):
    """Настройки подключения к Redis"""
    
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    host: str = Field(
        default="localhost",
        description="Хост Redis"
    )
    
    port: int = Field(
        default=6379,
        description="Порт Redis"
    )
    
    password: Optional[SecretStr] = Field(
        default=None,
        description="Пароль Redis (опционально)"
    )
    
    db: int = Field(
        default=0,
        description="Номер базы данных Redis"
    )
    
    @property
    def url(self) -> str:
        """Возвращает URL подключения к Redis"""
        password_value = self.password.get_secret_value() if self.password else ""
        if password_value:
            return f"redis://:{password_value}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class MnemonicSettings(BaseSettings):
    """Настройки для хранения mnemonic phrase"""
    
    model_config = SettingsConfigDict(
        env_prefix="MNEMONIC_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    phrase: Optional[SecretStr] = Field(
        default=None,
        description="Мнемоническая фраза для генерации ключей (опционально)"
    )
    
    encrypted_phrase: Optional[SecretStr] = Field(
        default=None,
        description="Зашифрованная мнемоническая фраза (опционально)"
    )


class AdminSettings(BaseSettings):
    """Настройки администратора"""
    
    model_config = SettingsConfigDict(
        env_prefix="ADMIN_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    method: Optional[str] = Field(
        default=None,
        description="Метод авторизации: 'password' или 'tron' (опционально)"
    )
    
    username: Optional[str] = Field(
        default=None,
        description="Имя пользователя администратора (для password метода)"
    )
    
    password: Optional[SecretStr] = Field(
        default=None,
        description="Пароль администратора (для password метода)"
    )
    
    tron_address: Optional[str] = Field(
        default=None,
        description="TRON адрес администратора (для tron метода)"
    )
    
    @property
    def is_configured(self) -> bool:
        """Проверяет, настроен ли админ через env vars"""
        if not self.method:
            return False
        
        if self.method == "password":
            return bool(self.username and self.password)
        elif self.method == "tron":
            return bool(self.tron_address)
        
        return False


class TronSettings(BaseSettings):
    """Настройки для работы с TRON сетью"""
    
    model_config = SettingsConfigDict(
        env_prefix="TRON_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    api_key: Optional[str] = Field(
        default=None,
        description="TronGrid API ключ для доступа к сети TRON (опционально)"
    )
    
    network: str = Field(
        default="mainnet",
        description="TRON сеть: 'mainnet', 'shasta' (testnet), или 'nile' (testnet)"
    )
    
    escrow_min_trx_balance: float = Field(
        default=110.0,
        description="Минимальный баланс TRX на адресе эскроу для инициализации (по умолчанию 100 TRX для AccountPermissionUpdate)"
    )


class ArbiterMnemonicSettings(BaseSettings):
    """Настройки для хранения mnemonic phrase арбитра"""
    
    model_config = SettingsConfigDict(
        env_prefix="MARKETPLACE_ARBITER_MNEMONIC_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    phrase: Optional[SecretStr] = Field(
        default=None,
        description="Мнемоническая фраза для генерации ключей арбитра (опционально)"
    )
    
    encrypted_phrase: Optional[SecretStr] = Field(
        default=None,
        description="Зашифрованная мнемоническая фраза арбитра (опционально)"
    )


class MarketplaceSettings(BaseSettings):
    """Настройки маркетплейса"""
    
    model_config = SettingsConfigDict(
        env_prefix="MARKETPLACE_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    arbiter_mnemonic: ArbiterMnemonicSettings = Field(default_factory=ArbiterMnemonicSettings)


class Settings(BaseSettings):
    """Основные настройки приложения"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Настройки приложения
    app_name: str = Field(
        default="Escrow Node",
        description="Node"
    )
    
    app_version: str = Field(
        default="1.0.0",
        description="Версия приложения"
    )
    
    debug: bool = Field(
        default=False,
        description="Режим отладки"
    )
    
    # Secret key for encryption/signing
    secret: SecretStr = Field(
        default=SecretStr("escrow-dev-secret-key-change-in-production-98765"),
        description="Secret key for encryption and signing operations"
    )
    
    # Настройки базы данных
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    
    # Настройки Redis
    redis: RedisSettings = Field(default_factory=RedisSettings)
    
    # Настройки мнемонической фразы
    mnemonic: MnemonicSettings = Field(default_factory=MnemonicSettings)
    
    # Настройки администратора
    admin: AdminSettings = Field(default_factory=AdminSettings)
    
    # Настройки TRON
    tron: TronSettings = Field(default_factory=TronSettings)
    
    # Настройки маркетплейса
    marketplace: MarketplaceSettings = Field(default_factory=MarketplaceSettings)
    
    # Настройки PEM ключа
    pem: Optional[str] = Field(
        default=None,
        description="PEM данные для ключа ноды (опционально)"
    )
    
    @property
    def is_node_initialized(self) -> bool:
        return bool(self.mnemonic.phrase or self.mnemonic.encrypted_phrase or self.pem)
    
    @property
    def is_admin_configured_from_env(self) -> bool:
        """Проверяет, настроен ли админ через env vars"""
        return self.admin.is_configured
    

# Экспортируем для удобства
__all__ = [
    "Settings",
    "DatabaseSettings",
    "MnemonicSettings",
    "RedisSettings",
    "AdminSettings",
    "TronSettings",
    "MarketplaceSettings",
    "ArbiterMnemonicSettings",
]
