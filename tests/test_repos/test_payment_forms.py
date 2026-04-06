"""
PaymentFormsYamlRepository: кеш Redis и чтение forms.yaml.

Без PostgreSQL::

    ESCROW_PYTEST_NO_DB=1 pytest tests/test_repos/test_payment_forms.py -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.bc import PaymentFormsYaml
from repos.bestchange import (
    _REDIS_PAYMENT_FORMS_DATA,
    _REDIS_PAYMENT_FORMS_SID,
    PaymentFormsYamlRepository,
)
from settings import Settings

pytestmark = pytest.mark.no_db

_MINIMAL_YAML = """
meta:
  schema_version: 1
forms:
  ABC:
    fields:
      - id: holder_name
        type: string
        required: true
        label_key: forms.requisite.holder_name
"""


class _FakePipeline:
    def __init__(self, store: dict) -> None:
        self._store = store
        self._sets: list[tuple[str, str]] = []

    def set(self, key: str, value: str, ex: int | None = None) -> None:  # noqa: ARG002
        self._sets.append((key, value))

    async def execute(self) -> None:
        for k, v in self._sets:
            self._store[k] = v
        self._sets.clear()


class FakeRedis:
    """Минимальная имитация redis.asyncio для репозитория форм."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self.store.pop(k, None)

    def pipeline(self) -> _FakePipeline:
        p = _FakePipeline(self.store)
        # подменяем: FakePipeline пишет в тот же store
        return p


@pytest.fixture
def tmp_forms(tmp_path: Path) -> Path:
    p = tmp_path / "forms.yaml"
    p.write_text(_MINIMAL_YAML.strip() + "\n", encoding="utf-8")
    return p


@pytest.fixture
def repo(tmp_forms: Path) -> PaymentFormsYamlRepository:
    settings = Settings()
    settings.payment_forms_yaml = str(tmp_forms)
    return PaymentFormsYamlRepository(
        session=MagicMock(),
        redis=FakeRedis(),
        settings=settings,
    )


async def test_get_form_returns_fields(repo: PaymentFormsYamlRepository) -> None:
    form = await repo.get_form("ABC")
    assert form is not None
    assert len(form.fields) == 1
    assert form.fields[0].id == "holder_name"


async def test_get_form_unknown_none(repo: PaymentFormsYamlRepository) -> None:
    assert await repo.get_form("NOPE") is None


async def test_get_form_empty_code_none(repo: PaymentFormsYamlRepository) -> None:
    assert await repo.get_form("") is None
    assert await repo.get_form("   ") is None


async def test_get_all_roundtrip(repo: PaymentFormsYamlRepository) -> None:
    data = await repo.get_all()
    assert data is not None
    assert isinstance(data, PaymentFormsYaml)
    assert "ABC" in data.forms


async def test_cache_second_hit_uses_redis(tmp_forms: Path) -> None:
    settings = Settings()
    settings.payment_forms_yaml = str(tmp_forms)
    redis = FakeRedis()
    r = PaymentFormsYamlRepository(session=MagicMock(), redis=redis, settings=settings)

    assert await r.get_all() is not None
    sid_first = redis.store.get(_REDIS_PAYMENT_FORMS_SID)
    assert sid_first is not None
    await r.get_all()
    assert redis.store.get(_REDIS_PAYMENT_FORMS_SID) == sid_first


async def test_patch_clears_cache_then_reloads(tmp_forms: Path) -> None:
    settings = Settings()
    settings.payment_forms_yaml = str(tmp_forms)
    redis = FakeRedis()
    r = PaymentFormsYamlRepository(session=MagicMock(), redis=redis, settings=settings)
    await r.get_all()
    assert _REDIS_PAYMENT_FORMS_SID in redis.store
    await r.patch()
    assert _REDIS_PAYMENT_FORMS_SID not in redis.store
    assert _REDIS_PAYMENT_FORMS_DATA not in redis.store
    again = await r.get_all()
    assert again is not None
    assert _REDIS_PAYMENT_FORMS_SID in redis.store


async def test_missing_file_none(tmp_path: Path) -> None:
    settings = Settings()
    settings.payment_forms_yaml = str(tmp_path / "missing.yaml")
    redis = FakeRedis()
    r = PaymentFormsYamlRepository(session=MagicMock(), redis=redis, settings=settings)
    assert await r.get_all() is None
    assert await r.get_form("ABC") is None
