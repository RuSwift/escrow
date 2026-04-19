"""payment_request: заявки Simple до Deal

Revision ID: payreq01
Revises: exsvcspwal01
Create Date: 2026-04-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "payreq01"
down_revision: Union[str, None] = "exsvcspwal01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_request",
        sa.Column(
            "pk",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Autoincrement primary key",
        ),
        sa.Column(
            "uid",
            sa.String(length=255),
            nullable=False,
            comment="Публичный UUID заявки (hex)",
        ),
        sa.Column(
            "space",
            sa.String(length=255),
            nullable=False,
            comment="Space nickname",
        ),
        sa.Column(
            "owner_did",
            sa.String(length=255),
            nullable=False,
            comment="DID автора заявки",
        ),
        sa.Column(
            "direction",
            sa.String(length=32),
            nullable=False,
            comment="fiat_to_stable или stable_to_fiat",
        ),
        sa.Column(
            "primary_leg",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Нога отдачи (give)",
        ),
        sa.Column(
            "counter_leg",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Нога получения (receive)",
        ),
        sa.Column(
            "primary_ramp_wallet_id",
            sa.BigInteger(),
            nullable=True,
            comment="Primary ramp wallet для спейса при создании",
        ),
        sa.Column(
            "deal_id",
            sa.BigInteger(),
            nullable=True,
            comment="Связанная сделка после принятия контрагентом",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Creation timestamp (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last update timestamp (UTC)",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deal.pk"],
            name="payment_request_deal_id_fkey",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("pk", name="payment_request_pkey"),
        sa.UniqueConstraint("uid", name="uq_payment_request_uid"),
    )
    op.create_index(
        "ix_payment_request_owner_did",
        "payment_request",
        ["owner_did"],
        unique=False,
    )
    op.create_index(
        "ix_payment_request_space",
        "payment_request",
        ["space"],
        unique=False,
    )
    op.create_index(
        "ix_payment_request_primary_ramp_wallet_id",
        "payment_request",
        ["primary_ramp_wallet_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_request_deal_id",
        "payment_request",
        ["deal_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_request_primary_leg",
        "payment_request",
        ["primary_leg"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_payment_request_counter_leg",
        "payment_request",
        ["counter_leg"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_request_counter_leg",
        table_name="payment_request",
        postgresql_using="gin",
    )
    op.drop_index(
        "ix_payment_request_primary_leg",
        table_name="payment_request",
        postgresql_using="gin",
    )
    op.drop_index("ix_payment_request_deal_id", table_name="payment_request")
    op.drop_index(
        "ix_payment_request_primary_ramp_wallet_id",
        table_name="payment_request",
    )
    op.drop_index("ix_payment_request_space", table_name="payment_request")
    op.drop_index("ix_payment_request_owner_did", table_name="payment_request")
    op.drop_table("payment_request")
