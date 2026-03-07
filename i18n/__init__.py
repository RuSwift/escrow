"""
Мультиязычность: функция _ как прокси на ContextVar.
Локаль берётся из контекста запроса (устанавливается middleware) или из Settings.default_locale.
"""
from i18n.context import _request_locale, set_request_locale
from i18n.translations import get_translation


def _(key: str, **params: str) -> str:
    """
    Возвращает перевод для ключа в текущей локали.
    Локаль: из ContextVar (если установлен middleware) иначе Settings.default_locale.
    """
    locale = _request_locale.get()
    if locale is None:
        from settings import Settings
        locale = Settings().default_locale
    return get_translation(key, locale, **params)


__all__ = ["_", "set_request_locale", "get_translation"]
