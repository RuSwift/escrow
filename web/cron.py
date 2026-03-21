"""
Фоновые задачи по расписанию (аналог garantex/cron).

Запуск из корня репозитория:
  .venv/bin/python web/cron.py

Параллельно:
  - Forex и Rapira: обновление кэша котировок каждую минуту;
  - ЦБ РФ (Cbr): каждый час.

Нужны Redis и настройки ratios в .env (для Rapira — ключи RATIOS_RAPIRA_*).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# корень репозитория в PYTHONPATH при ``python web/cron.py``
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from redis.asyncio import Redis

from db import init_db
from services.dashboard import DashboardService
from services.ratios.cbr import CbrEngine
from services.ratios.forex import ForexEngine
from services.ratios.rapira import RapiraEngine
from settings import Settings

logger = logging.getLogger(__name__)

FOREX_RAPIRA_SEC = 60.0
CBR_SEC = 3600.0


async def _loop_forex_rapira(redis: Redis, settings: Settings) -> None:
    svc = DashboardService(redis, settings)
    while True:
        try:
            result = await svc.update_ratios(
                only_engine_types=(ForexEngine, RapiraEngine),
            )
            for label, row in result.items():
                if not row.get("ok"):
                    logger.warning("ratios %s: %s", label, row.get("error"))
                else:
                    logger.debug("ratios %s: ok", label)
        except Exception:
            logger.exception("forex/rapira ratios refresh failed")
        await asyncio.sleep(FOREX_RAPIRA_SEC)


async def _loop_cbr(redis: Redis, settings: Settings) -> None:
    svc = DashboardService(redis, settings)
    while True:
        try:
            result = await svc.update_ratios(only_engine_types=(CbrEngine,))
            for label, row in result.items():
                if not row.get("ok"):
                    logger.warning("ratios %s: %s", label, row.get("error"))
                else:
                    logger.debug("ratios %s: ok", label)
        except Exception:
            logger.exception("cbr ratios refresh failed")
        await asyncio.sleep(CBR_SEC)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings()
    init_db(settings.database)
    redis = Redis.from_url(settings.redis.url, decode_responses=True)
    logger.info(
        "cron: forex+rapira every %ss, cbr every %ss",
        int(FOREX_RAPIRA_SEC),
        int(CBR_SEC),
    )
    try:
        await asyncio.gather(
            _loop_forex_rapira(redis, settings),
            _loop_cbr(redis, settings),
        )
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
