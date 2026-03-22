"""dashboard_state: снимок котировок дашборда

Revision ID: a9b0c1d2e3f4
Revises: f7a8b9c0d1e2
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_state",
        sa.Column("id", sa.Integer(), nullable=False, comment="Фиксированный идентификатор: всегда 1"),
        sa.Column(
            "ratios",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Снимок котировок: dict[engine_label, list[{base, quote, pair}]]",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время последнего обновления строки",
        ),
        sa.PrimaryKeyConstraint("id", name="dashboard_state_pkey"),
    )
    op.execute(
        sa.text(
            "INSERT INTO dashboard_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_table("dashboard_state")
