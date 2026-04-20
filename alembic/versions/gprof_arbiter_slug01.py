"""guarantor_profiles.arbiter_public_slug (уникальный путь /arbiter/{slug})

Revision ID: gprofslug01
Revises: payreqarb01
Create Date: 2026-04-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "gprofslug01"
down_revision: Union[str, None] = "payreqarb01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guarantor_profiles",
        sa.Column(
            "arbiter_public_slug",
            sa.String(length=64),
            nullable=True,
            comment="Уникальный сегмент URL /arbiter/{slug} вместо DID",
        ),
    )
    op.create_index(
        "ix_guarantor_profiles_arbiter_public_slug",
        "guarantor_profiles",
        ["arbiter_public_slug"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_guarantor_profiles_arbiter_public_slug",
        table_name="guarantor_profiles",
    )
    op.drop_column("guarantor_profiles", "arbiter_public_slug")
