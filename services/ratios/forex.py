"""
Движок котировок Forex (публичный API, без секретов).
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession

from core.ratio_entities import ExchangePair
from core.utils import datetime_to_float

from .base import BaseRatioEngine
from .cache import RatioCacheAdapter

FOREX_URL = (
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
)


class ForexEngine(BaseRatioEngine):
    """Курсы валют относительно USD (cdn.jsdelivr.net)."""

    REFRESH_TTL_SEC = 60 * 60  # 1 hour

    def __init__(
        self,
        cache: RatioCacheAdapter,
        settings: Any,
        refresh_cache: bool = False,
    ):
        super().__init__(cache=cache, settings=settings, refresh_cache=refresh_cache)

    @property
    def is_enabled(self) -> bool:
        return True

    async def market(self) -> List[ExchangePair]:
        if self.refresh_cache:
            data = None
        else:
            data = await self._cache.get("market")
        if not data:
            data = await self.load_from_internet()
            if data:
                await self._cache.set("market", data, self.REFRESH_TTL_SEC)
        if not data:
            return []
        pairs = []
        dt = datetime.strptime(data["date"], "%Y-%m-%d")
        for quote, ratio in data["usd"].items():
            p = ExchangePair(
                base="USD",
                quote=str(quote).upper(),
                ratio=1 / ratio,
                utc=datetime_to_float(dt),
            )
            pairs.append(p)
        return pairs

    @classmethod
    async def load_from_internet(cls) -> Optional[Dict]:
        async with ClientSession() as cli:
            resp = await cli.get(FOREX_URL, allow_redirects=True)
            if resp.ok:
                raw = await resp.text()
                return json.loads(raw)
            return None
