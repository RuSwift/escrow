"""
ContextVar для локали текущего запроса.
Устанавливается middleware; используется функцией _() для выбора языка перевода.
"""
from contextvars import ContextVar

_request_locale: ContextVar[str | None] = ContextVar("request_locale", default=None)


def get_request_locale() -> str | None:
    """Возвращает локаль текущего запроса или None, если контекст не установлен."""
    return _request_locale.get()


def set_request_locale(locale: str) -> None:
    """Устанавливает локаль для текущего контекста (вызывается из middleware)."""
    _request_locale.set(locale)


__all__ = ["_request_locale", "get_request_locale", "set_request_locale"]
