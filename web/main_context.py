"""Общий контекст Jinja для HTML-страниц main (лендинг, simple, app, приглашения)."""
from __future__ import annotations

import json

from fastapi import Request

from i18n import _
from i18n.context import get_request_locale, set_request_locale
from i18n.translations import get_translations_for_locale
from settings import Settings


def collateral_stablecoin_tokens_json() -> str:
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


def system_currencies_codes_json() -> str:
    """ISO-коды фиата из Settings для Simple UI."""
    s = Settings()
    codes = [str(c).strip().upper() for c in (s.system_currencies or []) if str(c).strip()]
    return json.dumps(codes, ensure_ascii=False)


def main_context(
    request: Request, initial_page: str = "dashboard", space_lang: str | None = None
) -> dict:
    settings = Settings()
    locale = get_request_locale()
    if space_lang and not request.query_params.get("lang"):
        locale = space_lang
        set_request_locale(locale)

    locale = locale or settings.default_locale
    translations = get_translations_for_locale(locale)
    tron_net = (settings.tron.network or "mainnet").strip().lower()
    if tron_net not in ("mainnet", "shasta", "nile"):
        tron_net = "mainnet"

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
