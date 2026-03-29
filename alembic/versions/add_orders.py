"""orders: эфемерные и будущие сделки (JSONB)

Revision ID: orders20260329
Revises: didweb20260326
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "orders20260329"
down_revision: Union[str, None] = "didweb20260326"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "category",
            sa.String(length=32),
            nullable=False,
            comment="ephemeral | deal | …",
        ),
        sa.Column(
            "dedupe_key",
            sa.String(length=255),
            nullable=False,
            comment="Стабильный ключ для upsert refresh",
        ),
        sa.Column(
            "wallet_id",
            sa.Integer(),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=True,
            comment="FK на ramp-кошелёк при необходимости",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="kind, diff, статусы multisig, адреса — гибко через JSON",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="orders_pkey"),
        sa.UniqueConstraint("dedupe_key", name="uq_orders_dedupe_key"),
    )
    op.create_index("ix_orders_category", "orders", ["category"], unique=False)
    op.create_index("ix_orders_wallet_id", "orders", ["wallet_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_wallet_id", table_name="orders")
    op.drop_index("ix_orders_category", table_name="orders")
    op.drop_table("orders")
