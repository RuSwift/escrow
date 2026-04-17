"""HTML-маршруты публичного Simple UI: /simple, /simple/deal/{uid}, /simple/{legacy_id}."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.main_context import (
    collateral_stablecoin_tokens_json,
    main_context,
    system_currencies_codes_json,
)


def _simple_template_ctx(request: Request) -> dict:
    ctx = main_context(request, "dashboard")
    ctx["simple_stablecoins_json"] = collateral_stablecoin_tokens_json()
    ctx["simple_system_currencies_json"] = system_currencies_codes_json()
    ctx.setdefault("simple_deal_uid", "")
    ctx.setdefault("simple_order_id", "")
    return ctx


def create_simple_html_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter(tags=["Simple UI"])

    @router.get("/simple", response_class=HTMLResponse)
    async def simple_orders_list(request: Request):
        ctx = _simple_template_ctx(request)
        ctx["simple_deal_uid"] = ""
        ctx["simple_order_id"] = ""
        return templates.TemplateResponse("main/simple.html", ctx)

    @router.get("/simple/deal/{deal_uid}", response_class=HTMLResponse)
    async def simple_deal_by_uid(request: Request, deal_uid: str):
        ctx = _simple_template_ctx(request)
        ctx["simple_deal_uid"] = (deal_uid or "").strip()
        ctx["simple_order_id"] = ""
        return templates.TemplateResponse("main/simple.html", ctx)

    @router.get("/simple/{legacy_id}", response_class=HTMLResponse)
    async def simple_legacy_view(request: Request, legacy_id: str):
        ctx = _simple_template_ctx(request)
        ctx["simple_deal_uid"] = ""
        ctx["simple_order_id"] = (legacy_id or "").strip()
        return templates.TemplateResponse("main/simple.html", ctx)

    return router
