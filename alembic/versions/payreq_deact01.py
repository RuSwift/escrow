"""payment_request deactivated_at

Revision ID: payreqdact01
Revises: payreqhexp01
Create Date: 2026-04-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "payreqdact01"
down_revision: Union[str, None] = "payreqhexp01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_request",
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Деактивация пользователем; NULL — активна",
        ),
    )


def downgrade() -> None:
    op.drop_column("payment_request", "deactivated_at")
