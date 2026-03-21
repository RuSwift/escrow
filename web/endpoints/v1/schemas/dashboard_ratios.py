"""Схемы ответов API котировок дашборда (спотовые движки)."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, RootModel

from core.ratio_entities import ExchangePair


class RatioListRow(BaseModel):
    """Одна строка: пара валют и котировка или null."""

    base: str = Field(..., description="Базовая валюта")
    quote: str = Field(..., description="Котируемая валюта")
    pair: Optional[ExchangePair] = Field(
        None,
        description="Курс (ExchangePair) или null, если недоступен",
    )


class ListRatiosResponse(RootModel[Dict[str, List[RatioListRow]]]):
    """
    Ключ — метка движка (``get_label()``), значение — строки по парам из
    ``Settings.system_currencies``.
    """
