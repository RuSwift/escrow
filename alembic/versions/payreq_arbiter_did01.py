"""payment_request.arbiter_did (Simple context)

Revision ID: payreqarb01
Revises: payreqpref01
Create Date: 2026-04-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "payreqarb01"
down_revision: Union[str, None] = "payreqpref01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Sentinel for any pre-migration rows without arbiter context (should be rare).
_LEGACY_ARBITER_DID = "did:escrow:legacy-migration-unset"


def upgrade() -> None:
    op.add_column(
        "payment_request",
        sa.Column("arbiter_did", sa.String(length=255), nullable=True),
    )
    op.execute(
        text(
            "UPDATE payment_request SET arbiter_did = :d WHERE arbiter_did IS NULL"
        ).bindparams(d=_LEGACY_ARBITER_DID)
    )
    op.alter_column(
        "payment_request",
        "arbiter_did",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.create_index(
        "ix_payment_request_arbiter_did",
        "payment_request",
        ["arbiter_did"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_request_arbiter_did", table_name="payment_request")
    op.drop_column("payment_request", "arbiter_did")
