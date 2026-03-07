"""
Middleware для web-приложения.
"""
from web.middleware.locale import LocaleMiddleware, install_locale_middleware

__all__ = ["LocaleMiddleware", "install_locale_middleware"]
