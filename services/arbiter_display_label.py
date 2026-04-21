"""
Человекочитаемая подпись для сегмента /arbiter/{segment} (DID ноды или public slug).
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import GuarantorProfile, Wallet, WalletUser

_ARBITER_ROLES = ("arbiter", "arbiter-backup")


async def arbiter_segment_display_label(
    session: AsyncSession, segment: str
) -> Optional[str]:
    """
    Имя кошелька арбитра по owner_did (DID) или ник владельца профиля гаранта (slug).
    """
    raw = (segment or "").strip()
    if not raw:
        return None
    if raw.lower().startswith("did:"):
        role_order = case(
            (Wallet.role == "arbiter", 0),
            (Wallet.role == "arbiter-backup", 1),
            else_=2,
        )
        stmt = (
            select(Wallet.name)
            .where(Wallet.owner_did == raw)
            .where(Wallet.role.in_(_ARBITER_ROLES))
            .order_by(role_order, Wallet.id.asc())
            .limit(1)
        )
        res = await session.execute(stmt)
        name = res.scalar_one_or_none()
        if name and str(name).strip():
            return str(name).strip()
        return None
    slug = raw.lower()
    stmt = select(GuarantorProfile).where(
        GuarantorProfile.arbiter_public_slug == slug
    ).limit(1)
    res = await session.execute(stmt)
    prof = res.scalar_one_or_none()
    if prof is None:
        return None
    wu = await session.get(WalletUser, prof.wallet_user_id)
    if wu is None:
        return None
    nick = (wu.nickname or "").strip()
    return nick or None
