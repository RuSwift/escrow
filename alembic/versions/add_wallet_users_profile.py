"""add wallet_users.profile (JSONB)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallet_users",
        sa.Column(
            "profile",
            postgresql.JSONB(),
            nullable=True,
            comment="Space profile: description, icon (base64)",
        ),
    )


def downgrade() -> None:
    op.drop_column("wallet_users", "profile")
