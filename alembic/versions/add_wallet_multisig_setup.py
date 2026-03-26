"""wallets: multisig_setup_status + meta

Revision ID: m5n6o7p8q9r0
Revises: h2j3k4l5m6n7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "m5n6o7p8q9r0"
down_revision: Union[str, None] = "h2j3k4l5m6n7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallets",
        sa.Column(
            "multisig_setup_status",
            sa.String(length=32),
            nullable=True,
            comment="Multisig setup lifecycle; NULL = legacy wallet = active",
        ),
    )
    op.add_column(
        "wallets",
        sa.Column(
            "multisig_setup_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Multisig setup progress JSON (actors, thresholds, errors)",
        ),
    )


def downgrade() -> None:
    op.drop_column("wallets", "multisig_setup_meta")
    op.drop_column("wallets", "multisig_setup_status")
