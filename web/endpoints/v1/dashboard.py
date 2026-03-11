"""
API статистики дашборда (пользователи, менеджеры, кошельки, арбитраж).
Ориентир: garantex node.py GET /api/dashboard/statistics.
"""
from sqlalchemy import func, or_, select

from fastapi import APIRouter

from db.models import Wallet, WalletUser
from web.endpoints.dependencies import DbSession, RequireAdminDepends
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
