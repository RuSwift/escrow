"""
Загрузка переводов и функция get_translation.
Переводы хранятся в JSON в i18n/translations/ (ru.json, en.json).
"""
from pathlib import Path
import json

_TRANSLATIONS: dict[str, dict[str, str]] = {}
_TRANSLATIONS_DIR = Path(__file__).resolve().parent / "translations"


def _load_translations() -> dict[str, dict[str, str]]:
    """Ленивая загрузка словарей переводов из JSON-файлов."""
    global _TRANSLATIONS
    if _TRANSLATIONS:
        return _TRANSLATIONS
    if not _TRANSLATIONS_DIR.is_dir():
        _TRANSLATIONS = {}
        return _TRANSLATIONS
    for path in _TRANSLATIONS_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                _TRANSLATIONS[path.stem.lower()] = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
    return _TRANSLATIONS


def get_translation(key: str, locale: str, **params: str) -> str:
    """
    Возвращает перевод по ключу для данной локали.
    Нормализует locale (ru-RU -> ru), подставляет params в плейсхолдеры {name}.
    Fallback: выбранная локаль -> en -> ключ как строка.
    """
    translations = _load_translations()
    locale = locale.split("-")[0].lower() if locale else "en"
    table = translations.get(locale) or translations.get("en") or {}
    msg = table.get(key, key)
    if params:
        try:
            msg = msg.format(**params)
        except KeyError:
            pass
    return msg


def get_translations_for_locale(locale: str) -> dict[str, str]:
    """Возвращает полный словарь переводов для локали (с fallback на en)."""
    translations = _load_translations()
    locale = locale.split("-")[0].lower() if locale else "en"
    table = dict(translations.get("en") or {})
    table.update(translations.get(locale) or {})
    return table


def supported_locales() -> frozenset[str]:
    """Коды языков из i18n/translations/*.json (имена файлов без .json)."""
    translations = _load_translations()
    if not translations:
        return frozenset({"en"})
    return frozenset(translations.keys())


def locale_from_accept_language(header: str | None) -> str | None:
    """
    Первый тег из заголовка Accept-Language, если он ru или en; иначе None.

    Пример: ``en-US,en;q=0.9,ru;q=0.8`` → ``en``.
    """
    if not header or not str(header).strip():
        return None
    for part in str(header).split(","):
        tag = part.strip().split(";", maxsplit=1)[0].strip()
        if not tag:
            continue
        code = tag.split("-", maxsplit=1)[0].lower()
        if code in ("ru", "en"):
            return code
    return None


def normalize_locale(locale: str | None) -> str:
    """
    Код языка как в i18n (en, ru). BCP-47 сводится к основному тегу (ru-RU -> ru).
    Если не задан или неизвестен — en.
    """
    if not locale:
        return "en"
    code = locale.split("-")[0].lower()
    if code in supported_locales():
        return code
    return "en"


__all__ = [
    "get_translation",
    "get_translations_for_locale",
    "locale_from_accept_language",
    "normalize_locale",
    "supported_locales",
]
