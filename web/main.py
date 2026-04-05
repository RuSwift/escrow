"""
Точка входа FastAPI для основного приложения (main).
Запуск: uvicorn web.main:app --reload
"""
import json
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler

from db import init_db
from db.models import WalletUserSubRole
from i18n import _
from i18n.context import get_request_locale, set_request_locale
from i18n.translations import get_translations_for_locale
from settings import Settings
from web.endpoints.dependencies import (
    get_exchange_wallet_service,
    get_invite_service,
    get_order_service,
    get_required_wallet_address_for_space,
    get_space_service,
    get_wallet_user_service,
)
from web.endpoints.health import router as health_router
from web.endpoints.v1 import router as v1_router
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

    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        """Редирект на лендинг при 401 для браузерных запросов."""
        if exc.status_code == 401:
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                # Если пользователь ломится в какой-то спейс, запоминаем куда
                path = request.url.path
                query = f"?next={path}" if path and path != "/" else ""
                # Если это корень, не добавляем next
                if path == "/":
                    query = ""
                return RedirectResponse(url=f"/{query}")
        
        # Для API или других ошибок используем стандартный обработчик
        return await default_http_exception_handler(request, exc)

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    def _collateral_stablecoin_tokens_json() -> str:
        s = Settings()
        payload = [
            {
                "symbol": t.symbol,
                "contract_address": t.contract_address,
                "network": t.network,
                "decimals": t.decimals,
            }
            for t in s.collateral_stablecoin.tokens
        ]
        return json.dumps(payload, ensure_ascii=False)

    app.include_router(health_router, prefix="/health")
    app.include_router(v1_router)

    def _main_context(request: Request, initial_page: str = "dashboard", space_lang: str | None = None):
        settings = Settings()
        # Приоритет языка: 1. query lang, 2. space profile lang, 3. Accept-Language header, 4. default
        locale = get_request_locale()
        if space_lang and not request.query_params.get("lang"):
            locale = space_lang
            set_request_locale(locale)
        
        locale = locale or settings.default_locale
        translations = get_translations_for_locale(locale)
        tron_net = (settings.tron.network or "mainnet").strip().lower()
        if tron_net not in ("mainnet", "shasta", "nile"):
            tron_net = "mainnet"
        
        # Check for 'next' parameter to show a message on landing
        next_url = request.query_params.get("next")
        show_auth_required = False
        if next_url and next_url.startswith("/") and len(next_url) > 1:
            show_auth_required = True

        return {
            "request": request,
            "_": _,
            "app_name": _("main.app_name"),
            "splash_title": _("main.splash_title"),
            "locale": locale,
            "translations": translations,
            "translations_json": json.dumps(translations, ensure_ascii=False),
            "initial_page": initial_page,
            "tron_network": tron_net,
            "settings_debug": settings.debug,
            "show_auth_required": show_auth_required,
            "next_url": next_url,
        }

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, space_service=Depends(get_space_service)):
        # If we have a saved space in cookies or can determine it, we could try to get its lang
        # but for landing it's better to stick to Accept-Language/query unless a space is specified.
        return templates.TemplateResponse(
            "main/landing.html",
            _main_context(request),
        )

    @app.get("/app", response_class=HTMLResponse)
    async def app_legacy(request: Request):
        """Обратная совместимость: редирект на лендинг для выбора/входа в space."""
        return RedirectResponse(url="/", status_code=302)

    @app.get("/v/{token}", response_class=HTMLResponse)
    async def invite_verify_page(
        request: Request,
        token: str,
        invite_service=Depends(get_invite_service),
    ):
        """Страница верификации приглашения по ссылке. Без авторизации. При невалидном/истёкшем токене — сообщение «приглашение истекло или не найдено»."""
        invite = await invite_service.get_invite_by_token(token)
        if not invite:
            return templates.TemplateResponse(
                "main/invite_verify.html",
                {
                    **_main_context(request, "dashboard"),
                    "invite_invalid": True,
                    "invite": None,
                    "invite_token": token,
                },
            )
        roles_str = [r.value for r in invite.roles]
        invite_payload = {
            "space_name": invite.space_name,
            "inviter_nickname": invite.inviter_nickname,
            "roles": roles_str,
            "roles_display": ", ".join(_(f"main.space.role_{r}") for r in roles_str) if roles_str else "—",
            "wallet_address": invite.wallet_address,
            "wallet_address_mask": f"{invite.wallet_address[:2]}…{invite.wallet_address[-4:]}" if invite.wallet_address and len(invite.wallet_address) >= 6 else (invite.wallet_address or "—"),
            "blockchain": invite.blockchain or "tron",
            "participant_nickname": invite.participant_nickname,
        }
        return templates.TemplateResponse(
            "main/invite_verify.html",
            {
                **_main_context(request, "dashboard"),
                "invite_invalid": False,
                "invite": invite_payload,
                "invite_json": json.dumps(invite_payload, ensure_ascii=False),
                "invite_token": token,
            },
        )

    @app.get("/o/{token}", response_class=HTMLResponse)
    async def order_sign_page(
        request: Request,
        token: str,
        order_svc=Depends(get_order_service),
    ):
        """Публичная страница подписи заявки на вывод по токену из Redis."""
        ctx = await order_svc.get_public_sign_context(token)
        if not ctx:
            return templates.TemplateResponse(
                "main/order_sign.html",
                {
                    **_main_context(request, "dashboard"),
                    "order_sign_invalid": True,
                    "order_sign_token": token,
                },
            )
        return templates.TemplateResponse(
            "main/order_sign.html",
            {
                **_main_context(request, "dashboard"),
                "order_sign_invalid": False,
                "order_sign_token": token,
            },
        )

    @app.get("/{space}", response_class=HTMLResponse)
    async def app_space_view(
        request: Request,
        space: str,
        initial_page: str = "dashboard",
        escrow_id: str = "",
        wallet_address: str = Depends(get_required_wallet_address_for_space),
        wallet_service=Depends(get_wallet_user_service),
        space_service=Depends(get_space_service),
        exchange_wallet_service=Depends(get_exchange_wallet_service),
    ):
        """Приложение в контексте space (nickname). Доступ только если JWT и space в списке spaces пользователя."""
        space_clean = (space or "").strip()
        if not space_clean:
            return RedirectResponse(url="/", status_code=302)
        allowed = await wallet_service.get_spaces_for_address(wallet_address, "tron")
        if space_clean not in allowed:
            return RedirectResponse(url="/", status_code=302)
        
        # Determine space language for priority i18n
        space_lang = await space_service.get_space_language_for_display(space_clean)
        
        space_company_name = await space_service.get_space_company_name_for_display(
            space_clean
        )
        space_role = await space_service.get_space_role(space_clean, wallet_address, "tron")
        is_owner = space_role == WalletUserSubRole.owner

        if initial_page in ("space-roles", "space-profile") and not is_owner:
            ctx = {
                **_main_context(request, "dashboard", space_lang=space_lang),
                "space": space_clean,
                "space_company_name": space_company_name,
                "space_role": space_role.value,
                "space_subs_count": -1,
                "space_profile_filled": True,
            }
            return templates.TemplateResponse(
                "main/forbidden.html",
                ctx,
                status_code=403,
            )

        if is_owner:
            subs = await space_service.list_subs_for_space(
                space_clean, wallet_address
            )
            space_subs_count = len(subs)
            profile = await space_service.get_space_profile(space_clean, wallet_address)
            space_profile_filled = space_service.get_space_profile_filled(profile)
            
            wallets = await exchange_wallet_service.list_wallets(
                space_clean, wallet_address
            )
            space_wallets_count = len(wallets)
        else:
            space_subs_count = -1
            space_profile_filled = True
            space_wallets_count = -1

        valid = (
            "dashboard",
            "how-it-works",
            "api",
            "settings",
            "support",
            "detail",
        )
        if is_owner:
            valid = valid + ("space-roles", "space-profile", "my-business", "guarantor")
        page = initial_page if initial_page in valid else "dashboard"
        if page == "detail" and not escrow_id:
            page = "dashboard"
        space_owner_wallet_tron = ""
        if is_owner:
            space_owner_wallet_tron = (
                await space_service.get_space_owner_tron_wallet(space_clean) or ""
            )
        
        # Primary wallet for the space
        space_primary_wallet = await space_service.get_primary_wallet(space_clean)

        return templates.TemplateResponse(
            "main/app.html",
            {
                **_main_context(request, page, space_lang=space_lang),
                "initial_page": page,
                "escrow_id": escrow_id.strip() if page == "detail" else "",
                "space": space_clean,
                "space_company_name": space_company_name,
                "space_role": space_role.value,
                "space_subs_count": space_subs_count,
                "space_wallets_count": space_wallets_count,
                "space_profile_filled": space_profile_filled,
                "space_owner_wallet_tron": space_owner_wallet_tron,
                "space_primary_wallet": space_primary_wallet,
                "collateral_stablecoin_tokens_json": _collateral_stablecoin_tokens_json(),
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
