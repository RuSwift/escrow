"""bestchange_yaml_snapshots.payload JSONB

Revision ID: d4e1f2a3b5c6
Revises: c3d0e1f2a4b5
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e1f2a3b5c6"
down_revision: Union[str, None] = "c3d0e1f2a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bestchange_yaml_snapshots",
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Содержимое bc.yaml, распарсенное в JSON (meta, payment_methods, cities, …)",
        ),
    )


def downgrade() -> None:
    op.drop_column("bestchange_yaml_snapshots", "payload")
