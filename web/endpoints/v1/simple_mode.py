"""Simple UI: JSON API с контекстом арбитра в path: /v1/arbiter/{arbiter_space_did}/..."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select

from core.exceptions import SpacePermissionDenied
from db.models import Deal, PaymentRequest
from services.arbiter_path import ArbiterPathResolveService
from services.payment_request import PaymentRequestService
from services.simple_resolve import ResolvedDeal, ResolvedPaymentRequest, SimpleResolveService
from web.endpoints.dependencies import (
    CurrentWalletUser,
    get_arbiter_path_resolve_service,
    get_payment_request_service,
    get_simple_resolve_service,
)
from web.endpoints.v1.schemas.payment_requests import (
    PaymentRequestAcceptBody,
    PaymentRequestCreateBody,
    PaymentRequestCreateResponse,
    PaymentRequestDeactivateBody,
    PaymentRequestDeactivateResponse,
    PaymentRequestExtendBody,
    PaymentRequestHandshakeResponse,
    PaymentRequestListResponse,
    PaymentRequestOut,
    PaymentRequestResellBody,
    PaymentRequestResellResponse,
    PaymentRequestViewerRoleBody,
    PaymentRequestViewerRoleResponse,
)
from web.endpoints.v1.schemas.simple_resolve import SimpleDealOut, SimpleResolveResponse

router = APIRouter(prefix="/arbiter/{arbiter_space_did}", tags=["simple"])


async def get_resolved_arbiter_did(
    arbiter_space_did: str,
    resolver: ArbiterPathResolveService = Depends(get_arbiter_path_resolve_service),
) -> str:
    did = await resolver.to_arbiter_did(arbiter_space_did)
    if not did:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Арбитр не найден",
        )
    return did


ResolvedArbiterDid = Annotated[str, Depends(get_resolved_arbiter_did)]


@router.get("/resolve/{public_uid}", response_model=SimpleResolveResponse)
async def resolve_simple_context(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    public_uid: str,
    svc: SimpleResolveService = Depends(get_simple_resolve_service),
    payment_svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Контекст для /arbiter/{arbiter}/deal/{segment}: PaymentRequest по uid или public_ref, иначе Deal по uid."""
    arb = arbiter_did
    result = await svc.resolve_public_uid(public_uid, arbiter_space_did=arb)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка или сделка не найдена",
        )
    if isinstance(result, ResolvedPaymentRequest):
        row, nick = await payment_svc.maybe_auto_resell_on_resolve(
            result.row,
            result.space_nickname,
            viewer_did=user.did,
            arbiter_did=arbiter_did,
            segment=result.segment,
        )
        await payment_svc.ensure_commissioner_view(row, user.did)
        # If PR already linked to Deal, render Deal context (Lockbox stage),
        # even when URL uses payment_request uid/public_ref.
        if row.deal_id is not None:
            res_deal = await payment_svc._session.execute(
                select(Deal).where(Deal.pk == row.deal_id).limit(1)
            )
            deal_row = res_deal.scalar_one_or_none()
            if deal_row is not None:
                return SimpleResolveResponse(
                    kind="deal_only",
                    viewer_did=user.did,
                    payment_request_pk=int(row.pk),
                    payment_request_public_ref=str(row.public_ref or ""),
                    payment_request_heading=str(row.heading or "") or None,
                    payment_request=PaymentRequestOut.from_model(
                        row,
                        space_nickname=nick,
                        viewer_did=user.did,
                    ),
                    deal=SimpleDealOut.from_model(deal_row),
                )
        return SimpleResolveResponse(
            kind="payment_request_only",
            viewer_did=user.did,
            payment_request=PaymentRequestOut.from_model(
                row,
                space_nickname=nick,
                viewer_did=user.did,
            ),
            deal=None,
        )
    assert isinstance(result, ResolvedDeal)
    # Try to attach PaymentRequest context for deal_only UI.
    pr_pk: Optional[int] = None
    pr_ref: Optional[str] = None
    pr_heading: Optional[str] = None
    pr_out: Optional[PaymentRequestOut] = None
    res_pr = await svc._session.execute(
        select(PaymentRequest)
        .where(PaymentRequest.deal_id == result.row.pk)
        .limit(1)
    )
    pr_model = res_pr.scalar_one_or_none()
    if pr_model is not None:
        pr_pk = int(pr_model.pk)
        pr_ref = str(pr_model.public_ref or "") or None
        pr_heading = str(pr_model.heading or "") or None
        pr_out = PaymentRequestOut.from_model(pr_model, space_nickname=None, viewer_did=user.did)
    return SimpleResolveResponse(
        kind="deal_only",
        viewer_did=user.did,
        payment_request_pk=pr_pk,
        payment_request_public_ref=pr_ref,
        payment_request_heading=pr_heading,
        payment_request=pr_out,
        deal=SimpleDealOut.from_model(result.row),
    )


@router.get("/payment-requests", response_model=PaymentRequestListResponse)
async def list_payment_requests(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    svc: PaymentRequestService = Depends(get_payment_request_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=512),
):
    """Список заявок PaymentRequest для текущего кошелька в контексте арбитра."""
    try:
        rows, total = await svc.list_payment_requests(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            arbiter_did=arbiter_did,
            page=page,
            page_size=page_size,
            q=q,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return PaymentRequestListResponse(
        items=[
            PaymentRequestOut.from_model(
                r, space_nickname=nick, viewer_did=user.did
            )
            for r, nick in rows
        ],
        total=total,
    )


@router.post(
    "/payment-requests",
    response_model=PaymentRequestCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_request(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    body: PaymentRequestCreateBody,
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Создать заявку fiat↔stable (без записи в deal); arbiter_did из path."""
    try:
        row, space_nickname = await svc.create_payment_request(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            arbiter_did=arbiter_did,
            direction=body.direction,
            primary_leg=body.primary_leg.model_dump(),
            counter_leg=body.counter_leg.model_dump(),
            heading=body.heading,
            lifetime=body.lifetime,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ValueError as e:
        msg = str(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from e
    return PaymentRequestCreateResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        )
    )


@router.post(
    "/payment-requests/{pk}/deactivate",
    response_model=PaymentRequestDeactivateResponse,
)
async def deactivate_payment_request(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    body: PaymentRequestDeactivateBody,
    svc: PaymentRequestService = Depends(get_payment_request_service),
    pk: int = Path(..., ge=1),
):
    """Деактивировать заявку после подтверждения номера (pk)."""
    try:
        row, space_nickname = await svc.deactivate_payment_request(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            arbiter_did=arbiter_did,
            pk=pk,
            confirm_pk=body.confirm_pk,
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ValueError as e:
        msg = str(e)
        if msg == "Заявка не найдена":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from e
    return PaymentRequestDeactivateResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        )
    )


@router.post(
    "/payment-requests/{pk}/extend",
    response_model=PaymentRequestHandshakeResponse,
)
async def extend_payment_request(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    svc: PaymentRequestService = Depends(get_payment_request_service),
    pk: int = Path(..., ge=1),
    body: PaymentRequestExtendBody | None = None,
):
    """Владелец заявки: продлить срок действия (expires_at) на 72 часа."""
    try:
        row, space_nickname = await svc.extend_payment_request_owner(
            wallet_address=user.wallet_address,
            owner_did=user.did,
            standard=user.standard,
            arbiter_did=arbiter_did,
            pk=pk,
            lifetime=(body.lifetime if body is not None else "72h"),
        )
    except SpacePermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except ValueError as e:
        code = str(e)
        if code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Заявка не найдена",
            ) from e
        if code == "not_owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Продлить заявку может только её владелец",
            ) from e
        if code == "invalid_lifetime":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный срок продления",
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=code,
        ) from e
    return PaymentRequestHandshakeResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        ),
        deal_uid=None,
    )


_RESELL_ERR_DETAIL = {
    "not_found": "Заявка не найдена",
    "public_uid_required": "Идентификатор заявки обязателен",
    "actor_required": "Не удалось определить пользователя",
    "request_deactivated": "Заявка снята с публикации",
    "request_already_accepted": "Заявка уже принята, этап «Условия» недоступен",
    "owner_cannot_resell": "Перепродажа недоступна автору заявки",
    "intermediary_percent_invalid": "Некорректный процент комиссии",
    "intermediary_percent_range": "Процент должен быть от 0.1 до 100",
    "commissioners_invalid": "Некорректная структура комиссионеров",
}


_ACCEPT_ERR_DETAIL = {
    "not_found": "Заявка не найдена",
    "actor_required": "Не удалось определить пользователя",
    "request_deactivated": "Заявка снята с публикации",
    "request_already_accepted": "Заявка уже связана со сделкой",
    "owner_cannot_accept": "Принять может только контрагент, не автор заявки",
    "counter_stable_amount_required": "Укажите согласованную сумму стейбла для приёма",
    "counter_leg_invalid": "Некорректная нога получения",
    "invalid_direction": "Некорректное направление заявки",
    "counterparty_already_locked": "Условия уже согласуются с другим контрагентом",
}

_CONFIRM_ERR_DETAIL = {
    "not_found": "Заявка не найдена",
    "not_owner": "Подтвердить может только автор заявки",
    "already_confirmed": "Заявка уже подтверждена",
    "nothing_to_confirm": "Нет шага контрагента для подтверждения",
    "signer_did_empty": "Некорректный DID подписанта",
    "wallet_user_not_found_for_did": "Участник сделки не найден в системе",
    "primary_wallet_empty": "Не задан primary wallet участника",
    "arbiter_did_empty": "Не указан арбитр",
    "arbiter_wallet_not_found": "Не найден кошелёк арбитра для подписи",
}

_WITHDRAW_ERR_DETAIL = {
    "not_found": "Заявка не найдена",
    "cannot_withdraw": "Отозвать принятие нельзя после создания сделки",
    "not_accepting_party": "Отозвать может только контрагент, который принял заявку",
    "no_pending_acceptance": "Нет ожидающего подтверждения принятия",
}

_REJECT_ERR_DETAIL = {
    "not_found": "Заявка не найдена",
    "not_owner": "Отклонить может только автор заявки",
    "already_confirmed": "Заявка уже подтверждена",
    "nothing_to_reject": "Нет ожидающего принятия для отклонения",
}

_VIEWER_ROLE_ERR_DETAIL = {
    "not_found": "Заявка не найдена",
    "request_deactivated": "Заявка деактивирована",
    "request_already_accepted": "Заявка уже подтверждена",
    "actor_required": "Не определён пользователь",
    "owner_cannot_resell": "Автор заявки не может менять роль на этой странице",
    "no_viewer_slot": "Слот участника не найден (обновите страницу)",
}


@router.post(
    "/payment-requests/{public_uid}/resell",
    response_model=PaymentRequestResellResponse,
)
async def resell_payment_request(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    public_uid: str,
    body: PaymentRequestResellBody,
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Посредник (не владелец): слот i_<…> или обновление своего; % по умолчанию 0.5."""
    try:
        row, space_nickname = await svc.apply_resell_intermediary(
            actor_did=user.did,
            arbiter_did=arbiter_did,
            public_uid=public_uid,
            intermediary_percent=body.intermediary_percent,
        )
    except ValueError as e:
        code = str(e)
        detail = _RESELL_ERR_DETAIL.get(code, code)
        if code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e
    return PaymentRequestResellResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        )
    )


@router.post(
    "/payment-requests/{pk}/viewer-role",
    response_model=PaymentRequestViewerRoleResponse,
)
async def set_payment_request_viewer_role(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    pk: int = Path(..., ge=1),
    body: PaymentRequestViewerRoleBody | None = None,
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Явно зафиксировать роль зрителя на стадии согласования условий (контрагент или посредник)."""
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role_required")
    try:
        row, space_nickname = await svc.set_payment_request_viewer_role(
            actor_did=user.did,
            arbiter_did=arbiter_did,
            pk=pk,
            role=body.role,
            parent_ref=body.parent_ref,
        )
    except ValueError as e:
        code = str(e)
        detail = _VIEWER_ROLE_ERR_DETAIL.get(code, code)
        if code == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from e
    return PaymentRequestViewerRoleResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        )
    )


@router.post(
    "/payment-requests/{pk}/accept",
    response_model=PaymentRequestHandshakeResponse,
)
async def accept_payment_request(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    pk: int = Path(..., ge=1),
    body: PaymentRequestAcceptBody | None = None,
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Контрагент фиксирует согласие с условиями (first lock); при обсуждаемой сумме — передать сумму."""
    try:
        amt = body.counter_stable_amount if body else None
        row, space_nickname = await svc.accept_payment_request_counterparty(
            actor_did=user.did,
            arbiter_did=arbiter_did,
            pk=pk,
            counter_stable_amount=amt,
        )
    except ValueError as e:
        code = str(e)
        detail = _ACCEPT_ERR_DETAIL.get(code, code)
        if code == "counterparty_already_locked":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from e
        if code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e
    return PaymentRequestHandshakeResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        ),
        deal_uid=None,
    )


@router.post(
    "/payment-requests/{pk}/confirm",
    response_model=PaymentRequestHandshakeResponse,
)
async def confirm_payment_request(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    pk: int = Path(..., ge=1),
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Владелец подтверждает заявку после accept контрагента; создаётся Deal."""
    try:
        row, space_nickname, deal_uid = await svc.confirm_payment_request_owner(
            owner_did=user.did,
            arbiter_did=arbiter_did,
            pk=pk,
        )
    except ValueError as e:
        code = str(e)
        detail = _CONFIRM_ERR_DETAIL.get(code, code)
        if code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from e
        if code == "not_owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e
    return PaymentRequestHandshakeResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        ),
        deal_uid=deal_uid,
    )


@router.post(
    "/payment-requests/{pk}/withdraw-acceptance",
    response_model=PaymentRequestHandshakeResponse,
)
async def withdraw_payment_request_acceptance(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    pk: int = Path(..., ge=1),
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Контрагент отзывает своё принятие до подтверждения владельцем."""
    try:
        row, space_nickname = await svc.withdraw_payment_request_acceptance(
            actor_did=user.did,
            arbiter_did=arbiter_did,
            pk=pk,
        )
    except ValueError as e:
        code = str(e)
        detail = _WITHDRAW_ERR_DETAIL.get(code, code)
        if code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from e
        if code == "not_accepting_party":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e
    return PaymentRequestHandshakeResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        ),
        deal_uid=None,
    )


@router.post(
    "/payment-requests/{pk}/reject-acceptance",
    response_model=PaymentRequestHandshakeResponse,
)
async def reject_payment_request_acceptance(
    arbiter_did: ResolvedArbiterDid,
    user: CurrentWalletUser,
    pk: int = Path(..., ge=1),
    svc: PaymentRequestService = Depends(get_payment_request_service),
):
    """Владелец отклоняет принятие контрагента: сбрасывает acceptance, откатывает counter_leg при наличии snapshot."""
    try:
        row, space_nickname = await svc.reject_payment_request_owner(
            owner_did=user.did,
            arbiter_did=arbiter_did,
            pk=pk,
        )
    except ValueError as e:
        code = str(e)
        detail = _REJECT_ERR_DETAIL.get(code, code)
        if code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from e
        if code == "not_owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            ) from e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from e
    return PaymentRequestHandshakeResponse(
        payment_request=PaymentRequestOut.from_model(
            row, space_nickname=space_nickname, viewer_did=user.did
        ),
        deal_uid=None,
    )
