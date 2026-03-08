"""
Admin service: business logic for admin credentials (password + TRON addresses).
Uses AdminRepository for CRUD; commit/refresh in service.
"""
from typing import List, Optional

from passlib.context import CryptContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AdminUser, AdminTronAddress
from repos.admin import AdminRepository, AdminTronAddressRepository
from services.tron_auth import TronAuth
from settings import AdminSettings, Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminService:
    """Service for managing admin credentials (single admin with multiple auth methods)."""

    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,
        settings: Settings,
    ):
        self._session = session
        self._redis = redis
        self._settings = settings
        self._repo = AdminRepository(
            session=session, redis=redis, settings=settings
        )
        self._tron_repo = AdminTronAddressRepository(
            session=session, redis=redis, settings=settings
        )

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def validate_tron_address(address: str) -> bool:
        """Validate TRON address format (T + 34 base58). Delegates to TronAuth."""
        return TronAuth.validate_tron_address((address or "").strip())

    # --- Admin ---

    async def get_admin(self) -> Optional[AdminUser]:
        """Get the single admin user (id=1)."""
        return await self._repo.get()

    async def ensure_admin_exists(self) -> AdminUser:
        """Ensure admin user exists, create if not."""
        admin = await self._repo.get()
        if not admin:
            await self._repo.create()
            await self._session.commit()
            admin = await self._repo.get()
            assert admin is not None
        return admin

    async def is_admin_configured(self) -> bool:
        """True if admin has password or at least one active TRON address."""
        admin = await self._repo.get()
        if not admin:
            return False
        has_password = bool(admin.username and admin.password_hash)
        addresses = await self._tron_repo.list(active_only=True)
        has_tron = len(addresses) > 0
        return has_password or has_tron

    # --- Password ---

    async def set_password(self, username: str, password: str) -> AdminUser:
        """Set or update admin password. Raises ValueError if validation fails."""
        if not username or not password:
            raise ValueError("Username and password are required")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters long")
        await self.ensure_admin_exists()
        password_hash = self.hash_password(password)
        await self._repo.patch(username=username, password_hash=password_hash)
        await self._session.commit()
        admin = await self._repo.get()
        assert admin is not None
        await self._session.refresh(admin)
        return admin

    async def change_password(
        self, old_password: str, new_password: str
    ) -> AdminUser:
        """Change admin password (requires old password). Raises ValueError on failure."""
        admin = await self._repo.get()
        if not admin or not admin.password_hash:
            raise ValueError("Password authentication not configured")
        if not self.verify_password(old_password, admin.password_hash):
            raise ValueError("Incorrect current password")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters long")
        password_hash = self.hash_password(new_password)
        await self._repo.patch(password_hash=password_hash)
        await self._session.commit()
        await self._session.refresh(admin)
        return admin

    async def remove_password(self) -> AdminUser:
        """Remove password auth. Raises ValueError if no TRON addresses configured."""
        addresses = await self._tron_repo.list(active_only=True)
        if len(addresses) == 0:
            raise ValueError(
                "Cannot remove password: no TRON addresses configured"
            )
        admin = await self._repo.get()
        if not admin:
            raise ValueError("Admin not found")
        await self._repo.patch(username=None, password_hash=None)
        await self._session.commit()
        await self._session.refresh(admin)
        return admin

    async def verify_password_auth(
        self, username: str, password: str
    ) -> Optional[AdminUser]:
        """Verify admin credentials. Returns AdminUser if valid, None otherwise."""
        admin = await self._repo.get()
        if not admin or not admin.username or not admin.password_hash:
            return None
        if admin.username != username:
            return None
        if self.verify_password(password, admin.password_hash):
            return admin
        return None

    # --- TRON addresses ---

    async def add_tron_address(
        self, tron_address: str, label: Optional[str] = None
    ) -> AdminTronAddress:
        """Add TRON address to whitelist. Raises ValueError if invalid or duplicate."""
        if not self.validate_tron_address(tron_address):
            raise ValueError("Invalid TRON address format")
        await self.ensure_admin_exists()
        if await self._tron_repo.get_by_address(tron_address):
            raise ValueError(f"TRON address '{tron_address}' already registered")
        addr = await self._tron_repo.create(
            tron_address=tron_address, label=label, is_active=True
        )
        await self._session.commit()
        await self._session.refresh(addr)
        return addr

    async def get_tron_addresses(
        self, active_only: bool = True
    ) -> List[AdminTronAddress]:
        """Get all TRON addresses."""
        return await self._tron_repo.list(active_only=active_only)

    async def update_tron_address(
        self,
        tron_id: int,
        new_address: Optional[str] = None,
        new_label: Optional[str] = None,
    ) -> AdminTronAddress:
        """Update TRON address or label. Raises ValueError if not found or invalid."""
        tron_addr = await self._tron_repo.get(tron_id)
        if not tron_addr:
            raise ValueError("TRON address not found")
        if new_address:
            if not self.validate_tron_address(new_address):
                raise ValueError("Invalid TRON address format")
            other = await self._tron_repo.get_by_address(new_address)
            if other and other.id != tron_id:
                raise ValueError("TRON address already in use")
        update_values = {}
        if new_address:
            update_values["tron_address"] = new_address
        if new_label is not None:
            update_values["label"] = new_label
        if update_values:
            await self._tron_repo.patch(tron_id, **update_values)
            await self._session.commit()
            await self._session.refresh(tron_addr)
        return tron_addr

    async def toggle_tron_address(
        self, tron_id: int, is_active: bool
    ) -> AdminTronAddress:
        """Toggle TRON address active status. Raises ValueError if not found."""
        tron_addr = await self._tron_repo.get(tron_id)
        if not tron_addr:
            raise ValueError("TRON address not found")
        await self._tron_repo.patch(tron_id, is_active=is_active)
        await self._session.commit()
        await self._session.refresh(tron_addr)
        return tron_addr

    async def delete_tron_address(self, tron_id: int) -> None:
        """Delete TRON address. Raises ValueError if last auth method."""
        admin = await self._repo.get()
        has_password = bool(
            admin and admin.username and admin.password_hash
        )
        addresses = await self._tron_repo.list(active_only=True)
        tron_count = len(addresses)
        if not has_password and tron_count <= 1:
            raise ValueError(
                "Cannot delete last authentication method. "
                "Add password or another TRON address first."
            )
        await self._tron_repo.delete(tron_id)
        await self._session.commit()

    async def verify_tron_auth(self, tron_address: str) -> bool:
        """True if TRON address is whitelisted and active."""
        addr = await self._tron_repo.get_by_address(tron_address)
        return addr is not None and addr.is_active

    # --- Init from env (for manual/CLI use; not called from lifespan) ---

    async def init_from_env(self, admin_settings: AdminSettings) -> bool:
        """
        Initialize admin from environment variables if configured.
        Pass settings.admin. Returns True if configured from env, False otherwise.
        """
        if not admin_settings.is_configured:
            return False
        await self._tron_repo.delete_all()
        await self._repo.delete()
        await self._session.commit()
        await self.ensure_admin_exists()
        try:
            if admin_settings.method == "password":
                if admin_settings.username and admin_settings.password:
                    await self.set_password(
                        admin_settings.username,
                        admin_settings.password.get_secret_value(),
                    )
                    return True
            elif admin_settings.method == "tron":
                if admin_settings.tron_address:
                    await self.add_tron_address(
                        admin_settings.tron_address, label="From ENV"
                    )
                    return True
        except ValueError as e:
            print(f"Error configuring admin from ENV: {e}")
            return False
        return False
