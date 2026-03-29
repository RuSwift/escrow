"""orders: space_wallet_id FK на wallets

Revision ID: ordspacewid2026
Revises: dropordwid2026
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ordspacewid2026"
down_revision: Union[str, None] = "dropordwid2026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "space_wallet_id",
            sa.Integer(),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=True,
            comment="Ramp-кошелёк спейса (связь с owner через wallets.owner_did)",
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE orders o
            SET space_wallet_id = (o.payload->>'wallet_id')::integer
            WHERE o.payload ? 'wallet_id'
              AND (o.payload->>'wallet_id') ~ '^[0-9]+$'
            """
        )
    )
    op.create_index(
        "ix_orders_space_wallet_id",
        "orders",
        ["space_wallet_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_orders_space_wallet_id", table_name="orders")
    op.drop_column("orders", "space_wallet_id")
