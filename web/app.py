"""
Точка входа FastAPI: создание приложения и подключение роутеров.
Запуск: uvicorn web.app:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from db import init_db
from settings import Settings
from web.endpoints.v1 import router as v1_router
from web.middleware import install_locale_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация БД при старте приложения."""
    settings = Settings()
    init_db(settings.database)
    yield
    # shutdown при необходимости


def create_app() -> FastAPI:
    """Фабрика приложения с роутерами и middleware."""
    app = FastAPI(title="Escrow API", lifespan=lifespan)
    install_locale_middleware(app)
    app.include_router(v1_router)
    return app


app = create_app()
