"""PaymentFormResolutionService: приоритет override спейса над forms.yaml."""

from __future__ import annotations

import pytest

from core.bc import PaymentForm, PaymentFormField, PaymentFormFieldType
from services.payment_form_resolve import PaymentFormResolutionService

pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_resolve_uses_space_override() -> None:
    class _Row:
        form = {
            "fields": [
                {
                    "id": "custom",
                    "type": "string",
                    "required": True,
                    "label_key": "forms.test",
                }
            ]
        }

    class _OvRepo:
        async def get(self, space: str, code: str):
            assert space == "myspace"
            assert code == "PM"
            return _Row()

    class _YamlRepo:
        async def get_form(self, code: str):
            raise AssertionError("system yaml must not load when override exists")

    svc = PaymentFormResolutionService(_OvRepo(), _YamlRepo())
    form, src = await svc.resolve("myspace", "PM")
    assert src == "space"
    assert form is not None
    assert len(form.fields) == 1
    assert form.fields[0].id == "custom"


@pytest.mark.asyncio
async def test_resolve_falls_back_to_yaml() -> None:
    pf = PaymentForm(
        fields=[
            PaymentFormField(
                id="holder",
                type=PaymentFormFieldType.STRING,
                required=True,
                label_key="forms.requisite.holder_name",
            )
        ]
    )

    class _OvRepo:
        async def get(self, space: str, code: str):
            return None

    class _YamlRepo:
        async def get_form(self, code: str):
            return pf if code == "ABC" else None

    svc = PaymentFormResolutionService(_OvRepo(), _YamlRepo())
    form, src = await svc.resolve("myspace", "ABC")
    assert src == "system"
    assert form == pf


@pytest.mark.asyncio
async def test_resolve_none_for_unknown_code() -> None:
    class _OvRepo:
        async def get(self, space: str, code: str):
            return None

    class _YamlRepo:
        async def get_form(self, code: str):
            return None

    svc = PaymentFormResolutionService(_OvRepo(), _YamlRepo())
    form, src = await svc.resolve("myspace", "NOPE")
    assert src == "none"
    assert form is None


@pytest.mark.asyncio
async def test_resolve_system_ignores_space_override() -> None:
    pf = PaymentForm(
        fields=[
            PaymentFormField(
                id="from_yaml",
                type=PaymentFormFieldType.STRING,
                required=True,
                label_key="forms.requisite.x",
            )
        ]
    )

    class _OvRepo:
        async def get(self, space: str, code: str):
            raise AssertionError("override must not be read for resolve_system")

    class _YamlRepo:
        async def get_form(self, code: str):
            return pf if code == "PM" else None

    svc = PaymentFormResolutionService(_OvRepo(), _YamlRepo())
    form, src = await svc.resolve_system("PM")
    assert src == "system"
    assert form is not None
    assert form.fields[0].id == "from_yaml"


@pytest.mark.asyncio
async def test_resolve_empty_payment_code() -> None:
    class _O:
        async def get(self, space: str, code: str):
            return None

    class _Y:
        async def get_form(self, code: str):
            return None

    svc = PaymentFormResolutionService(_O(), _Y())
    form, src = await svc.resolve("myspace", "   ")
    assert src == "none"
    assert form is None
