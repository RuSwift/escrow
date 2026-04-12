"""Репозиторий: UI-настройки main app (wallet_user + space)."""
from __future__ import annotations

import copy
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WalletSpaceUIPrefs

_MAX_PAYLOAD_JSON_LEN = 16_384


def _deep_merge_shallow_sections(existing: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Сливает patch в existing: верхний уровень и вложенные dict для известных секций."""
    out = copy.deepcopy(existing) if existing else {}
    for key, val in patch.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(val, dict)
        ):
            merged = {**out[key], **val}
            out[key] = merged
        else:
            out[key] = copy.deepcopy(val) if isinstance(val, dict) else val
    return out


class WalletSpaceUIPrefsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_payload(self, wallet_user_id: int, space: str) -> Dict[str, Any]:
        sp = (space or "").strip()
        stmt = select(WalletSpaceUIPrefs).where(
            WalletSpaceUIPrefs.wallet_user_id == wallet_user_id,
            WalletSpaceUIPrefs.space == sp,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if not row or row.payload is None:
            return {}
        if isinstance(row.payload, dict):
            return dict(row.payload)
        return {}

    async def merge_payload(
        self,
        wallet_user_id: int,
        space: str,
        patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        sp = (space or "").strip()
        current = await self.get_payload(wallet_user_id, sp)
        merged = _deep_merge_shallow_sections(current, patch)
        raw = __import__("json").dumps(merged, ensure_ascii=False)
        if len(raw) > _MAX_PAYLOAD_JSON_LEN:
            raise ValueError("UI preferences payload is too large")
        stmt = select(WalletSpaceUIPrefs).where(
            WalletSpaceUIPrefs.wallet_user_id == wallet_user_id,
            WalletSpaceUIPrefs.space == sp,
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row:
            row.payload = merged  # type: ignore[assignment]
        else:
            self._session.add(
                WalletSpaceUIPrefs(
                    wallet_user_id=wallet_user_id,
                    space=sp,
                    payload=merged,
                )
            )
        return merged
