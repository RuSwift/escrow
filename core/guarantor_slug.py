"""Публичный nickname гаранта для пути /arbiter/{nickname}."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def normalize_arbiter_public_slug(raw: str | None) -> str | None:
    """
    Нормализует nickname (lowercase) или None для сброса.
    Пустая строка после strip — сброс (None).
    Raises ValueError при неверном формате.
    """
    if raw is None:
        return None
    t = raw.strip().lower()
    if not t:
        return None
    if len(t) < 3 or len(t) > 32:
        raise ValueError("Nickname must be 3–32 characters.")
    if not _SLUG_RE.match(t):
        raise ValueError(
            "Nickname may contain only lowercase letters, digits, and hyphens; "
            "no leading or trailing hyphen."
        )
    return t
