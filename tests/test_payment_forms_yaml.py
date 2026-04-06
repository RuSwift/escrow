"""
Покрытие forms.yaml относительно bc.yaml и соответствие генератору.

Запуск без поднятого PostgreSQL::

    ESCROW_PYTEST_NO_DB=1 pytest tests/test_payment_forms_yaml.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.bc import load_payment_forms_yaml
from scripts.build_payment_forms_yaml import build_forms
from scripts.schemas import load_bestchange_export_yaml

pytestmark = pytest.mark.no_db

ROOT = Path(__file__).resolve().parent.parent


def test_forms_yaml_covers_bc_payment_codes() -> None:
    bc = load_bestchange_export_yaml(ROOT / "bc.yaml")
    forms = load_payment_forms_yaml(ROOT / "forms.yaml")
    bc_codes = {m.payment_code for m in bc.payment_methods if m.payment_code}
    assert bc_codes == set(forms.forms.keys())


def test_forms_yaml_matches_build_script() -> None:
    bc = load_bestchange_export_yaml(ROOT / "bc.yaml")
    built, _, _, _ = build_forms(bc, None)
    disk = load_payment_forms_yaml(ROOT / "forms.yaml")
    assert built.model_dump(mode="json") == disk.model_dump(mode="json")


def test_field_label_keys_exist_in_i18n() -> None:
    forms = load_payment_forms_yaml(ROOT / "forms.yaml")
    ru = ROOT.joinpath("i18n/translations/ru.json")
    en = ROOT.joinpath("i18n/translations/en.json")
    ru_map = json.loads(ru.read_text(encoding="utf-8"))
    en_map = json.loads(en.read_text(encoding="utf-8"))
    keys = {f.label_key for fm in forms.forms.values() for f in fm.fields}
    for k in keys:
        assert k in ru_map, f"missing ru: {k}"
        assert k in en_map, f"missing en: {k}"
