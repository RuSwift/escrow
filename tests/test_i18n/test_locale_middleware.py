"""
Интеграционные тесты: middleware устанавливает локаль, эндпоинт возвращает перевод через _().
Используется AsyncClient + ASGITransport (sync Client с ASGITransport не поддерживается в httpx).
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from i18n import _
from web.middleware import install_locale_middleware


def _make_app(settings=None):
    """Минимальное приложение с locale middleware и эндпоинтом, возвращающим перевод."""
    app = FastAPI()
    install_locale_middleware(app, settings=settings)

    @app.get("/message")
    def get_message():
        return {"text": _("errors.node_already_init")}

    return app


@pytest.fixture
def app():
    """Приложение с locale middleware для тестов."""
    return _make_app()


@pytest.mark.asyncio
async def test_locale_from_accept_language_en(app):
    """Accept-Language: en -> ответ на английском."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/message", headers={"Accept-Language": "en"})
    r.raise_for_status()
    assert r.json()["text"] == "Node can only be initialized once"


@pytest.mark.asyncio
async def test_locale_from_accept_language_ru(app):
    """Accept-Language: ru -> ответ на русском."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/message", headers={"Accept-Language": "ru"})
    r.raise_for_status()
    assert r.json()["text"] == "Нода инициализируется только один раз"


@pytest.mark.asyncio
async def test_locale_from_accept_language_ru_ru(app):
    """Accept-Language: ru-RU нормализуется в ru."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/message", headers={"Accept-Language": "ru-RU,en;q=0.9"})
    r.raise_for_status()
    assert r.json()["text"] == "Нода инициализируется только один раз"


@pytest.mark.asyncio
async def test_locale_from_query_lang_overrides_header(app):
    """Query ?lang= переопределяет Accept-Language."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/message", params={"lang": "en"}, headers={"Accept-Language": "ru"})
    r.raise_for_status()
    assert r.json()["text"] == "Node can only be initialized once"


@pytest.mark.asyncio
async def test_locale_from_query_lang_ru(app):
    """Query ?lang=ru -> русский."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/message", params={"lang": "ru"})
    r.raise_for_status()
    assert r.json()["text"] == "Нода инициализируется только один раз"


@pytest.mark.asyncio
async def test_locale_default_when_no_header_no_query(app):
    """Без заголовка и query используется default_locale из Settings (ru)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/message")
    r.raise_for_status()
    assert r.json()["text"] == "Нода инициализируется только один раз"


@pytest.mark.asyncio
async def test_locale_unsupported_falls_back_to_default(app):
    """Неподдерживаемая локаль в Accept-Language -> default_locale."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/message", headers={"Accept-Language": "fr,de"})
    r.raise_for_status()
    assert r.json()["text"] == "Нода инициализируется только один раз"


@pytest.mark.asyncio
async def test_locale_custom_settings_default_locale():
    """При переданных settings default_locale используется, когда нет заголовка/query."""
    from settings import Settings
    settings = Settings(default_locale="en", supported_locales=["ru", "en"])
    app = _make_app(settings=settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        r = await client.get("/message")
    r.raise_for_status()
    assert r.json()["text"] == "Node can only be initialized once"
