"""Короткие публичные идентификаторы (алфавит в духе Base58, без 0/O/I/l)."""

from __future__ import annotations

import secrets

# 32 символа: только строчные и цифры, однозначно под func.lower() в URL/SQL.
_PUBLIC_REF_ALPHABET = "123456789abcdefghijkmnopqrstuvwxyz"
PUBLIC_REF_LENGTH = 9


def generate_public_ref(length: int = PUBLIC_REF_LENGTH) -> str:
    """Криптоустойчивая строка фиксированной длины для колонки public_ref."""
    if length < 8 or length > 10:
        raise ValueError("length must be between 8 and 10")
    return "".join(secrets.choice(_PUBLIC_REF_ALPHABET) for _ in range(length))
