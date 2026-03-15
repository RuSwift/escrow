"""add wallet_user_subs table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_user_subs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_user_id", sa.Integer(), nullable=False, comment="Parent WalletUser (manager)"),
        sa.Column("wallet_address", sa.String(length=255), nullable=False, comment="Sub-account wallet address"),
        sa.Column("blockchain", sa.String(length=20), nullable=False, comment="Blockchain: tron, ethereum, etc."),
        sa.Column("nickname", sa.String(length=100), nullable=True, comment="Display name for sub-account"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["wallet_user_id"], ["wallet_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_user_id", "wallet_address", "blockchain", name="uq_wallet_user_sub_parent_address_chain"),
    )
    op.create_index(op.f("ix_wallet_user_subs_id"), "wallet_user_subs", ["id"], unique=False)
    op.create_index(op.f("ix_wallet_user_subs_wallet_user_id"), "wallet_user_subs", ["wallet_user_id"], unique=False)
    op.create_index(op.f("ix_wallet_user_subs_wallet_address"), "wallet_user_subs", ["wallet_address"], unique=False)
    op.create_index(op.f("ix_wallet_user_subs_blockchain"), "wallet_user_subs", ["blockchain"], unique=False)
    op.create_index(op.f("ix_wallet_user_subs_nickname"), "wallet_user_subs", ["nickname"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_wallet_user_subs_nickname"), table_name="wallet_user_subs")
    op.drop_index(op.f("ix_wallet_user_subs_blockchain"), table_name="wallet_user_subs")
    op.drop_index(op.f("ix_wallet_user_subs_wallet_address"), table_name="wallet_user_subs")
    op.drop_index(op.f("ix_wallet_user_subs_wallet_user_id"), table_name="wallet_user_subs")
    op.drop_index(op.f("ix_wallet_user_subs_id"), table_name="wallet_user_subs")
    op.drop_table("wallet_user_subs")
