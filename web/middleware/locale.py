"""
Middleware для установки локали запроса в ContextVar из Accept-Language или query lang.
Подключение: app.add_middleware(LocaleMiddleware) при создании FastAPI-приложения.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from i18n.context import set_request_locale
from settings import Settings


def _parse_accept_language(header_value: str | None, supported: list[str]) -> str | None:
    """
    Извлекает первый подходящий код языка из заголовка Accept-Language.
    Формат: "ru-RU,en;q=0.9" -> берём "ru" если в supported.
    """
    if not header_value or not supported:
        return None
    for part in header_value.split(","):
        part = part.strip().split(";")[0].strip()
        if not part:
            continue
        code = part.split("-")[0].lower()
        if code in supported:
            return code
    return None


class LocaleMiddleware(BaseHTTPMiddleware):
    """
    Устанавливает локаль текущего запроса в ContextVar до вызова эндпоинтов.
    Источники: query-параметр lang (приоритет), заголовок Accept-Language.
    """
    def __init__(self, app, settings: Settings | None = None):
        super().__init__(app)
        self._settings = settings or Settings()

    async def dispatch(self, request: Request, call_next):
        supported = list(self._settings.supported_locales)
        default = self._settings.default_locale

        # Query lang переопределяет заголовок
        locale = request.query_params.get("lang", "").strip().lower()
        if locale and locale in supported:
            set_request_locale(locale)
        else:
            accept = request.headers.get("accept-language")
            locale = _parse_accept_language(accept, supported)
            set_request_locale(locale if locale else default)

        response = await call_next(request)
        return response


def install_locale_middleware(app, settings: Settings | None = None) -> None:
    """
    Добавляет LocaleMiddleware к FastAPI-приложению.
    Вызвать при создании app: install_locale_middleware(app) или install_locale_middleware(app, settings).
    """
    app.add_middleware(LocaleMiddleware, settings=settings)
