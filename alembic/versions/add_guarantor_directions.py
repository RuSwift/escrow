"""guarantor_directions: направления гаранта по space

Revision ID: c0d1e2f3a4b5
Revises: a9b0c1d2e3f4
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guarantor_directions",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Идентификатор направления",
        ),
        sa.Column(
            "space",
            sa.String(length=255),
            nullable=False,
            comment="Идентификатор space (как в URL /{space}/…)",
        ),
        sa.Column(
            "currency_code",
            sa.String(length=64),
            nullable=False,
            comment="Код валюты (поле cur из bc.yaml / BestChange)",
        ),
        sa.Column(
            "payment_code",
            sa.String(length=128),
            nullable=False,
            comment="Код платёжного метода (payment_code в bc.yaml)",
        ),
        sa.Column(
            "payment_name",
            sa.String(length=512),
            nullable=True,
            comment="Локализованное имя метода на момент сохранения (подсказка для UI)",
        ),
        sa.Column(
            "conditions_text",
            sa.Text(),
            nullable=True,
            comment="Описание условий по направлению",
        ),
        sa.Column(
            "commission_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
            comment="Комиссия гаранта по направлению, %; NULL — использовать общую настройку",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Порядок отображения (меньше — выше)",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "space",
            "currency_code",
            "payment_code",
            name="uq_guarantor_directions_space_cur_pm",
        ),
    )
    op.create_index(
        "ix_guarantor_directions_space",
        "guarantor_directions",
        ["space"],
        unique=False,
    )
    op.create_index(
        "ix_guarantor_directions_space_sort",
        "guarantor_directions",
        ["space", "sort_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_guarantor_directions_space_sort", table_name="guarantor_directions")
    op.drop_index("ix_guarantor_directions_space", table_name="guarantor_directions")
    op.drop_table("guarantor_directions")
