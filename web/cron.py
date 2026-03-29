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
import time
from pathlib import Path
from typing import Any

# корень репозитория в PYTHONPATH при ``python web/cron.py``
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from redis.asyncio import Redis

import db as db_module
from repos.dashboard import DashboardStateRepository
from services.dashboard import DashboardService
from services.multisig_wallet.maintenance import MultisigWalletMaintenanceService
from services.ratios.cbr import CbrEngine
from services.ratios.forex import ForexEngine
from services.ratios.rapira import RapiraEngine
from settings import Settings

logger = logging.getLogger(__name__)

FOREX_RAPIRA_SEC = 60.0
CBR_SEC = 3600.0
MULTISIG_WALLET_SEC = 10.0


async def _merge_ratios_after_tick(
    redis: Redis,
    settings: Settings,
    only_engine_types: tuple[type, ...],
    update_result: dict[str, Any],
) -> None:
    """Частичное обновление ``dashboard_state.ratios`` после успешного ``update_ratios``."""
    if not update_result:
        return
    if not all(r.get("ok") for r in update_result.values()):
        return
    svc = DashboardService(redis, settings)
    try:
        partial = await svc.list_ratios_for_engine_types(only_engine_types)
    except Exception:
        logger.exception("cron: list_ratios_for_engine_types failed, skip DB merge")
        return
    session_factory = db_module.SessionLocal
    if session_factory is None:
        logger.warning("cron: SessionLocal not initialized, skip DB merge")
        return
    try:
        async with session_factory() as session:
            repo = DashboardStateRepository(session)
            await repo.merge_ratios_engines(partial)
            await session.commit()
    except Exception:
        logger.exception("cron: dashboard_state merge failed")


def _format_engine_status(result: dict[str, Any], *, max_err: int = 120) -> str:
    """Краткое описание статуса движков для одной строки лога."""
    parts: list[str] = []
    for label in sorted(result.keys()):
        row = result[label]
        if row.get("ok"):
            parts.append(f"{label}=ok")
        else:
            err = row.get("error") or "?"
            if isinstance(err, str) and len(err) > max_err:
                err = err[: max_err - 3] + "..."
            parts.append(f"{label}=fail:{err}")
    return " ".join(parts) if parts else "(no engines)"


async def _loop_forex_rapira(redis: Redis, settings: Settings) -> None:
    task = "forex_rapira"
    svc = DashboardService(redis, settings)
    while True:
        logger.info("cron task=%s: tick start (interval=%ss)", task, int(FOREX_RAPIRA_SEC))
        t0 = time.perf_counter()
        try:
            result = await svc.update_ratios(
                only_engine_types=(ForexEngine, RapiraEngine),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "cron task=%s: tick done in %.0fms | %s",
                task,
                elapsed_ms,
                _format_engine_status(result),
            )
            await _merge_ratios_after_tick(
                redis,
                settings,
                (ForexEngine, RapiraEngine),
                result,
            )
            for label, row in result.items():
                if not row.get("ok"):
                    logger.warning(
                        "cron task=%s: engine %s failed: %s",
                        task,
                        label,
                        row.get("error"),
                    )
        except Exception:
            logger.exception("cron task=%s: tick raised", task)
        logger.debug("cron task=%s: sleep %ss", task, FOREX_RAPIRA_SEC)
        await asyncio.sleep(FOREX_RAPIRA_SEC)


async def _loop_cbr(redis: Redis, settings: Settings) -> None:
    task = "cbr"
    svc = DashboardService(redis, settings)
    while True:
        logger.info("cron task=%s: tick start (interval=%ss)", task, int(CBR_SEC))
        t0 = time.perf_counter()
        try:
            result = await svc.update_ratios(only_engine_types=(CbrEngine,))
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "cron task=%s: tick done in %.0fms | %s",
                task,
                elapsed_ms,
                _format_engine_status(result),
            )
            await _merge_ratios_after_tick(
                redis,
                settings,
                (CbrEngine,),
                result,
            )
            for label, row in result.items():
                if not row.get("ok"):
                    logger.warning(
                        "cron task=%s: engine %s failed: %s",
                        task,
                        label,
                        row.get("error"),
                    )
        except Exception:
            logger.exception("cron task=%s: tick raised", task)
        logger.debug("cron task=%s: sleep %ss", task, CBR_SEC)
        await asyncio.sleep(CBR_SEC)


async def _loop_multisig_wallets(redis: Redis, settings: Settings) -> None:
    task = "multisig_wallets"
    while True:
        logger.info(
            "cron task=%s: tick start (interval=%ss)",
            task,
            int(MULTISIG_WALLET_SEC),
        )
        t0 = time.perf_counter()
        try:
            session_factory = db_module.SessionLocal
            if session_factory is None:
                logger.warning("cron task=%s: SessionLocal missing", task)
            else:
                async with session_factory() as session:
                    ms = MultisigWalletMaintenanceService(
                        session, redis, settings
                    )
                    n = await ms.process_batch()
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    logger.info(
                        "cron task=%s: processed %s wallet(s) in %.0fms",
                        task,
                        n,
                        elapsed_ms,
                    )
        except Exception:
            logger.exception("cron task=%s: tick raised", task)
        await asyncio.sleep(MULTISIG_WALLET_SEC)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings()
    db_module.init_db(settings.database)
    redis = Redis.from_url(settings.redis.url, decode_responses=True)
    logger.info(
        "cron: tasks started — forex_rapira every %ss, cbr every %ss, multisig every %ss",
        int(FOREX_RAPIRA_SEC),
        int(CBR_SEC),
        int(MULTISIG_WALLET_SEC),
    )
    try:
        await asyncio.gather(
            _loop_forex_rapira(redis, settings),
            _loop_cbr(redis, settings),
            _loop_multisig_wallets(redis, settings),
        )
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
