"""API v1: роутеры под префиксом /v1."""
from fastapi import APIRouter

from web.endpoints.v1 import admin, arbiter, auth, node, profile, users, wallets

router = APIRouter(prefix="/v1", tags=["v1"])
router.include_router(auth.router)
router.include_router(admin.router)
router.include_router(arbiter.router)
router.include_router(node.router)
router.include_router(profile.router)
router.include_router(users.router)
router.include_router(wallets.router)
