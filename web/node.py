"""
Точка входа FastAPI для приложения ноды (участника).
Запуск: uvicorn web.node:app --reload
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
    """Фабрика приложения ноды с роутерами и middleware."""
    app = FastAPI(title="Escrow Node API", lifespan=lifespan)
    install_locale_middleware(app)
    app.include_router(v1_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
