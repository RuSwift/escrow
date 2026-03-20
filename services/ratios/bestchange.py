"""
Движок P2P-котировок BestChange (ZIP по URL, парсинг bm_*.dat).
"""

import aiohttp
import os
from io import TextIOWrapper
from typing import Any, List, Optional, Tuple, Union
from zipfile import ZipFile

from core.ratio_entities import P2POrder, P2POrders
from core.utils import utc_now_float

from .base import BaseP2PRatioEngine, CacheableMixin
from .cache import RatioCacheAdapter


class Rates(CacheableMixin):
    def __init__(self, text: str, split_reviews: bool):
        self.__data: List[dict] = []
        for row in text.splitlines():
            val = row.split(";")
            try:
                self.__data.append({
                    "give_id": int(val[0]),
                    "get_id": int(val[1]),
                    "exchange_id": int(val[2]),
                    "rate": float(val[3]) / float(val[4]),
                    "reserve": float(val[5]),
                    "reviews": val[6].split(".") if split_reviews else val[6],
                    "min_sum": float(val[8]),
                    "max_sum": float(val[9]),
                    "city_id": int(val[10]),
                    "utc": None,
                })
            except (ZeroDivisionError, (IndexError, ValueError)):
                pass

    def get(self):
        return self.__data

    def filter(
        self,
        give_id: Union[int, List[int]],
        get_id: Union[int, List[int]],
    ):
        data = []
        give_id = [give_id] if isinstance(give_id, int) else give_id
        get_id = [get_id] if isinstance(get_id, int) else get_id
        for val in self.__data:
            if val["give_id"] in give_id and val["get_id"] in get_id:
                val["give"] = 1 if val["rate"] < 1 else val["rate"]
                val["get"] = 1 / val["rate"] if val["rate"] < 1 else 1
                data.append(val)
        return sorted(data, key=lambda x: x["rate"])

    def serialize(self) -> dict:
        return {"data": self.__data}

    def deserialize(self, dump: dict) -> None:
        self.__data = dump.get("data", [])

    def set_utc(self, value: float) -> None:
        for item in self.__data:
            item["utc"] = value


class Common(CacheableMixin):
    def __init__(self) -> None:
        self.data: dict = {}

    def get(self):
        return self.data

    @property
    def is_empty(self) -> bool:
        return len(self.data) > 0

    def get_by_id(self, id_: int, only_name: bool = True):
        if id_ not in self.data:
            return None
        return self.data[id_]["name"] if only_name else self.data[id_]

    def search_by_name(self, name: str):
        return {
            k: val
            for k, val in self.data.items()
            if name.lower() in val["name"].lower()
        }

    def serialize(self) -> dict:
        return self.data

    def deserialize(self, dump: dict) -> None:
        self.data.clear()
        for k, v in dump.items():
            if isinstance(k, str) and k.isdigit():
                k = int(k)
            self.data[k] = v


class CurCodes(Common):
    def __init__(self, text: str) -> None:
        super().__init__()
        for row in text.splitlines():
            val = row.split(";")
            self.data[int(val[0])] = {
                "id": int(val[0]),
                "code": val[1],
                "name": val[2],
            }

    def get_code(self, id_: int) -> Optional[str]:
        d = self.data.get(id_)
        return d["code"] if d else None


class PaymentCodes(Common):
    def __init__(self, text: str) -> None:
        super().__init__()
        for row in text.splitlines():
            val = row.split(";")
            self.data[int(val[0])] = {"id": int(val[0]), "code": val[1]}

    def get_code(self, id_: int) -> Optional[str]:
        d = self.data.get(id_)
        return d["code"] if d else None


class Currencies(Common):
    def __init__(self, text: str) -> None:
        super().__init__()
        for row in text.splitlines():
            val = row.split(";")
            self.data[int(val[0])] = {
                "id": int(val[0]),
                "pos_id": int(val[1]),
                "name": val[2],
                "payment_code": None,
                "cur_id": int(val[4]),
                "cur_code": None,
            }
        self.data = dict(sorted(self.data.items(), key=lambda x: x[1]["name"]))

    def apply_payment_codes(self, codes: PaymentCodes) -> None:
        for id_, d in self.data.items():
            d["payment_code"] = codes.get_code(id_)

    def apply_fiat_codes(self, codes: CurCodes) -> None:
        for id_, d in self.data.items():
            d["cur_code"] = codes.get_code(d["cur_id"])

    def filter(self, **attrs) -> List[dict]:
        result = []
        for d in self.data.values():
            if all(d.get(a) == v for a, v in attrs.items()):
                result.append(d)
        return result

    def filter_by_name(self, part: str) -> List[dict]:
        return [
            d for d in self.data.values()
            if part.lower() in d["name"].lower()
        ]


class Exchangers(Common):
    def __init__(self, text: str) -> None:
        super().__init__()
        for row in text.splitlines():
            val = row.split(";")
            self.data[int(val[0])] = {
                "id": int(val[0]),
                "name": val[1],
                "wmbl": int(val[3]),
                "reserve_sum": float(val[4]),
            }
        self.data = dict(sorted(self.data.items()))


class Cities(Common):
    def __init__(self, text: str) -> None:
        super().__init__()
        for row in text.splitlines():
            val = row.split(";")
            self.data[int(val[0])] = {"id": int(val[0]), "name": val[1]}
        self.data = dict(sorted(self.data.items(), key=lambda x: x[1]["name"]))


class BestChangeRatios(BaseP2PRatioEngine):
    """P2P-ордера BestChange: загрузка ZIP, парсинг bm_*.dat."""

    REFRESH_TTL_SEC = 5 * 60  # 5 min
    CACHE_VALUES_KEY = "values"

    def __init__(
        self,
        cache: RatioCacheAdapter,
        settings: Any,
        refresh_cache: bool = False,
        forced_zip_file: Optional[str] = None,
    ):
        super().__init__(cache=cache, settings=settings, refresh_cache=refresh_cache)
        self._forced_zip_file = forced_zip_file

    @property
    def is_enabled(self) -> bool:
        url = getattr(self.settings, "url", None)
        zip_path = getattr(self.settings, "zip_path", None)
        return bool(url and zip_path)

    async def load_from_server(
        self,
    ) -> Tuple[Rates, Currencies, Exchangers, Cities]:
        if self._forced_zip_file:
            zip_path = self._forced_zip_file
        else:
            zip_path = getattr(self.settings, "zip_path", "/tmp/bestchange.zip")
            if os.path.isfile(zip_path):
                os.remove(zip_path)
            url = getattr(self.settings, "url", "")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.read()
                    with open(zip_path, "wb") as f:
                        f.write(data)
        return await self.load_from_zip(zip_path)

    async def load_from_zip(
        self, path: str
    ) -> Tuple[Rates, Currencies, Exchangers, Cities]:
        if not os.path.isfile(path):
            raise RuntimeError(f'File "{path}" does not exist')
        enc = getattr(self.settings, "enc", "windows-1251")
        split_reviews = getattr(self.settings, "split_reviews", False)
        file_rates = getattr(self.settings, "file_rates", "bm_rates.dat")
        file_currencies = getattr(self.settings, "file_currencies", "bm_cy.dat")
        file_exchangers = getattr(self.settings, "file_exchangers", "bm_exch.dat")
        file_cities = getattr(self.settings, "file_cities", "bm_cities.dat")
        file_top = getattr(self.settings, "file_top", "bm_top.dat")
        file_cur_codes = getattr(self.settings, "file_cur_codes", "bm_bcodes.dat")
        file_payment_codes = getattr(
            self.settings, "file_payment_codes", "bm_cycodes.dat"
        )
        with ZipFile(path) as zf:
            files = zf.namelist()
            for name, attr in [
                (file_rates, "file_rates"),
                (file_currencies, "file_currencies"),
                (file_exchangers, "file_exchangers"),
                (file_cities, "file_cities"),
                (file_top, "file_top"),
                (file_cur_codes, "file_cur_codes"),
                (file_payment_codes, "file_payment_codes"),
            ]:
                if name not in files:
                    raise RuntimeError(f'File "{name}" not found in archive')
            with zf.open(file_rates) as f:
                with TextIOWrapper(f, encoding=enc) as r:
                    rates = Rates(r.read(), split_reviews)
            with zf.open(file_payment_codes) as f:
                with TextIOWrapper(f, encoding=enc) as r:
                    payment_codes = PaymentCodes(r.read())
            with zf.open(file_cur_codes) as f:
                with TextIOWrapper(f, encoding=enc) as r:
                    fiat_codes = CurCodes(r.read())
            with zf.open(file_currencies) as f:
                with TextIOWrapper(f, encoding=enc) as r:
                    currencies = Currencies(r.read())
                    currencies.apply_payment_codes(payment_codes)
                    currencies.apply_fiat_codes(fiat_codes)
            with zf.open(file_exchangers) as f:
                with TextIOWrapper(f, encoding=enc) as r:
                    exchangers = Exchangers(r.read())
            with zf.open(file_cities) as f:
                with TextIOWrapper(f, encoding=enc) as r:
                    cities = Cities(r.read())
        return rates, currencies, exchangers, cities

    async def save_to_cache(
        self,
        rates: Rates,
        currencies: Currencies,
        exchangers: Exchangers,
        cities: Cities,
        ttl: Optional[int] = None,
    ) -> float:
        utc_ = utc_now_float()
        await self._cache.set(
            self.CACHE_VALUES_KEY,
            {
                "rates": rates.serialize(),
                "currencies": currencies.serialize(),
                "exchangers": exchangers.serialize(),
                "cities": cities.serialize(),
                "utc": utc_,
            },
            ttl or self.REFRESH_TTL_SEC,
        )
        return utc_

    async def load_metadata(
        self,
    ) -> Tuple[Rates, Currencies, Exchangers, Cities]:
        cached = await self._cache.get(self.CACHE_VALUES_KEY)
        if not cached:
            rates, currencies, exchangers, cities = await self.load_from_server()
            utc_stamp = await self.save_to_cache(
                rates, currencies, exchangers, cities
            )
            rates.set_utc(utc_stamp)
            return rates, currencies, exchangers, cities
        utc_stamp = cached["utc"]
        rates = Rates("", False)
        rates.set_utc(utc_stamp)
        currencies = Currencies("")
        exchangers = Exchangers("")
        cities = Cities("")
        rates.deserialize(cached["rates"])
        currencies.deserialize(cached["currencies"])
        exchangers.deserialize(cached["exchangers"])
        cities.deserialize(cached["cities"])
        rates.set_utc(utc_stamp)
        return rates, currencies, exchangers, cities

    async def load_orders(
        self,
        token: str = "",
        fiat: str = "",
        page: int = 0,
        pg_size: Optional[int] = None,
        give: Optional[str] = None,
        get: Optional[str] = None,
    ) -> Optional[P2POrders]:
        if give and fiat:
            raise RuntimeError("Unexpected args configuration")
        if get and token:
            raise RuntimeError("Unexpected args configuration")
        if fiat:
            give = fiat
        if token:
            get = token
        if not give or not get:
            return None
        cache_orders_key = f"get:{get};give:{give}"
        if self.refresh_cache:
            raw = None
        else:
            raw = await self._cache.get(cache_orders_key)
        orders: Optional[P2POrders] = None
        if raw:
            try:
                orders = P2POrders.model_validate(raw)
            except (ValueError, TypeError):
                pass
        if not orders:
            rates, currencies, exchangers, cities = await self.load_metadata()
            asks_gives = currencies.filter(cur_code=give)
            if not asks_gives:
                asks_gives = currencies.filter_by_name(give)
            asks_gets = currencies.filter_by_name(get)
            asks_give_ids = [d["id"] for d in asks_gives]
            asks_get_ids = [d["id"] for d in asks_gets]
            asks = self._build_orders(
                give_ids=asks_give_ids,
                get_ids=asks_get_ids,
                src=give,
                dest=get,
                rates=rates,
                currencies=currencies,
                ex=exchangers,
            )
            bids_gives = currencies.filter_by_name(get)
            bids_gets = currencies.filter(cur_code=give)
            if not bids_gets:
                bids_gets = currencies.filter_by_name(give)
            bids_give_ids = [d["id"] for d in bids_gives]
            bids_get_ids = [d["id"] for d in bids_gets]
            bids = self._build_orders(
                give_ids=bids_give_ids,
                get_ids=bids_get_ids,
                src=get,
                dest=give,
                rates=rates,
                currencies=currencies,
                ex=exchangers,
            )
            orders = P2POrders(asks=asks, bids=bids)
            await self._cache.set(
                cache_orders_key,
                orders.model_dump(mode="json"),
                self.REFRESH_TTL_SEC,
            )
        return orders

    @classmethod
    def _build_orders(
        cls,
        give_ids: List[int],
        get_ids: List[int],
        src: str,
        dest: str,
        rates: Rates,
        currencies: Currencies,
        ex: Exchangers,
    ) -> List[P2POrder]:
        orders_ids: set = set()
        filtered = rates.filter(give_id=give_ids, get_id=get_ids)
        orders: List[P2POrder] = []
        for r in filtered:
            ex_name = ex.get_by_id(r["exchange_id"], only_name=True)
            give_cur = currencies.get_by_id(r["give_id"], only_name=False)
            get_cur = currencies.get_by_id(r["get_id"], only_name=False)
            if give_cur and get_cur and ex_name:
                order_id = (
                    f"{ex_name}:{src}-{dest}:"
                    + give_cur["payment_code"]
                    + "-"
                    + get_cur["payment_code"]
                )
                if order_id not in orders_ids:
                    orders_ids.add(order_id)
                    order = P2POrder(
                        id=order_id,
                        trader_nick=ex_name,
                        price=r["rate"],
                        min_amount=r["min_sum"],
                        max_amount=r["max_sum"],
                        pay_methods=[give_cur["name"], get_cur["name"]],
                        bestchange_codes=[
                            give_cur["payment_code"],
                            get_cur["payment_code"],
                        ],
                        utc=r.get("utc"),
                    )
                    orders.append(order)
        return orders
