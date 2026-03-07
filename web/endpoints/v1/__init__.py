"""API v1: роутеры под префиксом /v1."""
from fastapi import APIRouter

from web.endpoints.v1 import auth

router = APIRouter(prefix="/v1", tags=["v1"])
router.include_router(auth.router)
