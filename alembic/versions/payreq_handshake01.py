"""payment_request handshake columns (counterparty accept / owner confirm)

Revision ID: payreq_handshake01
Revises: payreqcgin01
Create Date: 2026-04-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "payreq_handshake01"
down_revision: Union[str, None] = "payreqcgin01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_request",
        sa.Column(
            "counterparty_accept_did",
            sa.String(255),
            nullable=True,
            comment="DID контрагента, принявшего заявку (до Deal)",
        ),
    )
    op.add_column(
        "payment_request",
        sa.Column(
            "counterparty_accept_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Время принятия контрагентом",
        ),
    )
    op.add_column(
        "payment_request",
        sa.Column(
            "owner_confirm_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Ожидается подтверждение владельца после accept контрагента",
        ),
    )
    op.add_column(
        "payment_request",
        sa.Column(
            "owner_confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Время подтверждения владельцем / создания Deal",
        ),
    )
    op.add_column(
        "payment_request",
        sa.Column(
            "counter_leg_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Снимок counter_leg до accept (откат при withdraw при обсуждаемой сумме)",
        ),
    )
    op.create_index(
        "ix_payment_request_counterparty_accept_did",
        "payment_request",
        ["counterparty_accept_did"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_request_counterparty_accept_did",
        table_name="payment_request",
    )
    op.drop_column("payment_request", "counter_leg_snapshot_json")
    op.drop_column("payment_request", "owner_confirmed_at")
    op.drop_column("payment_request", "owner_confirm_pending")
    op.drop_column("payment_request", "counterparty_accept_at")
    op.drop_column("payment_request", "counterparty_accept_did")
