"""HTML-маршруты публичного Simple UI: /arbiter/{arbiter_space_did}, deal, legacy order id."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from services.arbiter_display_label import arbiter_segment_display_label
from web.main_context import (
    collateral_stablecoin_tokens_json,
    main_context,
    system_currencies_codes_json,
)


async def _simple_template_ctx(
    request: Request, session: AsyncSession, *, arbiter_space_did: str
) -> dict:
    ctx = main_context(request, "dashboard")
    ctx["simple_stablecoins_json"] = collateral_stablecoin_tokens_json()
    ctx["simple_system_currencies_json"] = system_currencies_codes_json()
    ctx.setdefault("simple_deal_uid", "")
    ctx.setdefault("simple_order_id", "")
    ctx["arbiter_space_did"] = arbiter_space_did
    display = await arbiter_segment_display_label(session, arbiter_space_did)
    ctx["arbiter_display_name"] = (display or "").strip()
    return ctx


def create_simple_html_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter(tags=["Simple UI"])

    @router.get("/arbiter/{arbiter_space_did}/deal/{deal_uid}", response_class=HTMLResponse)
    async def simple_deal_by_uid(
        request: Request,
        arbiter_space_did: str,
        deal_uid: str,
        session: AsyncSession = Depends(get_db),
    ):
        arb = (arbiter_space_did or "").strip()
        ctx = await _simple_template_ctx(request, session, arbiter_space_did=arb)
        ctx["simple_deal_uid"] = (deal_uid or "").strip()
        ctx["simple_order_id"] = ""
        return templates.TemplateResponse("main/simple.html", ctx)

    @router.get("/arbiter/{arbiter_space_did}/{legacy_id}", response_class=HTMLResponse)
    async def simple_legacy_view(
        request: Request,
        arbiter_space_did: str,
        legacy_id: str,
        session: AsyncSession = Depends(get_db),
    ):
        """Legacy: идентификатор заявки/сделки одним сегментом."""
        arb = (arbiter_space_did or "").strip()
        leg = (legacy_id or "").strip()
        ctx = await _simple_template_ctx(request, session, arbiter_space_did=arb)
        ctx["simple_deal_uid"] = ""
        ctx["simple_order_id"] = leg
        return templates.TemplateResponse("main/simple.html", ctx)

    @router.get("/arbiter/{arbiter_space_did}", response_class=HTMLResponse)
    async def simple_orders_list(
        request: Request,
        arbiter_space_did: str,
        session: AsyncSession = Depends(get_db),
    ):
        arb = (arbiter_space_did or "").strip()
        ctx = await _simple_template_ctx(request, session, arbiter_space_did=arb)
        ctx["simple_deal_uid"] = ""
        ctx["simple_order_id"] = ""
        return templates.TemplateResponse("main/simple.html", ctx)

    return router
