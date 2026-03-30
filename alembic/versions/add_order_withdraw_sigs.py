"""order_withdrawal_signatures: подписи заявок на вывод

Revision ID: ordwdsig2026
Revises: ordspacewid2026
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ordwdsig2026"
down_revision: Union[str, None] = "ordspacewid2026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_withdrawal_signatures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "order_id",
            sa.BigInteger(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "signer_address",
            sa.String(length=64),
            nullable=False,
            comment="TRON base58 адрес подписанта",
        ),
        sa.Column(
            "signature_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Фрагмент подписи / partial signed tx (Tron)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="order_withdrawal_signatures_pkey"),
        sa.UniqueConstraint(
            "order_id",
            "signer_address",
            name="uq_order_withdrawal_sig_order_signer",
        ),
    )
    op.create_index(
        "ix_order_withdrawal_signatures_order_id",
        "order_withdrawal_signatures",
        ["order_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_order_withdrawal_signatures_order_id",
        table_name="order_withdrawal_signatures",
    )
    op.drop_table("order_withdrawal_signatures")
