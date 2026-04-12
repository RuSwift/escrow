"""Резолвинг формы реквизитов: переопределение спейса или system forms.yaml."""

from __future__ import annotations

from typing import Literal

from pydantic import ValidationError

from core.bc import PaymentForm
from repos.bestchange import PaymentFormsYamlRepository
from repos.space_payment_form import SpacePaymentFormOverrideRepository

PaymentFormSource = Literal["space", "system", "none"]


class PaymentFormResolutionService:
    """space override → иначе PaymentFormsYamlRepository (disk/settings)."""

    def __init__(
        self,
        overrides: SpacePaymentFormOverrideRepository,
        yaml_forms: PaymentFormsYamlRepository,
    ) -> None:
        self._overrides = overrides
        self._yaml_forms = yaml_forms

    async def resolve(
        self,
        space: str,
        payment_code: str,
    ) -> tuple[PaymentForm | None, PaymentFormSource]:
        pc = (payment_code or "").strip()
        sp = (space or "").strip()
        if not pc:
            return None, "none"
        row = await self._overrides.get(sp, pc)
        if row is not None:
            try:
                return PaymentForm.model_validate(row.form), "space"
            except ValidationError:
                return None, "none"
        base = await self._yaml_forms.get_form(pc)
        if base is not None:
            return base, "system"
        return None, "none"
