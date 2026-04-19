"""payment_request heading + expires_at

Revision ID: payreqhexp01
Revises: payreqsid01
Create Date: 2026-04-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "payreqhexp01"
down_revision: Union[str, None] = "payreqsid01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_request",
        sa.Column(
            "heading",
            sa.String(length=256),
            nullable=True,
            comment="Пользовательский заголовок заявки",
        ),
    )
    op.add_column(
        "payment_request",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Срок действия; NULL — без ограничения",
        ),
    )
    op.create_index(
        "ix_payment_request_expires_at",
        "payment_request",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_request_expires_at", table_name="payment_request")
    op.drop_column("payment_request", "expires_at")
    op.drop_column("payment_request", "heading")
