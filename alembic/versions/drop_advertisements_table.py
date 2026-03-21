"""drop advertisements table

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("advertisements")


def downgrade() -> None:
    op.create_table(
        "advertisements",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Autoincrement primary key",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
            comment="User ID from wallet_users table",
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="Display name for the advertisement",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            comment="Detailed description of the offer",
        ),
        sa.Column(
            "fee",
            sa.String(length=10),
            nullable=False,
            comment="Fee percentage (e.g. '2.5')",
        ),
        sa.Column(
            "min_limit",
            sa.Integer(),
            nullable=False,
            comment="Minimum transaction limit in USDT",
        ),
        sa.Column(
            "max_limit",
            sa.Integer(),
            nullable=False,
            comment="Maximum transaction limit in USDT",
        ),
        sa.Column(
            "currency",
            sa.String(length=10),
            nullable=False,
            comment="Currency code (USD, EUR, RUB, etc.)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="Whether the advertisement is active",
        ),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            comment="Whether the advertisement is verified by admin",
        ),
        sa.Column(
            "escrow_enabled",
            sa.Boolean(),
            nullable=False,
            comment=(
                "Whether escrow deals are enabled (agent conducts deal using their "
                "liquidity, debiting funds from escrow address upon service delivery)"
            ),
        ),
        sa.Column(
            "rating",
            sa.String(length=10),
            nullable=True,
            comment="User rating (e.g. '4.9')",
        ),
        sa.Column(
            "deals_count",
            sa.Integer(),
            nullable=False,
            comment="Number of completed deals",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last update timestamp (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_advertisements_currency_active",
        "advertisements",
        ["currency", "is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advertisements_id"), "advertisements", ["id"], unique=False
    )
    op.create_index(
        "ix_advertisements_user_active",
        "advertisements",
        ["user_id", "is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advertisements_user_id"), "advertisements", ["user_id"], unique=False
    )
