#!/usr/bin/env python3
"""
Сборка ``forms.yaml`` из ``bc.yaml``: эвристические шаблоны полей по ``payment_code``,
опциональные переопределения из YAML, проверка покрытия.

Примеры::

    poetry run python scripts/build_payment_forms_yaml.py -o forms.yaml
    poetry run python scripts/build_payment_forms_yaml.py --check
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.bc import (  # noqa: E402
    PaymentForm,
    PaymentFormField,
    PaymentFormFieldType,
    PaymentFormsBcSourceMeta,
    PaymentFormsMeta,
    PaymentFormsYaml,
    load_payment_forms_yaml,
)
from scripts.schemas import (  # noqa: E402
    BestchangeExportYaml,
    BestchangePaymentMethod,
    load_bestchange_export_yaml,
)


def _field(
    fid: str,
    ftype: PaymentFormFieldType,
    *,
    required: bool = True,
    label_key: Optional[str] = None,
) -> PaymentFormField:
    return PaymentFormField(
        id=fid,
        type=ftype,
        required=required,
        label_key=label_key or f"forms.requisite.{fid}",
    )


def _crypto() -> List[PaymentFormField]:
    return [
        _field("wallet_address", PaymentFormFieldType.STRING),
        _field("memo_tag", PaymentFormFieldType.STRING, required=False),
    ]


def _card() -> List[PaymentFormField]:
    return [
        _field("pan_last_digits", PaymentFormFieldType.PAN_LAST_DIGITS),
        _field("holder_name", PaymentFormFieldType.STRING),
        _field("bank_name", PaymentFormFieldType.STRING, required=False),
    ]


def _cash() -> List[PaymentFormField]:
    return [
        _field("city", PaymentFormFieldType.STRING),
        _field("contact_phone", PaymentFormFieldType.PHONE),
        _field("meeting_notes", PaymentFormFieldType.TEXT, required=False),
    ]


def _sepa() -> List[PaymentFormField]:
    return [
        _field("holder_name", PaymentFormFieldType.STRING),
        _field("iban", PaymentFormFieldType.IBAN),
        _field("bic", PaymentFormFieldType.BIC, required=False),
    ]


def _corp_rub_family(cur: str) -> List[PaymentFormField]:
    if cur in ("RUB", "BYN"):
        return [
            _field("company_name", PaymentFormFieldType.STRING),
            _field("inn", PaymentFormFieldType.STRING),
            _field("kpp", PaymentFormFieldType.STRING, required=False),
            _field("settlement_account", PaymentFormFieldType.ACCOUNT_NUMBER),
            _field("bik", PaymentFormFieldType.BIC),
            _field("bank_name", PaymentFormFieldType.STRING, required=False),
        ]
    return [
        _field("company_name", PaymentFormFieldType.STRING),
        _field("tax_id", PaymentFormFieldType.STRING, required=False),
        _field("account_number", PaymentFormFieldType.ACCOUNT_NUMBER),
        _field("swift_bic", PaymentFormFieldType.BIC),
        _field("bank_name", PaymentFormFieldType.STRING),
        _field("bank_address", PaymentFormFieldType.TEXT, required=False),
    ]


def _wire_rub_family() -> List[PaymentFormField]:
    return [
        _field("holder_name", PaymentFormFieldType.STRING),
        _field("settlement_account", PaymentFormFieldType.ACCOUNT_NUMBER),
        _field("bik", PaymentFormFieldType.BIC),
        _field("bank_name", PaymentFormFieldType.STRING, required=False),
        _field("payment_reference", PaymentFormFieldType.STRING, required=False),
    ]


def _wire_iban_family() -> List[PaymentFormField]:
    return [
        _field("holder_name", PaymentFormFieldType.STRING),
        _field("iban", PaymentFormFieldType.IBAN),
        _field("bic", PaymentFormFieldType.BIC, required=False),
        _field("payment_reference", PaymentFormFieldType.STRING, required=False),
    ]


def _wire_international() -> List[PaymentFormField]:
    return [
        _field("holder_name", PaymentFormFieldType.STRING),
        _field("account_number", PaymentFormFieldType.ACCOUNT_NUMBER),
        _field("swift_bic", PaymentFormFieldType.BIC),
        _field("bank_name", PaymentFormFieldType.STRING),
        _field("bank_address", PaymentFormFieldType.TEXT, required=False),
        _field("payment_reference", PaymentFormFieldType.STRING, required=False),
    ]


def _wire(cur: str) -> List[PaymentFormField]:
    if cur in ("RUB", "BYN"):
        return _wire_rub_family()
    if cur in (
        "EUR",
        "CHF",
        "SEK",
        "NOK",
        "DKK",
        "PLN",
        "CZK",
        "HUF",
        "RON",
        "BGN",
    ):
        return _wire_iban_family()
    return _wire_international()


def _alipay() -> List[PaymentFormField]:
    return [
        _field("alipay_id", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING),
    ]


def _wechat() -> List[PaymentFormField]:
    return [
        _field("wechat_id", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING),
    ]


def _blik() -> List[PaymentFormField]:
    return [
        _field("blik_alias", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING, required=False),
    ]


def _bkash() -> List[PaymentFormField]:
    return [
        _field("mobile_money_phone", PaymentFormFieldType.PHONE),
        _field("holder_name", PaymentFormFieldType.STRING),
    ]


def _bpay() -> List[PaymentFormField]:
    return [
        _field("bill_pay_account", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING, required=False),
    ]


def _adv_wallet() -> List[PaymentFormField]:
    return [
        _field("wallet_id", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING, required=False),
    ]


def _paypal() -> List[PaymentFormField]:
    return [
        _field("paypal_email", PaymentFormFieldType.EMAIL),
        _field("holder_name", PaymentFormFieldType.STRING, required=False),
    ]


def _wise() -> List[PaymentFormField]:
    return [
        _field("wise_identifier", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING, required=False),
    ]


def _mir_card() -> List[PaymentFormField]:
    return [
        _field("pan_last_digits", PaymentFormFieldType.PAN_LAST_DIGITS),
        _field("holder_name", PaymentFormFieldType.STRING),
    ]


def _sbp_rub() -> List[PaymentFormField]:
    return [
        _field("sbp_phone", PaymentFormFieldType.PHONE),
        _field("holder_name", PaymentFormFieldType.STRING),
    ]


def _qr_payment() -> List[PaymentFormField]:
    return [
        _field("qr_payload", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING, required=False),
    ]


def _nfc_phone() -> List[PaymentFormField]:
    return [
        _field("device_phone", PaymentFormFieldType.PHONE),
        _field("holder_name", PaymentFormFieldType.STRING),
    ]


def _phone_balance() -> List[PaymentFormField]:
    return [
        _field("phone_account", PaymentFormFieldType.PHONE),
        _field("holder_name", PaymentFormFieldType.STRING),
    ]


def _mercado() -> List[PaymentFormField]:
    return [
        _field("ewallet_account", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING),
    ]


def _idram_style() -> List[PaymentFormField]:
    return [
        _field("ewallet_account", PaymentFormFieldType.STRING),
        _field("holder_name", PaymentFormFieldType.STRING, required=False),
    ]


def _domestic_fiat_bank() -> List[PaymentFormField]:
    return [
        _field("holder_name", PaymentFormFieldType.STRING),
        _field("recipient_account", PaymentFormFieldType.ACCOUNT_NUMBER),
        _field("routing_code", PaymentFormFieldType.STRING, required=False),
        _field("bank_name", PaymentFormFieldType.STRING, required=False),
    ]


def _generic() -> List[PaymentFormField]:
    return [
        _field("holder_name", PaymentFormFieldType.STRING),
        _field("requisite_details", PaymentFormFieldType.TEXT),
    ]


def _crypto_currencies(methods: List[BestchangePaymentMethod]) -> Set[str]:
    """
    Базовая валюта крипто-направления: совпадение code==cur (BTC, ADA, …)
    плюс варианты вида BTCBEP20 / USDTTRC20 при префиксе кода равном тикеру.
    """
    out: Set[str] = set()
    for m in methods:
        pc = (m.payment_code or "").upper()
        c = (m.cur or "").upper()
        if not pc or not c:
            continue
        if pc == c:
            out.add(c)
        elif (
            c.isalpha()
            and 2 <= len(c) <= 6
            and pc.startswith(c)
            and pc != c
        ):
            out.add(c)
    return out


FIAT_DOMESTIC_MARKERS = frozenset(
    {
        "RUB",
        "BYN",
        "UAH",
        "KZT",
        "TRY",
    }
)


def classify_fields(
    pm: BestchangePaymentMethod,
    crypto_curs: Set[str],
) -> List[PaymentFormField]:
    pc = pm.payment_code or ""
    cur = (pm.cur or "").upper()

    if pc.startswith("SEPA"):
        return _sepa()
    if pc.startswith("CORP"):
        return _corp_rub_family(cur)
    if pc.startswith("CARD"):
        return _card()
    if pc.startswith("CASH"):
        return _cash()
    if pc.startswith("WIRE"):
        return _wire(cur)
    if pc.startswith("ALP"):
        return _alipay()
    if pc.startswith("WCT"):
        return _wechat()
    if pc.startswith("BLIK"):
        return _blik()
    if pc.startswith("BKASH"):
        return _bkash()
    if pc.startswith("BPAY"):
        return _bpay()
    if pc.startswith("ADV"):
        return _adv_wallet()
    if pc.startswith("PP"):
        return _paypal()
    if pc.startswith("WISE"):
        return _wise()
    if pc.startswith("MIR"):
        return _mir_card()
    if pc == "SBPRUB":
        return _sbp_rub()
    if "QR" in pc:
        return _qr_payment()
    if "NFC" in pc:
        return _nfc_phone()
    if pc == "MWRUB":
        return _phone_balance()
    if pc.startswith("MP"):
        return _mercado()
    if pc.startswith("ID") and len(pc) > 2:
        return _idram_style()
    if cur in crypto_curs:
        return _crypto()
    if cur in FIAT_DOMESTIC_MARKERS:
        return _domestic_fiat_bank()
    return _generic()


def _load_overrides(path: Optional[Path]) -> Dict[str, List[Dict[str, Any]]]:
    if path is None or not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    ov = raw.get("overrides") or {}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for code, block in ov.items():
        if not isinstance(block, dict):
            continue
        fields = block.get("fields")
        if isinstance(fields, list):
            out[str(code)] = fields
    return out


def _parse_override_fields(
    code: str,
    rows: List[Dict[str, Any]],
) -> List[PaymentFormField]:
    fields: List[PaymentFormField] = []
    for i, row in enumerate(rows):
        try:
            fields.append(PaymentFormField.model_validate(row))
        except Exception as e:
            raise ValueError(f"overrides[{code}].fields[{i}]: {e}") from e
    return fields


def build_forms(
    bc: BestchangeExportYaml,
    overrides_path: Optional[Path],
) -> Tuple[PaymentFormsYaml, Set[str], Set[str], Set[str]]:
    crypto_curs = _crypto_currencies(bc.payment_methods)
    overrides_raw = _load_overrides(overrides_path)
    forms: Dict[str, PaymentForm] = {}
    bc_codes: Set[str] = set()
    missing_override: Set[str] = set()

    for pm in bc.payment_methods:
        code = pm.payment_code
        if not code:
            continue
        bc_codes.add(code)

        if code in overrides_raw:
            try:
                fields = _parse_override_fields(code, overrides_raw[code])
            except ValueError as e:
                raise SystemExit(str(e)) from e
            forms[code] = PaymentForm(fields=fields)
            continue

        forms[code] = PaymentForm(fields=classify_fields(pm, crypto_curs))

    for code in overrides_raw:
        if code not in bc_codes:
            missing_override.add(code)

    meta = PaymentFormsMeta(
        schema_version=1,
        bc_source=PaymentFormsBcSourceMeta(
            file="bc.yaml",
            exported_at=bc.meta.exported_at,
        ),
    )
    data = PaymentFormsYaml(meta=meta, forms=forms)
    label_keys = {f.label_key for form in forms.values() for f in form.fields}
    return data, bc_codes, missing_override, label_keys


def _dump_yaml(payload: PaymentFormsYaml) -> str:
    """Сериализация: сортировка ключей форм для стабильного диффа."""
    primitive = payload.model_dump(mode="json")
    ordered_forms = dict(sorted(primitive["forms"].items(), key=lambda x: x[0]))
    primitive["forms"] = ordered_forms
    return yaml.dump(
        primitive,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def run_check(forms_path: Path, bc_path: Path, overrides_path: Optional[Path]) -> int:
    bc = load_bestchange_export_yaml(bc_path)
    built, bc_codes, missing_override, _ = build_forms(bc, overrides_path)
    if not forms_path.is_file():
        print(f"Нет файла {forms_path}", file=sys.stderr)
        return 1
    disk = load_payment_forms_yaml(forms_path)

    errs: List[str] = []
    if missing_override:
        errs.append(f"В overrides неизвестные payment_code: {sorted(missing_override)}")

    missing_on_disk = bc_codes - set(disk.forms.keys())
    extra_on_disk = set(disk.forms.keys()) - bc_codes
    if missing_on_disk:
        errs.append(f"В forms.yaml нет ключей: {sorted(missing_on_disk)}")
    if extra_on_disk:
        errs.append(f"Лишние ключи в forms.yaml: {sorted(extra_on_disk)}")

    built_dump = built.model_dump(mode="json")
    disk_dump = disk.model_dump(mode="json")
    if built_dump != disk_dump:
        errs.append(
            f"Содержимое {forms_path} не совпадает с пересчётом из {bc_path} "
            "(перегенерируйте: poetry run python scripts/build_payment_forms_yaml.py -o forms.yaml)"
        )

    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 1
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Сборка forms.yaml из bc.yaml")
    ap.add_argument(
        "-b",
        "--bc",
        type=Path,
        default=Path("bc.yaml"),
        help="Путь к bc.yaml",
    )
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Записать forms.yaml (по умолчанию только --check)",
    )
    ap.add_argument(
        "--overrides",
        type=Path,
        default=None,
        help="YAML с блоком overrides: payment_code → fields",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Проверить, что существующий forms.yaml совпадает с генерацией из bc.yaml",
    )
    ap.add_argument(
        "--print-label-keys",
        action="store_true",
        help="Вывести уникальные label_key в stdout",
    )
    args = ap.parse_args()

    bc_path = args.bc
    if not bc_path.is_file():
        raise SystemExit(f"Нет файла {bc_path}")

    overrides_path = args.overrides
    if overrides_path is None:
        default_ov = _ROOT / "i18n" / "payment_forms_overrides.yaml"
        if default_ov.is_file():
            overrides_path = default_ov

    bc = load_bestchange_export_yaml(bc_path)
    built, bc_codes, missing_override, label_keys = build_forms(bc, overrides_path)

    if missing_override:
        print(
            f"Предупреждение: в overrides неизвестные коды: {sorted(missing_override)}",
            file=sys.stderr,
        )

    if args.print_label_keys:
        for k in sorted(label_keys):
            print(k)

    if args.output:
        args.output.write_text(_dump_yaml(built), encoding="utf-8")
        print(f"Записано {args.output} ({len(built.forms)} форм).")

    if args.check:
        target = args.output if args.output else Path("forms.yaml")
        rc = run_check(target, bc_path, overrides_path)
        raise SystemExit(rc)

    if not args.output and not args.print_label_keys:
        ap.print_help()
        print("\nУкажите -o forms.yaml, --print-label-keys или --check.", file=sys.stderr)


if __name__ == "__main__":
    main()
