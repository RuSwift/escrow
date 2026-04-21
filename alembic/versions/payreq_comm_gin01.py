"""payment_request commissioners GIN index

Revision ID: payreqcgin01
Revises: gprofslug01
Create Date: 2026-04-21

"""

from typing import Sequence, Union

from alembic import op


revision: str = "payreqcgin01"
down_revision: Union[str, None] = "gprofslug01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_payment_request_commissioners_gin "
        "ON payment_request USING gin (commissioners)"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_request_commissioners_gin",
        table_name="payment_request",
    )
