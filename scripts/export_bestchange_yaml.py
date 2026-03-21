#!/usr/bin/env python3
"""
Выгрузка в YAML данных BestChange (архив info.zip):
- payment_methods: payment_code, cur, payment_name (+ payment_name_en при --en);
- cities: id, name (+ name_en при --en).

Структура задаётся Pydantic-моделями в ``scripts/schemas.py`` (``BestchangeExportYaml``).

Запуск из корня репозитория (с вирт. окружением):
  poetry run python scripts/export_bestchange_yaml.py -o bestchange.yaml

С переводом на английский (ручной YAML + цепочка автоперевода):
  poetry run python scripts/export_bestchange_yaml.py -o bc.yaml --en \\
    --en-manual i18n/bestchange_en.yaml \\
    --en-sources manual,google,mymemory,libre

Локальный ZIP без скачивания:
  poetry run python scripts/export_bestchange_yaml.py --zip /path/to/info.zip -o out.yaml

Настройки URL и путей — из settings (RATIOS_BESTCHANGE_*, .env / .env.local).
См. scripts/bestchange_i18n.py — список источников и переменных окружения для API.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import yaml

from scripts.bestchange_i18n import apply_english
from scripts.schemas import (
    BestchangeCity,
    BestchangeExportMeta,
    BestchangeExportYaml,
    BestchangePaymentMethod,
)

from services.ratios.bestchange import BestChangeRatios, Cities, Currencies, Rates
from settings import BestChangeSettings, Settings


class _NoopCache:
    """Кэш не нужен для однократной загрузки ZIP."""

    async def get(self, key: str) -> None:
        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        return None


def _resolve_bestchange_settings(args: argparse.Namespace) -> BestChangeSettings:
    if args.url or args.zip_path or args.enc:
        base = BestChangeSettings()
        data = base.model_dump()
        if args.url:
            data["url"] = args.url
        if args.zip_path:
            data["zip_path"] = args.zip_path
        if args.enc:
            data["enc"] = args.enc
        return BestChangeSettings(**data)
    ratios = Settings().ratios
    if ratios and ratios.bestchange:
        return ratios.bestchange
    return BestChangeSettings()


def _build_payment_methods(currencies: Currencies) -> List[BestchangePaymentMethod]:
    """Уникальные способы оплаты: payment_code + cur + payment_name (из bm_cy + коды)."""
    seen: Set[Tuple[Optional[str], Optional[str], str]] = set()
    rows: List[BestchangePaymentMethod] = []
    for _id, d in sorted(currencies.data.items(), key=lambda x: x[0]):
        pc = d.get("payment_code")
        cur = d.get("cur_code")
        name = d.get("name") or ""
        key = (pc, cur, name)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            BestchangePaymentMethod(
                payment_code=pc,
                cur=cur,
                payment_name=name,
            )
        )
    rows.sort(
        key=lambda x: (
            (x.cur or ""),
            (x.payment_code or ""),
            x.payment_name,
        )
    )
    return rows


def _build_cities_from_rates(
    rates: Rates, cities: Cities
) -> List[BestchangeCity]:
    city_ids: Set[int] = set()
    for row in rates.get():
        try:
            city_ids.add(int(row["city_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    out: List[BestchangeCity] = []
    for cid in sorted(city_ids):
        info = cities.data.get(cid)
        out.append(
            BestchangeCity(
                id=cid,
                name=info["name"] if info else None,
            )
        )
    return out


async def _load(
    settings: BestChangeSettings, forced_zip: Optional[str]
) -> Tuple[Rates, Currencies, Cities]:
    engine = BestChangeRatios(
        _NoopCache(),
        settings,
        refresh_cache=True,
        forced_zip_file=forced_zip,
    )
    rates, currencies, _ex, cities = await engine.load_from_server()
    return rates, currencies, cities


async def _run(args: argparse.Namespace) -> BestchangeExportYaml:
    settings = _resolve_bestchange_settings(args)
    forced = str(args.zip) if args.zip else None
    rates, currencies, cities = await _load(settings, forced)

    export = BestchangeExportYaml(
        meta=BestchangeExportMeta(
            source_url=settings.url,
            zip_path=settings.zip_path,
            encoding=settings.enc,
            exported_at=datetime.now(timezone.utc).isoformat(),
        ),
        payment_methods=_build_payment_methods(currencies),
        cities=_build_cities_from_rates(rates, cities),
    )
    if args.en:
        manual = args.en_manual
        if manual is None:
            default_manual = _ROOT / "i18n" / "bestchange_en.yaml"
            manual = default_manual if default_manual.is_file() else None
        sources = [s.strip() for s in args.en_sources.split(",") if s.strip()]
        apply_english(export, manual_path=manual, sources=sources)
    return export


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Экспорт способов оплаты и городов BestChange в YAML"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Файл вывода (по умолчанию stdout)",
    )
    parser.add_argument(
        "--zip",
        type=Path,
        help="Локальный info.zip (без HTTP-загрузки)",
    )
    parser.add_argument("--url", help="Переопределить URL архива")
    parser.add_argument("--zip-path", dest="zip_path", help="Куда сохранять ZIP при скачивании")
    parser.add_argument("--enc", help="Кодировка файлов в архиве (например windows-1251)")
    parser.add_argument(
        "--en",
        action="store_true",
        help="Добавить payment_name_en и name_en (ручной YAML + автоперевод)",
    )
    parser.add_argument(
        "--en-manual",
        type=Path,
        default=None,
        help="YAML с переводами (по умолчанию i18n/bestchange_en.yaml, если существует)",
    )
    parser.add_argument(
        "--en-sources",
        default="manual,google,mymemory,libre",
        help=(
            "Цепочка источников через запятую: manual, google, mymemory, libre, "
            "deepl, bing, yandex, chatgpt (см. scripts/bestchange_i18n.py)"
        ),
    )
    args = parser.parse_args()

    data = asyncio.run(_run(args))

    text = yaml.safe_dump(
        data.model_dump(mode="json", exclude_none=True),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
