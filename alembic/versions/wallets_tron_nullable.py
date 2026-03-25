"""wallets tron_address nullable

Revision ID: g9h0i1j2k3l4
Revises: f8e9a0b1c2d3
Create Date: 2026-03-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "g9h0i1j2k3l4"
down_revision: Union[str, None] = "f8e9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "wallets",
        "tron_address",
        existing_type=sa.String(length=34),
        nullable=True,
        existing_comment="TRON address",
    )


def downgrade() -> None:
    conn = op.get_bind()
    n = conn.execute(
        sa.text("SELECT COUNT(*) FROM wallets WHERE tron_address IS NULL")
    ).scalar()
    if n and int(n) > 0:
        raise RuntimeError(
            "Cannot downgrade: fill wallets.tron_address for NULL rows first"
        )
    op.alter_column(
        "wallets",
        "tron_address",
        existing_type=sa.String(length=34),
        nullable=False,
        existing_comment="TRON address",
    )
