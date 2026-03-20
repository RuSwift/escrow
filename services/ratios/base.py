"""
Базовые классы движков котировок: без Django, кэш и настройки передаются явно.
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional, TypeVar

from pydantic import BaseModel

from core.ratio_entities import ExchangePair, P2POrders
from core.utils import utc_now_float

from .cache import RatioCacheAdapter

SettingsT = TypeVar("SettingsT", bound=BaseModel)


class CacheableMixin:
    """Миксин для сериализации в кэш (Rates, Currencies и т.д. в BestChange)."""

    @abstractmethod
    def serialize(self) -> Dict:
        ...

    @abstractmethod
    def deserialize(self, dump: Dict) -> None:
        ...


class BaseRatioEngine:
    """
    Базовый движок курсов валют. Кэш и настройки передаются в конструктор.
    """

    CACHE_TTL = 60 * 5  # 5 min

    def __init__(
        self,
        cache: RatioCacheAdapter,
        settings: Any,
        refresh_cache: bool = False,
    ):
        self._cache = cache
        self.settings = settings
        self.refresh_cache = refresh_cache

    @property
    def is_enabled(self) -> bool:
        """По умолчанию движок активен; в наследниках переопределять по наличию конфига/секретов."""
        return True

    @classmethod
    def get_label(cls) -> str:
        return cls.__name__.replace("Engine", "")

    @abstractmethod
    async def market(self) -> List[ExchangePair]:
        ...

    async def ratio(self, base: str, quote: str) -> Optional[ExchangePair]:
        cached: Optional[dict] = None
        if not self.refresh_cache:
            cached = await self._cache.get(f"{quote}/{base}")
        if cached:
            return ExchangePair.model_validate(cached)
        if base == quote:
            return ExchangePair(
                utc=utc_now_float(),
                base=base,
                quote=quote,
                ratio=1.0,
            )
        pairs = await self.market()
        fwd1: Optional[ExchangePair] = None
        fwd2: Optional[ExchangePair] = None
        revert: Optional[ExchangePair] = None
        for pair in pairs:
            if pair.base == base and pair.quote == quote:
                return pair
            if pair.quote == base and pair.base == quote:
                revert = pair
                break
        if not revert:
            cross = {}
            for pair in pairs:
                if pair.quote == base:
                    cross[pair.base] = pair
            for pair in pairs:
                if pair.quote == quote and pair.base in cross:
                    fwd1, fwd2 = pair, cross[pair.base]
                    break
        if (fwd1 and fwd2) or revert:
            if revert:
                p = ExchangePair(
                    utc=revert.utc,
                    base=base,
                    quote=quote,
                    ratio=1 / revert.ratio,
                )
            else:
                p = ExchangePair(
                    utc=fwd1.utc,
                    base=base,
                    quote=quote,
                    ratio=fwd1.ratio / fwd2.ratio,
                )
            expire_ttl = p.utc + self.CACHE_TTL
            ttl = round(expire_ttl - utc_now_float())
            await self._cache.set(
                f"{quote}/{base}",
                p.model_dump(mode="json"),
                ttl=max(ttl, 60),
            )
            return p
        return None


class BaseP2PRatioEngine:
    """
    Базовый движок P2P-ордеров (BestChange и др.). Кэш и настройки в конструкторе.
    """

    def __init__(
        self,
        cache: RatioCacheAdapter,
        settings: Any,
        refresh_cache: bool = False,
    ):
        self._cache = cache
        self.settings = settings
        self.refresh_cache = refresh_cache

    @property
    def is_enabled(self) -> bool:
        """В наследниках переопределять по наличию конфига (url, zip_path и т.д.)."""
        return True

    @abstractmethod
    async def load_orders(
        self,
        token: str,
        fiat: str,
        page: int = 0,
        pg_size: Optional[int] = None,
        give: Optional[str] = None,
        get: Optional[str] = None,
    ) -> Optional[P2POrders]:
        ...
