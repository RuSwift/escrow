"""
Движок котировок ЦБ РФ (публичный XML, без секретов).
"""

from datetime import datetime
from typing import List, Optional
import xml.etree.ElementTree as ET

from aiohttp import ClientSession

from core.ratio_entities import ExchangePair
from core.utils import datetime_to_float

from .base import BaseRatioEngine


class CbrEngine(BaseRatioEngine):
    """
    Курсы ЦБ РФ (XML).
    Источник: https://www.cbr.ru/scripts/XML_daily.asp
    """

    URL = "https://www.cbr.ru/scripts/XML_daily.asp"
    BASE = "RUB"
    REFRESH_TTL_SEC = 60 * 60  # 1 hour

    @classmethod
    def get_label(cls) -> str:
        return "ЦБ РФ"

    @property
    def is_enabled(self) -> bool:
        return True

    async def ratio(self, base: str, quote: str) -> Optional[ExchangePair]:
        stablecoins = ["USDT", "USDC"]
        if base in stablecoins:
            base = "USD"
        if quote in stablecoins:
            quote = "USD"
        return await super().ratio(base, quote)

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
        pairs: List[ExchangePair] = []
        dt = datetime.strptime(data["date"], "%d.%m.%Y")
        ts = datetime_to_float(dt)
        for item in data["rates"]:
            pairs.append(
                ExchangePair(
                    base=self.BASE,
                    quote=item["code"],
                    ratio=item["rate"],
                    utc=ts,
                )
            )
        return pairs

    @classmethod
    async def load_from_internet(cls) -> Optional[dict]:
        async with ClientSession() as cli:
            resp = await cli.get(cls.URL)
            if not resp.ok:
                return None
            xml = await resp.text()
            return cls._parse_xml(xml)

    @staticmethod
    def _parse_xml(xml: str) -> dict:
        root = ET.fromstring(xml)
        date_str = root.attrib.get("Date")
        rates = []
        for valute in root.findall("Valute"):
            code = valute.findtext("CharCode")
            nominal = int(valute.findtext("Nominal"))
            value = float(valute.findtext("Value").replace(",", "."))
            rate = value / nominal
            rates.append({"code": code.upper(), "rate": rate})
        return {"date": date_str, "rates": rates}
