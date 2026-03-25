"""wallets ethereum_address nullable

Revision ID: f8e9a0b1c2d3
Revises: e3f4a5b6c7d8
Create Date: 2026-03-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8e9a0b1c2d3"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "wallets",
        "ethereum_address",
        existing_type=sa.String(length=42),
        nullable=True,
        existing_comment="Ethereum address",
    )


def downgrade() -> None:
    conn = op.get_bind()
    n = conn.execute(
        sa.text("SELECT COUNT(*) FROM wallets WHERE ethereum_address IS NULL")
    ).scalar()
    if n and int(n) > 0:
        raise RuntimeError(
            "Cannot downgrade: fill wallets.ethereum_address for NULL rows first"
        )
    op.alter_column(
        "wallets",
        "ethereum_address",
        existing_type=sa.String(length=42),
        nullable=False,
        existing_comment="Ethereum address",
    )
