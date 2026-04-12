"""
Pydantic-модели для ``forms.yaml`` (поля реквизитов по ``payment_code`` / BestChange).

Используются репозиторием приложения и скриптами сборки в ``scripts/``.
"""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PaymentFormFieldType(StrEnum):
    """Допустимые типы полей реквизитов в ``forms.yaml``."""

    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    MONEY = "money"
    PHONE = "phone"
    EMAIL = "email"
    BIC = "bic"
    IBAN = "iban"
    ACCOUNT_NUMBER = "account_number"
    PAN_LAST_DIGITS = "pan_last_digits"
    DATE = "date"


class PaymentFormsBcSourceMeta(BaseModel):
    """Привязка ``forms.yaml`` к снимку BestChange (``bc.yaml``)."""

    file: str = Field(default="bc.yaml", description="Имя файла-источника")
    exported_at: Optional[str] = Field(None, description="``meta.exported_at`` из bc.yaml")


class PaymentFormsMeta(BaseModel):
    """Корневой ``meta`` файла ``forms.yaml``."""

    schema_version: int = Field(1, description="Версия схемы")
    bc_source: Optional[PaymentFormsBcSourceMeta] = Field(
        None,
        description="Ссылка на выгрузку bc.yaml",
    )


class PaymentFormField(BaseModel):
    """Одно поле формы реквизитов."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Стабильный идентификатор поля (snake_case)")
    type: PaymentFormFieldType = Field(..., description="Тип для валидации и UI")
    required: bool = Field(..., description="Обязательность")
    label_key: Optional[str] = Field(
        None,
        description="Ключ в i18n/translations/*.json (каталог и совместимость)",
    )
    label: Optional[str] = Field(
        None,
        description="Подпись поля по умолчанию (без i18n-ключа)",
    )
    labels: Optional[Dict[str, str]] = Field(
        None,
        description="Подписи по коду локали (ru, en, …)",
    )
    default: Optional[str] = Field(
        None,
        description="Значение по умолчанию для UI (опционально)",
    )
    readonly: bool = Field(
        False,
        description="Поле только для чтения в форме ввода",
    )

    @model_validator(mode="after")
    def _at_least_one_caption(self) -> "PaymentFormField":
        lk = (self.label_key or "").strip()
        lb = (self.label or "").strip()
        labs = self.labels or {}
        has_locale = any((v or "").strip() for v in labs.values())
        if not lk and not lb and not has_locale:
            raise ValueError(
                "PaymentFormField requires non-empty label_key, label, or labels[locale]"
            )
        return self


class PaymentForm(BaseModel):
    """Набор полей для одного ``payment_code``."""

    fields: List[PaymentFormField] = Field(default_factory=list)


class PaymentFormsYaml(BaseModel):
    """Корневая модель ``forms.yaml`` рядом с ``bc.yaml``."""

    meta: PaymentFormsMeta
    forms: Dict[str, PaymentForm] = Field(
        default_factory=dict,
        description="Ключ — payment_code (как в bc.yaml)",
    )

    @classmethod
    def model_validate_yaml(cls, raw_yaml: str) -> "PaymentFormsYaml":
        data = yaml.safe_load(raw_yaml)
        return cls.model_validate(data)

    @classmethod
    def model_validate_file(cls, path: Path) -> "PaymentFormsYaml":
        text = path.read_text(encoding="utf-8")
        return cls.model_validate_yaml(text)


def load_payment_forms_yaml(path: Path) -> PaymentFormsYaml:
    """Загрузить и провалидировать ``forms.yaml``."""
    return PaymentFormsYaml.model_validate_file(path)


__all__ = [
    "PaymentForm",
    "PaymentFormField",
    "PaymentFormFieldType",
    "PaymentFormsBcSourceMeta",
    "PaymentFormsMeta",
    "PaymentFormsYaml",
    "load_payment_forms_yaml",
]
