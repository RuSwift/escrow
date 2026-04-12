"""Управление переопределениями форм payment_code в спейсе (owner only)."""

from __future__ import annotations

from pydantic import ValidationError

from core.bc import PaymentForm
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SpacePaymentFormOverride
from repos.space_payment_form import SpacePaymentFormOverrideRepository
from services.payment_form_resolve import PaymentFormResolutionService
from services.space import SpaceService
from settings import Settings


class SpacePaymentFormAdminError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class SpacePaymentFormAdminService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ) -> None:
        self._session = session
        self._repo = SpacePaymentFormOverrideRepository(
            session=session, redis=redis, settings=settings
        )
        self._space = SpaceService(session=session, redis=redis, settings=settings)
        from repos.bestchange import PaymentFormsYamlRepository

        self._resolve = PaymentFormResolutionService(
            overrides=self._repo,
            yaml_forms=PaymentFormsYamlRepository(
                session=session, redis=redis, settings=settings
            ),
        )

    async def get_effective(
        self,
        space: str,
        actor_wallet_address: str,
        payment_code: str,
    ):
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        form, source = await self._resolve.resolve(space, payment_code)
        return form, source

    async def list_overrides(
        self, space: str, actor_wallet_address: str
    ) -> list[SpacePaymentFormOverride]:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        return await self._repo.list_for_space(space)

    async def put_override(
        self,
        space: str,
        actor_wallet_address: str,
        payment_code: str,
        form: dict,
    ) -> SpacePaymentFormOverride:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        code = (payment_code or "").strip()
        if not code:
            raise SpacePaymentFormAdminError("payment_code_required", "payment_code is required")
        try:
            validated = PaymentForm.model_validate(form)
        except ValidationError as e:
            raise SpacePaymentFormAdminError("invalid_form", str(e)) from e
        row = await self._repo.upsert(
            space, code, form=validated.model_dump(mode="json")
        )
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def delete_override(
        self,
        space: str,
        actor_wallet_address: str,
        payment_code: str,
    ) -> bool:
        await self._space._ensure_owner_and_owner_id(space, actor_wallet_address)
        code = (payment_code or "").strip()
        if not code:
            return False
        ok = await self._repo.delete(space, code)
        if ok:
            await self._session.commit()
        return ok
