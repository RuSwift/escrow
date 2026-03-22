"""
Репозиторий строки состояния дашборда (dashboard_state, id=1): котировки по движкам.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DashboardState


class DashboardStateRepository:
    """Чтение/merge колонки ``ratios`` без вызова внешних API."""

    DASHBOARD_ROW_ID = 1

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_ratios(self) -> Optional[Dict[str, Any]]:
        """Весь объект ratios или ``None``, если строки нет."""
        stmt = select(DashboardState).where(DashboardState.id == self.DASHBOARD_ROW_ID)
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            return None
        if row.ratios is None:
            return {}
        return dict(row.ratios)

    async def merge_ratios_engines(self, partial: Dict[str, Any]) -> None:
        """
        Объединяет ``partial`` (ключ = метка движка) с текущим JSONB.
        Строка ``id=1`` создаётся при отсутствии (миграция обычно уже создала seed).
        """
        stmt = (
            select(DashboardState)
            .where(DashboardState.id == self.DASHBOARD_ROW_ID)
            .with_for_update()
        )
        res = await self._session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is None:
            row = DashboardState(id=self.DASHBOARD_ROW_ID, ratios={})
            self._session.add(row)
            await self._session.flush()

        current: Dict[str, Any] = {}
        if row.ratios is not None:
            current = dict(row.ratios)
        current.update(partial)
        row.ratios = current
