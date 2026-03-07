"""
Тесты для i18n: функция _, get_translation, контекст локали.
"""
import pytest

from i18n import _, get_translation, set_request_locale
from i18n.context import _request_locale


def test_get_translation_returns_message_for_locale():
    """get_translation возвращает строку для заданной локали."""
    assert get_translation("errors.node_already_init", "ru") == "Нода инициализируется только один раз"
    assert get_translation("errors.node_already_init", "en") == "Node can only be initialized once"


def test_get_translation_normalizes_locale():
    """Локаль нормализуется (ru-RU -> ru)."""
    assert get_translation("errors.node_already_init", "ru-RU") == "Нода инициализируется только один раз"


def test_get_translation_fallback_to_en():
    """При отсутствии локали используется en."""
    msg = get_translation("errors.node_already_init", "fr")
    assert msg == "Node can only be initialized once"


def test_get_translation_fallback_to_key():
    """При отсутствии ключа возвращается сам ключ."""
    assert get_translation("missing.key.xyz", "ru") == "missing.key.xyz"


def test_get_translation_params():
    """Параметры подставляются в плейсхолдеры."""
    msg = get_translation("errors.pem_invalid_private_key", "ru", detail="wrong format")
    assert "wrong format" in msg
    assert "Невалидный PEM" in msg


def test_underscore_uses_default_locale_when_context_empty():
    """Когда ContextVar пуст (None), _ использует default_locale из Settings."""
    token = _request_locale.set(None)
    try:
        msg = _("errors.node_already_init")
        assert msg == "Нода инициализируется только один раз"
    finally:
        _request_locale.reset(token)


def test_underscore_uses_context_when_set():
    """Когда контекст установлен, _ использует его локаль."""
    token = _request_locale.set("en")
    try:
        assert _("errors.node_already_init") == "Node can only be initialized once"
        _request_locale.set("ru")
        assert _("errors.node_already_init") == "Нода инициализируется только один раз"
    finally:
        _request_locale.reset(token)


def test_underscore_with_params():
    """_() с параметрами подставляет их в строку."""
    token = _request_locale.set("en")
    try:
        msg = _("errors.access_denied_deal_owner", owner_did="did:1", deal_uid="deal-1", attempted_by="did:2")
        assert "did:1" in msg and "deal-1" in msg and "did:2" in msg
    finally:
        _request_locale.reset(token)
