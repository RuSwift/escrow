"""Схемы GET/PATCH UI-предпочтений для main app."""
from typing import Any, Dict

from pydantic import BaseModel, Field


class WalletSpaceUIPrefsResponse(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
