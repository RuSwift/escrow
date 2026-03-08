"""
Health check endpoints for liveness and readiness probes.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from web.endpoints.dependencies import DbSession, RedisClient

router = APIRouter(tags=["health"])


@router.get("/liveness")
async def liveness():
    """Liveness probe: process is running."""
    return {"status": "ok"}


@router.get("/readiness")
async def readiness(db: DbSession, redis: RedisClient):
    """Readiness probe: app is ready to accept traffic (DB and Redis up)."""
    checks = {"database": "ok", "redis": "ok"}
    errors = []
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = "error"
        errors.append(f"database: {e!s}")
    try:
        await redis.ping()
    except Exception as e:
        checks["redis"] = "error"
        errors.append(f"redis: {e!s}")
    if errors:
        raise HTTPException(
            status_code=503,
            detail={"status": "unhealthy", "checks": checks, "errors": errors},
        )
    return {"status": "ok", "checks": checks}
