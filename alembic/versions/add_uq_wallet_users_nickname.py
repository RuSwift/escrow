"""add unique constraint wallet_users.nickname

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f("ix_wallet_users_nickname"), table_name="wallet_users")
    op.create_unique_constraint(
        "uq_wallet_users_nickname",
        "wallet_users",
        ["nickname"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_wallet_users_nickname"), table_name="wallet_users")
    op.drop_constraint("uq_wallet_users_nickname", "wallet_users", type_="unique")
    op.create_index(
        op.f("ix_wallet_users_nickname"),
        "wallet_users",
        ["nickname"],
        unique=True,
    )
