"""
Настройки приложения с использованием pydantic_settings
"""

from decimal import Decimal
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# Корень репозитория (settings/__init__.py → parent = settings, parent.parent = repo)
_REPO_ROOT = Path(__file__).resolve().parent.parent


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
        env_file=(".env", ".env.local"),
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


# --- Движки котировок (forex, cbr, rapira, bestchange) ---


class ForexEngineSettings(BaseSettings):
    """Настройки движка Forex (публичный API, без секретов)."""
    model_config = SettingsConfigDict(
        env_prefix="RATIOS_FOREX_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    ttl: int = Field(default=3600, description="TTL кэша в секундах")


class CbrEngineSettings(BaseSettings):
    """Настройки движка ЦБ РФ (публичный XML, без секретов)."""
    model_config = SettingsConfigDict(
        env_prefix="RATIOS_CBR_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    ttl: int = Field(default=3600, description="TTL кэша в секундах")


class RapiraEngineSettings(BaseSettings):
    """Настройки движка Rapira (JWT: private_key, uid)."""
    model_config = SettingsConfigDict(
        env_prefix="RATIOS_RAPIRA_",
        case_sensitive=False,
        # Абсолютные пути: при pytest cwd может быть не корень репозитория.
        # .env.local переопределяет значения из .env (локальные секреты).
        env_file=(_REPO_ROOT / ".env", _REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore"
    )
    private_key: Optional[SecretStr] = Field(default=None, description="Приватный ключ API")
    uid: Optional[str] = Field(default=None, description="UID API ключа")
    host: str = Field(default="api.rapira.net", description="Хост API")
    ttl: int = Field(default=60, description="JWT TTL в секундах")


class BestChangeSettings(BaseSettings):
    """Настройки движка BestChange (ZIP по URL, без секретов)."""
    model_config = SettingsConfigDict(
        env_prefix="RATIOS_BESTCHANGE_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    url: str = Field(default="http://api.bestchange.ru/info.zip", description="URL архива")
    enc: str = Field(default="windows-1251", description="Кодировка файлов в архиве")
    file_currencies: str = Field(default="bm_cy.dat", description="Файл валют в архиве")
    file_exchangers: str = Field(default="bm_exch.dat", description="Файл обменников")
    file_rates: str = Field(default="bm_rates.dat", description="Файл курсов")
    file_cities: str = Field(default="bm_cities.dat", description="Файл городов")
    file_top: str = Field(default="bm_top.dat", description="Файл топа")
    file_payment_codes: str = Field(default="bm_cycodes.dat", description="Файл кодов оплаты")
    file_cur_codes: str = Field(default="bm_bcodes.dat", description="Файл кодов валют")
    zip_path: str = Field(default="/tmp/bestchange.zip", description="Путь для сохранения ZIP")
    split_reviews: bool = Field(default=False, description="Разбивать отзывы")


class RatiosSettings(BaseSettings):
    """Настройки движков котировок (forex, cbr, rapira, bestchange)."""
    model_config = SettingsConfigDict(
        env_prefix="RATIOS_",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    forex: Optional[ForexEngineSettings] = Field(default_factory=ForexEngineSettings)
    cbr: Optional[CbrEngineSettings] = Field(default_factory=CbrEngineSettings)
    rapira: Optional[RapiraEngineSettings] = Field(default_factory=RapiraEngineSettings)
    bestchange: Optional[BestChangeSettings] = Field(default_factory=BestChangeSettings)


class CollateralStablecoinToken(BaseModel):
    """Одна строка каталога залоговых стейблкоинов."""

    model_config = {"extra": "ignore"}

    symbol: str = Field(description="Символ токена (тикер)")
    network: str = Field(description="Имя сети блокчейна")
    contract_address: str = Field(description="Адрес контракта токена")
    base_currency: str = Field(description="Базовая валюта привязки (например USD, RUB)")
    decimals: int = Field(default=6, ge=0, le=36, description="Decimals токена для отображения баланса")


def _default_collateral_stablecoin_tokens() -> list[CollateralStablecoinToken]:
    """USDT (TRC-20) и A7A5 — рублёвый стейблкоин A7A5 на TRON (TRC-20)."""
    return [
        CollateralStablecoinToken(
            symbol="USDT",
            network="TRON",
            contract_address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            base_currency="USD",
            decimals=6,
        ),
        CollateralStablecoinToken(
            symbol="A7A5",
            network="TRON",
            contract_address="TLeVfrdym8RoJreJ23dAGyfJDygRtiWKBZ",
            base_currency="RUB",
            decimals=6,
        ),
    ]


class CollateralStablecoinSettings(BaseSettings):
    """Каталог токенов для залогового стейблкоина (переопределение через JSON в env)."""

    model_config = SettingsConfigDict(
        env_prefix="COLLATERAL_STABLECOIN_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tokens: list[CollateralStablecoinToken] = Field(
        default_factory=_default_collateral_stablecoin_tokens,
        description="Список токенов: символ, сеть, контракт, базовая валюта",
    )


class CommissionWalletSettings(BaseSettings):
    """Адреса кошельков и размер комиссии платформы по блокчейнам (tron, ethereum)."""

    model_config = SettingsConfigDict(
        env_prefix="COMMISSION_WALLET_",
        case_sensitive=False,
        env_file=(_REPO_ROOT / ".env", _REPO_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    percent: Decimal = Field(
        default=Decimal("0.2"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Размер комиссии платформы в процентах (0–100)",
    )

    tron: Optional[str] = Field(
        default=None,
        description="TRON-адрес для зачисления комиссий (TRC-20 / нативный TRX)",
    )
    ethereum: Optional[str] = Field(
        default=None,
        description="Ethereum-адрес для зачисления комиссий (ERC-20 и совместимые EVM-сети)",
    )

    def address_for_blockchain(self, blockchain: str) -> Optional[str]:
        """Адрес по идентификатору блокчейна, как в WalletUser (tron | ethereum)."""
        b = (blockchain or "").strip().lower()
        if b == "tron":
            return (self.tron or "").strip() or None
        if b == "ethereum":
            return (self.ethereum or "").strip() or None
        return None


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
        description=(
            "Режим отладки (dev-UI). Только env APP_DEBUG; переменная DEBUG не используется "
            "(её подмешивает IDE/отладчик и она конфликтовала с .env)."
        ),
        validation_alias="APP_DEBUG",
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
    
    # Движки котировок (forex, cbr, rapira, bestchange)
    ratios: RatiosSettings = Field(
        default_factory=RatiosSettings,
        description="Настройки движков котировок (активность по is_enabled каждого движка)",
    )

    # Залоговые стейблкоины (символ, сеть, контракт, базовая валюта)
    collateral_stablecoin: CollateralStablecoinSettings = Field(
        default_factory=CollateralStablecoinSettings,
        description="Каталог токенов залогового стейблкоина",
    )

    # Кошельки комиссий платформы по сетям
    commission_wallet: CommissionWalletSettings = Field(
        default_factory=CommissionWalletSettings,
        description="Адреса получения комиссий: tron, ethereum",
    )
    
    # Настройки PEM ключа
    pem: Optional[str] = Field(
        default=None,
        description="PEM данные для ключа ноды (опционально)"
    )
    
    # Локализация
    default_locale: str = Field(
        default="ru",
        description="Язык по умолчанию для переводов (когда контекст запроса отсутствует)"
    )
    supported_locales: list[str] = Field(
        default=["ru", "en"],
        description="Список поддерживаемых кодов локалей для валидации Accept-Language",
    )
    system_currencies: list[str] = Field(
        default=["RUB", "CNY", "USD", "EUR"],
        description="Коды валют (ISO 4217), используемые в системе",
    )

    deal_simple_placeholder_receiver_did: str = Field(
        default="did:tron:simple_pending",
        description=(
            "DID-заглушка для receiver_did в черновых Simple-заявках (Deal.receiver_did NOT NULL)"
        ),
        validation_alias=AliasChoices(
            "DEAL_SIMPLE_PLACEHOLDER_RECEIVER_DID",
            "deal_simple_placeholder_receiver_did",
        ),
    )

    payment_forms_yaml: str = Field(
        default="forms.yaml",
        description=(
            "Путь к YAML с полями реквизитов по payment_code; "
            "относительно корня репозитория или абсолютный"
        ),
        validation_alias=AliasChoices("PAYMENT_FORMS_YAML", "payment_forms_yaml"),
    )

    @property
    def payment_forms_yaml_path(self) -> Path:
        """Разрешённый путь к ``forms.yaml``."""
        p = Path(self.payment_forms_yaml)
        if p.is_absolute():
            return p
        return _REPO_ROOT / p

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
    "RatiosSettings",
    "ForexEngineSettings",
    "CbrEngineSettings",
    "RapiraEngineSettings",
    "BestChangeSettings",
    "CollateralStablecoinToken",
    "CollateralStablecoinSettings",
    "CommissionWalletSettings",
]
