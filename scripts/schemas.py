"""
Pydantic-схема YAML, который выгружает ``export_bestchange_yaml.py`` (например ``bc.yaml``).

Использование::

    from pathlib import Path
    from scripts.schemas import load_bestchange_export_yaml

    data = load_bestchange_export_yaml(Path("bc.yaml"))
    for pm in data.payment_methods:
        print(pm.cur, pm.payment_name)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field

from core.bc import (
    PaymentForm,
    PaymentFormField,
    PaymentFormFieldType,
    PaymentFormsBcSourceMeta,
    PaymentFormsMeta,
    PaymentFormsYaml,
    load_payment_forms_yaml,
)


class BestchangeExportTranslationMeta(BaseModel):
    """Блок ``meta.translation`` при запуске с ``--en``."""

    sources: List[str] = Field(default_factory=list, description="Цепочка источников перевода")
    manual_file: Optional[str] = Field(None, description="Путь к ручному YAML или null")


class BestchangeExportMeta(BaseModel):
    """Корневой блок ``meta``."""

    source_url: str = Field(..., description="URL скачанного архива BestChange")
    zip_path: str = Field(..., description="Путь сохранения ZIP на диске")
    encoding: str = Field(..., description="Кодировка файлов внутри архива")
    exported_at: str = Field(..., description="Время выгрузки (ISO 8601)")
    translation: Optional[BestchangeExportTranslationMeta] = Field(
        None,
        description="Присутствует при экспорте с --en",
    )


class BestchangePaymentMethod(BaseModel):
    """Элемент ``payment_methods``."""

    payment_code: Optional[str] = Field(None, description="Код способа оплаты")
    cur: Optional[str] = Field(None, description="Код валюты (cur_code)")
    payment_name: str = Field(..., description="Название способа оплаты (из bm_cy)")
    payment_name_en: Optional[str] = Field(
        None,
        description="Английское название (при --en)",
    )


class BestchangeCity(BaseModel):
    """Элемент ``cities``."""

    id: int = Field(..., description="city_id из bm_rates / bm_cities")
    name: Optional[str] = Field(None, description="Название города")
    name_en: Optional[str] = Field(None, description="Английское название (при --en)")


class BestchangeExportYaml(BaseModel):
    """
    Корневая модель файла ``bc.yaml`` / вывода ``export_bestchange_yaml.py``.
    """

    meta: BestchangeExportMeta
    payment_methods: List[BestchangePaymentMethod] = Field(
        default_factory=list,
        description="Уникальные способы оплаты",
    )
    cities: List[BestchangeCity] = Field(
        default_factory=list,
        description="Города, встречающиеся в курсах",
    )

    @classmethod
    def model_validate_yaml(cls, raw_yaml: str) -> "BestchangeExportYaml":
        """Разбор YAML-строки."""
        data = yaml.safe_load(raw_yaml)
        return cls.model_validate(data)

    @classmethod
    def model_validate_file(cls, path: Path) -> "BestchangeExportYaml":
        """Разбор YAML-файла."""
        text = path.read_text(encoding="utf-8")
        return cls.model_validate_yaml(text)


def load_bestchange_export_yaml(path: Path) -> BestchangeExportYaml:
    """Загрузить и провалидировать ``bc.yaml``."""
    return BestchangeExportYaml.model_validate_file(path)


__all__ = [
    "BestchangeCity",
    "BestchangeExportMeta",
    "BestchangeExportTranslationMeta",
    "BestchangeExportYaml",
    "BestchangePaymentMethod",
    "PaymentForm",
    "PaymentFormField",
    "PaymentFormFieldType",
    "PaymentFormsBcSourceMeta",
    "PaymentFormsMeta",
    "PaymentFormsYaml",
    "load_bestchange_export_yaml",
    "load_payment_forms_yaml",
]
