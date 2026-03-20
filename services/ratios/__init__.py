"""
Движки котировок: forex, cbr, rapira, bestchange.
Кэш и настройки передаются явно; секреты только через settings (Rapira).
"""

from typing import List, Optional

from redis.asyncio import Redis

from .base import BaseP2PRatioEngine, BaseRatioEngine, CacheableMixin
from .bestchange import BestChangeRatios
from .cache import RatioCacheAdapter
from .cbr import CbrEngine
from .forex import ForexEngine
from .rapira import RapiraAuth, RapiraEngine


__all__ = [
    "BaseRatioEngine",
    "BaseP2PRatioEngine",
    "CacheableMixin",
    "RatioCacheAdapter",
    "ForexEngine",
    "CbrEngine",
    "RapiraEngine",
    "RapiraAuth",
    "BestChangeRatios",
    "get_ratios_engines",
]


def get_ratios_engines(
    redis: Redis,
    ratios_settings: Optional[object] = None,
    *,
    refresh_cache: bool = False,
) -> List[object]:
    """
    Собирает экземпляры движков котировок (forex, cbr, rapira, bestchange).
    Настройки берутся из ratios_settings (например settings.ratios).
    Возвращает список движков; активность каждого — по атрибуту is_enabled.
    """
    if ratios_settings is None:
        return []
    engines: List[object] = []
    forex_cfg = getattr(ratios_settings, "forex", None)
    if forex_cfg is not None:
        cache = RatioCacheAdapter(redis, "ForexEngine")
        engines.append(ForexEngine(cache, forex_cfg, refresh_cache=refresh_cache))
    cbr_cfg = getattr(ratios_settings, "cbr", None)
    if cbr_cfg is not None:
        cache = RatioCacheAdapter(redis, "CbrEngine")
        engines.append(CbrEngine(cache, cbr_cfg, refresh_cache=refresh_cache))
    rapira_cfg = getattr(ratios_settings, "rapira", None)
    if rapira_cfg is not None:
        cache = RatioCacheAdapter(redis, "RapiraEngine")
        engines.append(RapiraEngine(cache, rapira_cfg, refresh_cache=refresh_cache))
    bestchange_cfg = getattr(ratios_settings, "bestchange", None)
    if bestchange_cfg is not None:
        cache = RatioCacheAdapter(redis, "BestChangeRatios")
        engines.append(
            BestChangeRatios(
                cache, bestchange_cfg, refresh_cache=refresh_cache
            )
        )
    return engines
