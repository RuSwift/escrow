"""
Перевод строк BestChange (RU → EN) с цепочкой источников.

Источники (порядок задаётся ``--en-sources``):

1. **manual** — YAML: ``cities_by_id``, ``payments_by_key``, ``payments_by_name``
   (см. ``i18n/bestchange_en.example.yaml``).

2. Автоматические (``deep-translator``; при сбое — следующий в цепочке):

   - **google** — Google Translate
   - **mymemory** — MyMemory
   - **libre** — LibreTranslate (``LIBRETRANSLATE_URL``, по умолчанию публичный инстанс)
   - **deepl** — DeepL (``DEEPL_API_KEY``)
   - **bing** — Microsoft (``BING_TRANSLATE_KEY`` + при необходимости регион в env)
   - **yandex** — Yandex (``YANDEX_TRANSLATE_KEY``)
   - **chatgpt** — OpenAI (``OPENAI_API_KEY``)

Одинаковые строки в одном прогоне кэшируются в памяти.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from scripts.schemas import BestchangeExportTranslationMeta, BestchangeExportYaml


def load_manual(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "cities_by_id": raw.get("cities_by_id") or {},
        "payments_by_key": raw.get("payments_by_key") or {},
        "payments_by_name": raw.get("payments_by_name") or {},
    }


def _payment_lookup_key(cur: Optional[str], payment_code: Optional[str]) -> str:
    return f"{cur or ''}|{payment_code or ''}"


def manual_payment(
    manual: Dict[str, Any],
    cur: Optional[str],
    payment_code: Optional[str],
    payment_name: str,
) -> Optional[str]:
    m = manual.get("payments_by_key") or {}
    k = _payment_lookup_key(cur, payment_code)
    if k in m:
        return m[k]
    by_name = manual.get("payments_by_name") or {}
    return by_name.get(payment_name)


def manual_city(manual: Dict[str, Any], city_id: int) -> Optional[str]:
    m = manual.get("cities_by_id") or {}
    return m.get(city_id) or m.get(str(city_id))


def _translate_auto_one(text: str, engine: str, memo_fail: Set[str]) -> Optional[str]:
    if not text or not text.strip():
        return None
    tag = f"{engine}:{text}"
    if tag in memo_fail:
        return None
    try:
        from deep_translator import (
            ChatGptTranslator,
            DeeplTranslator,
            GoogleTranslator,
            LibreTranslator,
            MicrosoftTranslator,
            MyMemoryTranslator,
            YandexTranslator,
        )
    except ImportError:
        return None

    engine = engine.lower().strip()
    tr: Any = None
    try:
        if engine == "google":
            tr = GoogleTranslator(source="auto", target="en")
        elif engine == "mymemory":
            tr = MyMemoryTranslator(source="ru", target="en")
        elif engine == "libre":
            url = os.environ.get("LIBRETRANSLATE_URL", "https://libretranslate.com")
            tr = LibreTranslator(source="ru", target="en", base_url=url)
        elif engine == "deepl":
            key = os.environ.get("DEEPL_API_KEY")
            if not key:
                return None
            tr = DeeplTranslator(source="ru", target="en", api_key=key)
        elif engine == "bing":
            key = os.environ.get("BING_TRANSLATE_KEY")
            if not key:
                return None
            region = os.environ.get("BING_TRANSLATE_REGION")
            tr = MicrosoftTranslator(
                source="ru",
                target="en",
                api_key=key,
                region=region,
            )
        elif engine == "yandex":
            key = os.environ.get("YANDEX_TRANSLATE_KEY")
            if not key:
                return None
            tr = YandexTranslator(api_key=key, source="ru", target="en")
        elif engine == "chatgpt":
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                return None
            tr = ChatGptTranslator(api_key=key, source="ru", target="en")
        else:
            return None
        out = tr.translate(text)
        if out and isinstance(out, str) and out.strip():
            return out.strip()
    except Exception:
        memo_fail.add(tag)
    return None


def _auto_translate_cached(
    text: str,
    sources: List[str],
    memo_fail: Set[str],
    cache: Dict[str, str],
) -> Optional[str]:
    if not text:
        return None
    if text in cache:
        return cache[text]
    for src in sources:
        if src == "manual":
            continue
        en = _translate_auto_one(text, src, memo_fail)
        if en:
            cache[text] = en
            return en
    return None


def apply_english(
    payload: BestchangeExportYaml,
    *,
    manual_path: Optional[Path],
    sources: List[str],
) -> BestchangeExportYaml:
    """Добавляет ``payment_name_en`` и ``name_en``; обновляет ``meta.translation``."""
    manual = load_manual(manual_path) if manual_path else {}
    sources_l = [s.strip().lower() for s in sources if s.strip()]
    memo_fail: Set[str] = set()
    str_cache: Dict[str, str] = {}
    auto_order = [s for s in sources_l if s != "manual"]

    for row in payload.payment_methods:
        cur = row.cur
        pc = row.payment_code
        name = row.payment_name or ""
        en: Optional[str] = None
        if "manual" in sources_l and manual_path:
            en = manual_payment(manual, cur, pc, name)
        if not en and name and auto_order:
            en = _auto_translate_cached(name, auto_order, memo_fail, str_cache)
        row.payment_name_en = en

    for row in payload.cities:
        cid = row.id
        name = row.name or ""
        en: Optional[str] = None
        if "manual" in sources_l and manual_path:
            try:
                en = manual_city(manual, int(cid))
            except (TypeError, ValueError):
                en = None
        if not en and name and auto_order:
            en = _auto_translate_cached(name, auto_order, memo_fail, str_cache)
        row.name_en = en

    payload.meta.translation = BestchangeExportTranslationMeta(
        sources=sources_l,
        manual_file=str(manual_path) if manual_path else None,
    )
    return payload
