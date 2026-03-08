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


__all__ = ["get_translation", "get_translations_for_locale"]
