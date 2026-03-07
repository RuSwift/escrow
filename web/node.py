"""
Точка входа FastAPI для приложения ноды (участника).
Запуск: uvicorn web.node:app --reload
"""
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import init_db
from settings import Settings
from web.endpoints.dependencies import NodeServiceDep
from web.endpoints.v1 import router as v1_router
from web.middleware import install_locale_middleware

# Пути относительно корня репозитория
WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


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

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(v1_router)

    _PAGE_MAP = {
        "/": ("dashboard", "Дашборд"),
        "/wallet-users": ("wallet-users", "Пользователи"),
        "/arbiter": ("arbiter", "Арбитр"),
        "/wallets": ("wallets", "Кошельки"),
        "/node": ("node", "Нода"),
        "/admin": ("admin", "Админ"),
        "/settings": ("settings", "Настройки"),
        "/support": ("support", "Поддержка"),
    }

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, node_service: NodeServiceDep):
        """Главная: SPA с Vue, начальная страница — дашборд."""
        initial_page, page_title = _PAGE_MAP["/"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse(
            "node/app.html",
            {
                "request": request,
                "app_name": "Escrow Node",
                "initial_page": initial_page,
                "page_title": page_title,
                "is_node_initialized": is_node_initialized,
            },
        )

    @app.get("/wallet-users", response_class=HTMLResponse)
    async def wallet_users(request: Request, node_service: NodeServiceDep):
        initial_page, page_title = _PAGE_MAP["/wallet-users"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse(
            "node/app.html",
            {"request": request, "app_name": "Escrow Node", "initial_page": initial_page, "page_title": page_title, "is_node_initialized": is_node_initialized},
        )

    @app.get("/arbiter", response_class=HTMLResponse)
    async def arbiter(request: Request, node_service: NodeServiceDep):
        initial_page, page_title = _PAGE_MAP["/arbiter"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse(
            "node/app.html",
            {"request": request, "app_name": "Escrow Node", "initial_page": initial_page, "page_title": page_title, "is_node_initialized": is_node_initialized},
        )

    @app.get("/wallets", response_class=HTMLResponse)
    async def wallets(request: Request, node_service: NodeServiceDep):
        initial_page, page_title = _PAGE_MAP["/wallets"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse(
            "node/app.html",
            {"request": request, "app_name": "Escrow Node", "initial_page": initial_page, "page_title": page_title, "is_node_initialized": is_node_initialized},
        )

    @app.get("/node", response_class=HTMLResponse)
    async def node_page(request: Request, node_service: NodeServiceDep):
        initial_page, page_title = _PAGE_MAP["/node"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse(
            "node/app.html",
            {"request": request, "app_name": "Escrow Node", "initial_page": initial_page, "page_title": page_title, "is_node_initialized": is_node_initialized},
        )

    @app.get("/admin", response_class=HTMLResponse)
    async def admin(request: Request, node_service: NodeServiceDep):
        initial_page, page_title = _PAGE_MAP["/admin"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse(
            "node/app.html",
            {"request": request, "app_name": "Escrow Node", "initial_page": initial_page, "page_title": page_title, "is_node_initialized": is_node_initialized},
        )

    @app.get("/settings", response_class=HTMLResponse)
    async def settings(request: Request, node_service: NodeServiceDep):
        initial_page, page_title = _PAGE_MAP["/settings"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse(
            "node/app.html",
            {"request": request, "app_name": "Escrow Node", "initial_page": initial_page, "page_title": page_title, "is_node_initialized": is_node_initialized},
        )

    @app.get("/support", response_class=HTMLResponse)
    async def support(request: Request, node_service: NodeServiceDep):
        initial_page, page_title = _PAGE_MAP["/support"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse(
            "node/app.html",
            {"request": request, "app_name": "Escrow Node", "initial_page": initial_page, "page_title": page_title, "is_node_initialized": is_node_initialized},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
