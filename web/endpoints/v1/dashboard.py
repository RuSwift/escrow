"""
API статистики дашборда (пользователи, менеджеры, кошельки, арбитраж).
Ориентир: garantex node.py GET /api/dashboard/statistics.

Котировки: GET ``/ratios`` — снимок из БД (спотовые движки); JWT пользователя
(TRON/Web3) или cookie ``main_auth_token``. Статистика ``GET /`` — только админ.
"""
import logging

from sqlalchemy import func, or_, select

from fastapi import APIRouter

from db.models import Wallet, WalletUser
from web.endpoints.dependencies import (
    CurrentWalletUser,
    DashboardStateRepoDep,
    DbSession,
    RequireAdminDepends,
)

logger = logging.getLogger(__name__)
from web.endpoints.v1.schemas.dashboard_ratios import ListRatiosResponse
from web.endpoints.v1.schemas.node import DashboardStatisticsResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardStatisticsResponse)
async def get_dashboard_statistics(
    db: DbSession,
    _admin: RequireAdminDepends,
):
    """
    Статистика для дашборда: количество пользователей, менеджеров, кошельков, кошельков арбитража.
    Требует авторизации админа.
    """
    users_result = await db.execute(select(func.count(WalletUser.id)))
    users_count = users_result.scalar() or 0

    managers_result = await db.execute(
        select(func.count(WalletUser.id)).where(
            WalletUser.access_to_admin_panel.is_(True)
        )
    )
    managers_count = managers_result.scalar() or 0

    wallets_result = await db.execute(select(func.count(Wallet.id)))
    wallets_count = wallets_result.scalar() or 0

    arbiter_result = await db.execute(
        select(func.count(Wallet.id)).where(
            or_(Wallet.role == "arbiter", Wallet.role == "arbiter-backup")
        )
    )
    arbiter_wallets_count = arbiter_result.scalar() or 0

    return DashboardStatisticsResponse(
        users_count=users_count,
        managers_count=managers_count,
        wallets_count=wallets_count,
        arbiter_wallets_count=arbiter_wallets_count,
    )


@router.get(
    "/ratios",
    response_model=ListRatiosResponse,
    summary="Список котировок по system_currencies",
)
async def list_dashboard_ratios(
    dashboard_repo: DashboardStateRepoDep,
    _user: CurrentWalletUser,
):
    """
    Кросс-курсы из снимка ``dashboard_state.ratios`` (обновляется cron после прогрева Redis).
    При отсутствии строки в БД — пустой объект ``{}`` (200). BestChange не участвует.
    """
    raw = await dashboard_repo.get_ratios()
    if raw is None:
        logger.warning("dashboard_state: row id=1 missing, returning empty ratios")
        data: dict = {}
    else:
        data = raw
    return ListRatiosResponse.model_validate(data)
