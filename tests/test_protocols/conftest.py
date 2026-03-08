"""
Конфигурация для тестов протоколов DIDComm.
Мокаем db.SessionLocal, чтобы ConnectionHandler не требовал реальную БД.
"""
import pytest

import db


class _AsyncSessionMock:
    """Минимальный async context manager для подмены сессии БД."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture(scope="session", autouse=True)
def mock_db_session_local():
    """Mock SessionLocal: вызываемый, возвращает async context manager."""
    original_session_local = db.SessionLocal
    db.SessionLocal = lambda: _AsyncSessionMock()
    yield
    db.SessionLocal = original_session_local
