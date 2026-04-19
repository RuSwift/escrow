"""payment_request.space -> space_id FK wallet_users

Revision ID: payreqsid01
Revises: payreq01
Create Date: 2026-04-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "payreqsid01"
down_revision: Union[str, None] = "payreq01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_request",
        sa.Column("space_id", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE payment_request pr
            SET space_id = wu.id
            FROM wallet_users wu
            WHERE wu.nickname = pr.space
            """
        )
    )
    op.execute(sa.text("DELETE FROM payment_request WHERE space_id IS NULL"))
    op.drop_index("ix_payment_request_space", table_name="payment_request")
    op.drop_column("payment_request", "space")
    op.alter_column(
        "payment_request",
        "space_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "payment_request_space_id_fkey",
        "payment_request",
        "wallet_users",
        ["space_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_payment_request_space_id",
        "payment_request",
        ["space_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_request_space_id", table_name="payment_request")
    op.drop_constraint(
        "payment_request_space_id_fkey", "payment_request", type_="foreignkey"
    )
    op.add_column(
        "payment_request",
        sa.Column("space", sa.String(length=255), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE payment_request pr
            SET space = wu.nickname
            FROM wallet_users wu
            WHERE wu.id = pr.space_id
            """
        )
    )
    op.alter_column(
        "payment_request",
        "space",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.drop_column("payment_request", "space_id")
    op.create_index(
        "ix_payment_request_space",
        "payment_request",
        ["space"],
        unique=False,
    )
