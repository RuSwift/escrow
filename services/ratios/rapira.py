"""
Движок котировок Rapira (JWT: private_key, uid из settings).
"""

import base64
import datetime
import random
import time
from typing import Any, List, Optional

import jwt
from aiohttp import ClientSession
from pydantic import BaseModel

from core.ratio_entities import ExchangePair
from core.utils import utc_now_float

from .base import BaseRatioEngine
from .cache import RatioCacheAdapter


class RapiraAuth:
    """
    Выделение JWT для API Rapira.
    Документация: https://rapira.readme.io/reference/jwt
    """

    def __init__(
        self,
        uid: str,
        private_key: str,
        base_url: str = "https://api.rapira.net",
        ttl: int = 60 * 60,
        cache: Optional[RatioCacheAdapter] = None,
    ):
        self._private_key = private_key
        self._uid = uid
        self._base_url = base_url.rstrip("/")
        self._ttl = ttl
        self._cache = cache

    async def allocate_token(self) -> str:
        key_b = base64.b64decode(self._private_key)
        cache_key = "rapira:jwt"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached and cached.get("jwt"):
                return cached["jwt"]
        iat = int(time.mktime(datetime.datetime.now().timetuple()))
        claims = {
            "exp": iat + self._ttl,
            "jti": hex(random.getrandbits(12)).upper(),
        }
        jwt_token = jwt.encode(claims, key_b, algorithm="RS256")
        if hasattr(jwt_token, "decode"):
            jwt_token = jwt_token.decode("utf-8")
        async with ClientSession(base_url=self._base_url) as cli:
            resp = await cli.post(
                "/open/generate_jwt",
                allow_redirects=True,
                json={"kid": self._uid, "jwt_token": jwt_token},
            )
            data = await resp.json()
            if resp.status != 200:
                raise RuntimeError(
                    f"Rapira generate_jwt HTTP {resp.status}: {data!r}"
                )
            token = data.get("token")
            if not token:
                raise RuntimeError(
                    f"Rapira generate_jwt: нет token в ответе: {data!r}"
                )
            if self._cache:
                await self._cache.set(cache_key, {"jwt": token}, ttl=self._ttl)
            return token


class RapiraMarketData(BaseModel):
    """Один элемент ответа /open/market/rates."""

    symbol: str
    open: float
    high: float
    low: float
    close: float
    chg: float
    change: float
    fee: float
    lastDayClose: float
    usdRate: float
    baseUsdRate: float
    askPrice: float
    bidPrice: float
    baseCoinScale: int
    coinScale: int
    quoteCurrencyName: str
    baseCurrency: str
    quoteCurrency: str


class RapiraEngine(BaseRatioEngine):
    """Курсы с Rapira API (JWT из settings: private_key, uid)."""

    CACHE_TTL = 30  # 30 sec

    def __init__(
        self,
        cache: RatioCacheAdapter,
        settings: Any,
        refresh_cache: bool = False,
    ):
        super().__init__(cache=cache, settings=settings, refresh_cache=refresh_cache)
        if not getattr(settings, "host", "").startswith("http"):
            self._base_url = f"https://{settings.host}"
        else:
            self._base_url = settings.host
        pk = getattr(settings, "private_key", None)
        uid = getattr(settings, "uid", None)
        pk_str = pk.get_secret_value() if pk and hasattr(pk, "get_secret_value") else (pk or "")
        self._auth = RapiraAuth(
            uid=uid or "",
            private_key=pk_str,
            base_url=self._base_url,
            ttl=getattr(settings, "ttl", 60),
            cache=cache,
        )

    @property
    def is_enabled(self) -> bool:
        pk = getattr(self.settings, "private_key", None)
        uid = getattr(self.settings, "uid", None)
        if pk and hasattr(pk, "get_secret_value"):
            pk = pk.get_secret_value() if pk else None
        return bool(pk and uid)

    async def market(self) -> List[ExchangePair]:
        if not self.refresh_cache:
            cached = await self._cache.get("market")
            if cached:
                return [ExchangePair.model_validate(d) for d in cached]
        markets = await self.load_markets()
        if not markets:
            return []
        pairs: List[ExchangePair] = []
        for market in markets:
            p = ExchangePair(
                base=market.baseCurrency,
                quote=market.quoteCurrency,
                ratio=(market.askPrice + market.bidPrice) / 2,
                utc=utc_now_float(),
            )
            pairs.append(p)
        ttl = getattr(self.settings, "ttl", self.CACHE_TTL)
        await self._cache.set(
            "market",
            [p.model_dump(mode="json") for p in pairs],
            ttl=ttl,
        )
        return pairs

    async def load_markets(self) -> Optional[List[RapiraMarketData]]:
        token = await self._auth.allocate_token()
        async with ClientSession(base_url=self._base_url) as cli:
            resp = await cli.get(
                "/open/market/rates",
                headers={
                    "accept": "application/json",
                    "Authorization": "Bearer " + token,
                },
            )
            if resp.status == 200:
                data = await resp.json()
                return [RapiraMarketData.model_validate(i) for i in data["data"]]
            return None
