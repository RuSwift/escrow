"""
Точка входа FastAPI для приложения ноды (участника).
Запуск: uvicorn web.node:app --reload
"""
import json
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import init_db
from i18n import _
from i18n.context import get_request_locale
from i18n.translations import get_translations_for_locale
from settings import Settings
from web.endpoints.dependencies import NodeServiceDep
from web.endpoints.health import router as health_router
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

    app.include_router(health_router, prefix="/health")
    app.include_router(v1_router)

    _PAGE_MAP = {
        "/": ("dashboard", "dashboard"),
        "/wallet-users": ("wallet-users", "wallet-users"),
        "/arbiter": ("arbiter", "arbiter"),
        "/wallets": ("wallets", "wallets"),
        "/node": ("node", "node"),
        "/admin": ("admin", "admin"),
        "/settings": ("settings", "settings"),
        "/support": ("support", "support"),
    }

    def _node_context(request: Request, initial_page: str, page_title_key: str, is_node_initialized: bool):
        locale = get_request_locale() or Settings().default_locale
        translations = get_translations_for_locale(locale)
        return {
            "request": request,
            "_": _,
            "app_name": _("node.app_name"),
            "initial_page": initial_page,
            "page_title": _("node.page." + page_title_key),
            "is_node_initialized": is_node_initialized,
            "locale": locale,
            "translations": translations,
            "translations_json": json.dumps(translations, ensure_ascii=False),
        }

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, node_service: NodeServiceDep):
        initial_page, page_title_key = _PAGE_MAP["/"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse("node/app.html", _node_context(request, initial_page, page_title_key, is_node_initialized))

    @app.get("/wallet-users", response_class=HTMLResponse)
    async def wallet_users(request: Request, node_service: NodeServiceDep):
        initial_page, page_title_key = _PAGE_MAP["/wallet-users"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse("node/app.html", _node_context(request, initial_page, page_title_key, is_node_initialized))

    @app.get("/arbiter", response_class=HTMLResponse)
    async def arbiter(request: Request, node_service: NodeServiceDep):
        initial_page, page_title_key = _PAGE_MAP["/arbiter"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse("node/app.html", _node_context(request, initial_page, page_title_key, is_node_initialized))

    @app.get("/wallets", response_class=HTMLResponse)
    async def wallets(request: Request, node_service: NodeServiceDep):
        initial_page, page_title_key = _PAGE_MAP["/wallets"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse("node/app.html", _node_context(request, initial_page, page_title_key, is_node_initialized))

    @app.get("/node", response_class=HTMLResponse)
    async def node_page(request: Request, node_service: NodeServiceDep):
        initial_page, page_title_key = _PAGE_MAP["/node"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse("node/app.html", _node_context(request, initial_page, page_title_key, is_node_initialized))

    @app.get("/admin", response_class=HTMLResponse)
    async def admin(request: Request, node_service: NodeServiceDep):
        initial_page, page_title_key = _PAGE_MAP["/admin"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse("node/app.html", _node_context(request, initial_page, page_title_key, is_node_initialized))

    @app.get("/settings", response_class=HTMLResponse)
    async def settings(request: Request, node_service: NodeServiceDep):
        initial_page, page_title_key = _PAGE_MAP["/settings"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse("node/app.html", _node_context(request, initial_page, page_title_key, is_node_initialized))

    @app.get("/support", response_class=HTMLResponse)
    async def support(request: Request, node_service: NodeServiceDep):
        initial_page, page_title_key = _PAGE_MAP["/support"]
        is_node_initialized = await node_service.is_node_initialized()
        return templates.TemplateResponse("node/app.html", _node_context(request, initial_page, page_title_key, is_node_initialized))

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
