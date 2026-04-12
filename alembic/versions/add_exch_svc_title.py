"""exchange_services.title: заголовок направления (обязательный)

Revision ID: exsvctitle01
Revises: wsuiprefs01
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "exsvctitle01"
down_revision: Union[str, None] = "wsuiprefs01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exchange_services",
        sa.Column(
            "title",
            sa.String(length=255),
            nullable=True,
            comment="Краткий заголовок направления для списков и карточек",
        ),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE exchange_services
            SET title = LEFT(
                COALESCE(
                    NULLIF(BTRIM(description), ''),
                    fiat_currency_code || ' · ' || stablecoin_symbol
                ),
                255
            )
            WHERE title IS NULL
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE exchange_services
            SET title = '?'
            WHERE title IS NULL OR BTRIM(title) = ''
            """
        )
    )
    op.alter_column(
        "exchange_services",
        "title",
        existing_type=sa.String(length=255),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("exchange_services", "title")
