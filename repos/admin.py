"""
Admin repositories: AdminRepository (AdminUser id=1), AdminTronAddressRepository.
Only get / create / patch / delete primitives; no commit (caller commits).
"""
from typing import List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.models import AdminUser, AdminTronAddress
from repos.base import BaseRepository
from settings import Settings

ADMIN_USER_ID = 1


class AdminRepository(BaseRepository):
    """
    Repository for admin user (single row id=1).
    get(), create(), patch(**values), delete().
    """

    async def get(self) -> Optional[AdminUser]:
        """Get the single admin user (id=1)."""
        result = await self._session.execute(
            select(AdminUser).where(AdminUser.id == ADMIN_USER_ID)
        )
        return result.scalar_one_or_none()

    async def create(self) -> AdminUser:
        """Create the default admin row (id=1)."""
        admin = AdminUser(
            id=ADMIN_USER_ID,
            username=None,
            password_hash=None,
        )
        self._session.add(admin)
        await self._session.flush()
        await self._session.refresh(admin)
        return admin

    async def patch(self, **values: object) -> None:
        """Update admin user (id=1)."""
        await self._session.execute(
            update(AdminUser).where(AdminUser.id == ADMIN_USER_ID).values(**values)
        )

    async def delete(self) -> None:
        """Delete the admin user (id=1)."""
        await self._session.execute(
            delete(AdminUser).where(AdminUser.id == ADMIN_USER_ID)
        )


class AdminTronAddressRepository(BaseRepository):
    """
    Repository for AdminTronAddress.
    get(id), get_by_address(address), list(active_only), create(...), patch(id, **values), delete(id), delete_all().
    """

    async def get(self, id: int) -> Optional[AdminTronAddress]:
        """Get TRON address record by id."""
        result = await self._session.execute(
            select(AdminTronAddress).where(AdminTronAddress.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_address(self, address: str) -> Optional[AdminTronAddress]:
        """Get TRON address record by tron_address."""
        result = await self._session.execute(
            select(AdminTronAddress).where(AdminTronAddress.tron_address == address)
        )
        return result.scalar_one_or_none()

    async def list(self, active_only: bool = True) -> List[AdminTronAddress]:
        """List TRON addresses, optionally only active, ordered by created_at desc."""
        stmt = select(AdminTronAddress).order_by(AdminTronAddress.created_at.desc())
        if active_only:
            stmt = stmt.where(AdminTronAddress.is_active == True)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        tron_address: str,
        label: Optional[str] = None,
        is_active: bool = True,
    ) -> AdminTronAddress:
        """Create a TRON address record."""
        addr = AdminTronAddress(
            tron_address=tron_address,
            label=label,
            is_active=is_active,
        )
        self._session.add(addr)
        await self._session.flush()
        await self._session.refresh(addr)
        return addr

    async def patch(self, id: int, **values: object) -> None:
        """Update TRON address record by id."""
        await self._session.execute(
            update(AdminTronAddress).where(AdminTronAddress.id == id).values(**values)
        )

    async def delete(self, id: int) -> None:
        """Delete TRON address record by id."""
        await self._session.execute(
            delete(AdminTronAddress).where(AdminTronAddress.id == id)
        )

    async def delete_all(self) -> None:
        """Delete all TRON address records."""
        await self._session.execute(delete(AdminTronAddress))
