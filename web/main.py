"""
Точка входа FastAPI для основного приложения (main).
Запуск: uvicorn web.main:app --reload
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
from web.endpoints.health import router as health_router
from web.middleware import install_locale_middleware

# Пути относительно корня web (как в node.py)
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
    """Фабрика основного приложения: роутеры, статика, темплейты."""
    app = FastAPI(title="Escrow Main API", lifespan=lifespan)
    install_locale_middleware(app)

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(health_router, prefix="/health")

    def _main_context(request: Request, initial_page: str = "dashboard"):
        locale = get_request_locale() or Settings().default_locale
        translations = get_translations_for_locale(locale)
        return {
            "request": request,
            "_": _,
            "app_name": _("main.app_name"),
            "splash_title": _("main.splash_title"),
            "locale": locale,
            "translations": translations,
            "translations_json": json.dumps(translations, ensure_ascii=False),
            "initial_page": initial_page,
        }

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        return templates.TemplateResponse(
            "main/landing.html",
            _main_context(request),
        )

    @app.get("/app", response_class=HTMLResponse)
    async def app_view(
        request: Request,
        initial_page: str = "dashboard",
        escrow_id: str = "",
    ):
        valid = ("dashboard", "my-trusts", "how-it-works", "api", "settings", "support", "detail")
        page = initial_page if initial_page in valid else "dashboard"
        if page == "detail" and not escrow_id:
            page = "dashboard"
        return templates.TemplateResponse(
            "main/app.html",
            {
                **_main_context(request, page),
                "initial_page": page,
                "escrow_id": escrow_id.strip() if page == "detail" else "",
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
