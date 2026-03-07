"""
Централизованная конфигурация pytest для всех тестов.
Использует реальный PostgreSQL и Redis (docker-compose / .env).
"""
import os
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from redis.asyncio import Redis

from db import Base
from settings import DatabaseSettings, RedisSettings, Settings


TEST_DB_NAME = "escrow_test"


@pytest.fixture(scope="function")
def event_loop():
    """
    Создает новый event loop для каждого теста.
    Предотвращает проблемы с "Task got Future attached to a different loop".
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_db_settings():
    """
    Настройки для тестовой БД (параметры из .env, имя БД — escrow_test).
    """
    db_settings = DatabaseSettings()
    return DatabaseSettings(
        host=db_settings.host,
        port=db_settings.port,
        user=db_settings.user,
        password=db_settings.password,
        database=TEST_DB_NAME,
        echo=False,
    )


@pytest.fixture(scope="session")
def test_redis_settings():
    """
    Настройки Redis для тестов (db=1, чтобы не затирать dev).
    """
    redis_settings = RedisSettings()
    return RedisSettings(
        host=redis_settings.host,
        port=redis_settings.port,
        password=redis_settings.password,
        db=1,
    )


@pytest.fixture(scope="session", autouse=True)
def create_test_database(test_db_settings):
    """
    Создает тестовую БД перед запуском тестов и удаляет после.
    """
    db_settings = DatabaseSettings()
    admin_url = (
        f"postgresql://{db_settings.user}:{db_settings.password.get_secret_value()}"
        f"@{db_settings.host}:{db_settings.port}/postgres"
    )
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with engine.connect() as conn:
        conn.execute(
            text(
                f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{TEST_DB_NAME}'
            AND pid <> pg_backend_pid()
        """
            )
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))

    engine.dispose()

    original_db_database = os.environ.get("DB_DATABASE")
    os.environ["DB_DATABASE"] = TEST_DB_NAME
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", test_db_settings.url)
        command.upgrade(alembic_cfg, "head")
    finally:
        if original_db_database is not None:
            os.environ["DB_DATABASE"] = original_db_database
        else:
            os.environ.pop("DB_DATABASE", None)

    yield

    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(
            text(
                f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{TEST_DB_NAME}'
            AND pid <> pg_backend_pid()
        """
            )
        )
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_engine(test_db_settings):
    """
    Async engine для тестовой БД (NullPool для изоляции тестов).
    """
    engine = create_async_engine(
        test_db_settings.async_url,
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_redis(test_redis_settings) -> AsyncGenerator[Redis, None]:
    """
    Клиент Redis для тестов. Очищает выбранный db после теста.
    """
    client = Redis.from_url(test_redis_settings.url, decode_responses=True)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def test_db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Сессия БД для каждого теста. После теста очищает таблицы (кроме alembic_version).
    """
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

    async with db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE node_settings CASCADE"))
        await conn.execute(text("TRUNCATE TABLE admin_users CASCADE"))
        await conn.execute(text("TRUNCATE TABLE admin_tron_addresses CASCADE"))
        await conn.execute(text("TRUNCATE TABLE wallet_users CASCADE"))
        await conn.execute(text("TRUNCATE TABLE billing CASCADE"))
        await conn.execute(text("TRUNCATE TABLE storage CASCADE"))
        await conn.execute(text("TRUNCATE TABLE connections CASCADE"))
        await conn.execute(text("TRUNCATE TABLE escrow_operations CASCADE"))
        await conn.execute(text("TRUNCATE TABLE escrow_txn CASCADE"))
        await conn.execute(text("TRUNCATE TABLE deal CASCADE"))
        await conn.execute(text("TRUNCATE TABLE advertisements CASCADE"))
        await conn.execute(text("TRUNCATE TABLE wallets CASCADE"))


@pytest.fixture
def test_secret():
    """Секрет для шифрования в тестах."""
    return "test-secret-key-for-encryption-12345678"


@pytest.fixture
def set_test_secret(test_secret, monkeypatch):
    """Устанавливает тестовый SECRET в окружение (для Settings)."""
    monkeypatch.setenv("SECRET", test_secret)
    return test_secret


@pytest.fixture
def test_settings(set_test_secret) -> Settings:
    """Настройки приложения с тестовым секретом."""
    return Settings()
