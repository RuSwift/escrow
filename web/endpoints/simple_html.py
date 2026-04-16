"""HTML-маршруты публичного Simple UI: /simple, /simple/{order_id}."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.main_context import main_context


def create_simple_html_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter(tags=["Simple UI"])

    @router.get("/simple", response_class=HTMLResponse)
    async def simple_orders_list(request: Request):
        return templates.TemplateResponse(
            "main/simple.html",
            {
                **main_context(request, "dashboard"),
                "simple_order_id": "",
            },
        )

    @router.get("/simple/{order_id}", response_class=HTMLResponse)
    async def simple_deal_view(request: Request, order_id: str):
        return templates.TemplateResponse(
            "main/simple.html",
            {
                **main_context(request, "dashboard"),
                "simple_order_id": order_id,
            },
        )

    return router
