"""Единая логика effective-формы реквизитов для направления (exchange_services).

Кастом в ``requisites_form_schema`` (непустой ``fields``) имеет приоритет;
иначе — тот же резолвинг, что для каталога: override спейса → ``forms.yaml``.
Используется в API и при обработке заявок.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ValidationError

from core.bc import PaymentForm
from services.payment_form_resolve import PaymentFormResolutionService

EffectiveRequisitesFormSource = Literal["exchange_service", "space", "system", "none"]


def payment_form_from_requisites_schema(raw: Any) -> PaymentForm | None:
    """Вернуть валидную форму из JSON направления или ``None`` (пусто / невалидно)."""
    if not isinstance(raw, dict):
        return None
    fields = raw.get("fields")
    if not isinstance(fields, list) or len(fields) < 1:
        return None
    try:
        return PaymentForm.model_validate(raw)
    except ValidationError:
        return None


async def resolve_effective_requisites_form(
    *,
    space: str,
    payment_code: str | None,
    requisites_form_schema: Any,
    resolver: PaymentFormResolutionService,
) -> tuple[PaymentForm | None, EffectiveRequisitesFormSource]:
    custom = payment_form_from_requisites_schema(requisites_form_schema)
    if custom is not None:
        return custom, "exchange_service"
    base, src = await resolver.resolve(space, payment_code or "")
    return base, src
