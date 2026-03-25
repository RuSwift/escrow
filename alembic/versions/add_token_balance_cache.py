"""token_balance_cache: fallback кэш балансов токена по сети

Revision ID: h2j3k4l5m6n7
Revises: g9h0i1j2k3l4
Create Date: 2026-03-25
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h2j3k4l5m6n7"
down_revision: Union[str, None] = "g9h0i1j2k3l4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "token_balance_cache",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("blockchain", sa.String(length=50), nullable=False),
        sa.Column("contract_address", sa.String(length=255), nullable=False),
        sa.Column("balance_raw", sa.Numeric(78, 0), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="token_balance_cache_pkey"),
    )

    op.create_unique_constraint(
        "uq_token_balance_cache_addr_chain_contract",
        "token_balance_cache",
        ["address", "blockchain", "contract_address"],
    )

    op.create_index(
        "ix_token_balance_cache_address",
        "token_balance_cache",
        ["address"],
        unique=False,
    )
    op.create_index(
        "ix_token_balance_cache_contract_address",
        "token_balance_cache",
        ["contract_address"],
        unique=False,
    )
    op.create_index(
        "ix_token_balance_cache_updated_at",
        "token_balance_cache",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_token_balance_cache_contract_address",
        table_name="token_balance_cache",
    )
    op.drop_index(
        "ix_token_balance_cache_address",
        table_name="token_balance_cache",
    )
    op.drop_index(
        "ix_token_balance_cache_updated_at",
        table_name="token_balance_cache",
    )
    op.drop_table("token_balance_cache")
