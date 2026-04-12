"""wallet_space_ui_prefs: UI state per wallet user + space

Revision ID: wsuiprefs01
Revises: exspform2026
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "wsuiprefs01"
down_revision: Union[str, None] = "exspform2026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallet_space_ui_prefs",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Autoincrement primary key",
        ),
        sa.Column(
            "wallet_user_id",
            sa.Integer(),
            nullable=False,
            comment="WalletUser.id of the logged-in account",
        ),
        sa.Column(
            "space",
            sa.String(length=255),
            nullable=False,
            comment="Space nickname (URL segment)",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="Arbitrary UI state JSON (e.g. my_business.ramp_wallets_expanded)",
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
        sa.ForeignKeyConstraint(
            ["wallet_user_id"],
            ["wallet_users.id"],
            name="wallet_space_ui_prefs_wallet_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="wallet_space_ui_prefs_pkey"),
        sa.UniqueConstraint(
            "wallet_user_id",
            "space",
            name="uq_wallet_space_ui_prefs_user_space",
        ),
    )
    op.create_index(
        "ix_wallet_space_ui_prefs_wallet_user_id",
        "wallet_space_ui_prefs",
        ["wallet_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_space_ui_prefs_space",
        "wallet_space_ui_prefs",
        ["space"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_space_ui_prefs_space", table_name="wallet_space_ui_prefs")
    op.drop_index(
        "ix_wallet_space_ui_prefs_wallet_user_id",
        table_name="wallet_space_ui_prefs",
    )
    op.drop_table("wallet_space_ui_prefs")
