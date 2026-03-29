"""i18n.translations: вспомогательные функции."""

from i18n.translations import locale_from_accept_language


def test_locale_from_accept_language_first_tag():
    assert locale_from_accept_language("en-US,en;q=0.9,ru;q=0.8") == "en"


def test_locale_from_accept_language_ru():
    assert locale_from_accept_language("ru-RU,en;q=0.5") == "ru"


def test_locale_from_accept_language_unsupported_returns_none():
    assert locale_from_accept_language("de-DE,fr;q=0.9") is None


def test_locale_from_accept_language_empty():
    assert locale_from_accept_language(None) is None
    assert locale_from_accept_language("") is None
