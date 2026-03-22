"""guarantor_profiles: условия гаранта 1:1 (wallet_user, space)

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guarantor_profiles",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Идентификатор профиля гаранта",
        ),
        sa.Column(
            "wallet_user_id",
            sa.Integer(),
            nullable=False,
            comment="Владелец настроек гаранта в данном space",
        ),
        sa.Column(
            "space",
            sa.String(length=255),
            nullable=False,
            comment="Идентификатор space (как в URL /{space}/…)",
        ),
        sa.Column(
            "commission_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
            comment="Базовая комиссия гаранта для панели, %",
        ),
        sa.Column(
            "conditions_text",
            sa.Text(),
            nullable=True,
            comment="Общие условия работы гаранта в этом space",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Создано (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Обновлено (UTC)",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_user_id"],
            ["wallet_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "wallet_user_id",
            "space",
            name="uq_guarantor_profiles_wallet_space",
        ),
    )
    op.create_index(
        "ix_guarantor_profiles_wallet_user_id",
        "guarantor_profiles",
        ["wallet_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_guarantor_profiles_space",
        "guarantor_profiles",
        ["space"],
        unique=False,
    )
    op.create_index(
        "ix_guarantor_profiles_wallet_space",
        "guarantor_profiles",
        ["wallet_user_id", "space"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_guarantor_profiles_wallet_space", table_name="guarantor_profiles")
    op.drop_index("ix_guarantor_profiles_space", table_name="guarantor_profiles")
    op.drop_index("ix_guarantor_profiles_wallet_user_id", table_name="guarantor_profiles")
    op.drop_table("guarantor_profiles")
