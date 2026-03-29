"""orders: drop wallet_id (связь в payload)

Revision ID: dropordwid2026
Revises: orders20260329
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "dropordwid2026"
down_revision: Union[str, None] = "orders20260329"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_orders_wallet_id", table_name="orders")
    op.drop_constraint("orders_wallet_id_fkey", "orders", type_="foreignkey")
    op.drop_column("orders", "wallet_id")


def downgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "wallet_id",
            sa.Integer(),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=True,
            comment="Ramp-кошелёк при привязке",
        ),
    )
    op.create_index("ix_orders_wallet_id", "orders", ["wallet_id"], unique=False)
