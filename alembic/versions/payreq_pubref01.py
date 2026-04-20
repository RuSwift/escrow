"""payment_request public_ref + commissioners

Revision ID: payreqpref01
Revises: payreqdact01
Create Date: 2026-04-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from core.short_id import generate_public_ref

revision: str = "payreqpref01"
down_revision: Union[str, None] = "payreqdact01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_request",
        sa.Column(
            "public_ref",
            sa.String(length=10),
            nullable=True,
            comment="Короткий публичный код заявки (список/ссылки)",
        ),
    )
    op.add_column(
        "payment_request",
        sa.Column(
            "commissioners",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Карта слотов комиссионеров (JSON)",
        ),
    )

    conn = op.get_bind()
    conn.execute(
        text("UPDATE payment_request SET commissioners = '{}'::jsonb WHERE commissioners IS NULL")
    )

    rows = conn.execute(text("SELECT pk FROM payment_request ORDER BY pk")).fetchall()
    used: set[str] = set()
    for (pk,) in rows:
        while True:
            ref = generate_public_ref()
            if ref in used:
                continue
            row = conn.execute(
                text("SELECT 1 FROM payment_request WHERE public_ref = :r LIMIT 1"),
                {"r": ref},
            ).first()
            if row is not None:
                continue
            used.add(ref)
            conn.execute(
                text("UPDATE payment_request SET public_ref = :r WHERE pk = :pk"),
                {"r": ref, "pk": pk},
            )
            break

    op.alter_column(
        "payment_request",
        "public_ref",
        existing_type=sa.String(length=10),
        nullable=False,
    )
    op.alter_column(
        "payment_request",
        "commissioners",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )
    op.create_index(
        "uq_payment_request_public_ref",
        "payment_request",
        ["public_ref"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_payment_request_public_ref", table_name="payment_request")
    op.drop_column("payment_request", "commissioners")
    op.drop_column("payment_request", "public_ref")
