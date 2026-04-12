"""API v1: роутеры под префиксом /v1."""
from fastapi import APIRouter

from web.endpoints.v1 import (
    admin,
    arbiter,
    auth,
    autocomplete,
    dashboard,
    exchange_wallets,
    guarantor,
    invite,
    node,
    orders,
    profile,
    space_balances,
    space_exchange_services,
    space_participants,
    space_payment_forms,
    users,
    wallet_space_ui_prefs,
    wallets,
)

router = APIRouter(prefix="/v1", tags=["v1"])
router.include_router(auth.router)
router.include_router(admin.router)
router.include_router(autocomplete.router)
router.include_router(arbiter.router)
router.include_router(dashboard.router)
router.include_router(invite.router)
router.include_router(node.router)
router.include_router(profile.router)
router.include_router(space_participants.router)
router.include_router(guarantor.router)
router.include_router(exchange_wallets.router)
router.include_router(space_exchange_services.router)
router.include_router(space_payment_forms.router)
router.include_router(orders.router)
router.include_router(space_balances.router)
router.include_router(users.router)
router.include_router(wallet_space_ui_prefs.router)
router.include_router(wallets.router)
