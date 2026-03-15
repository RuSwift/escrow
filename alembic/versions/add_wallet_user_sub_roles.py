"""add wallet_user_subs.roles

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallet_user_subs",
        sa.Column(
            "roles",
            sa.dialects.postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Set of roles: owner, operator, reader",
        ),
    )
    op.create_check_constraint(
        "ck_wallet_user_subs_roles_allowed",
        "wallet_user_subs",
        "roles <@ ARRAY['owner','operator','reader']::text[]",
    )


def downgrade() -> None:
    op.drop_constraint("ck_wallet_user_subs_roles_allowed", "wallet_user_subs", type_="check")
    op.drop_column("wallet_user_subs", "roles")
