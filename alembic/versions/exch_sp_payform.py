"""exchange_services.space + space_payment_form_overrides

Revision ID: exspform2026
Revises: 0ee60a74395c
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "exspform2026"
down_revision: Union[str, None] = "0ee60a74395c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        "ix_exchange_services_fiat_type_active",
        table_name="exchange_services",
    )
    op.add_column(
        "exchange_services",
        sa.Column("space", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "exchange_services",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "exchange_services",
        sa.Column("payment_code", sa.String(length=128), nullable=True),
    )
    op.execute(
        "UPDATE exchange_services SET space = '_legacy_' WHERE space IS NULL"
    )
    op.alter_column(
        "exchange_services",
        "space",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.create_index(
        "ix_exch_svc_space_fiat_type_act",
        "exchange_services",
        ["space", "fiat_currency_code", "service_type", "is_active"],
        unique=False,
    )

    op.create_table(
        "space_payment_form_overrides",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Идентификатор переопределения формы",
        ),
        sa.Column(
            "space",
            sa.String(length=255),
            nullable=False,
            comment="Идентификатор space (как в URL /{space}/…)",
        ),
        sa.Column(
            "payment_code",
            sa.String(length=128),
            nullable=False,
            comment="Код платёжного метода (payment_code в bc.yaml)",
        ),
        sa.Column(
            "form",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Объект формы: { fields: [...] } как PaymentForm",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Создано (UTC)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Обновлено (UTC)",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_space_payment_form_overrides"),
        sa.UniqueConstraint(
            "space",
            "payment_code",
            name="uq_space_payment_form_space_code",
        ),
    )
    op.create_index(
        "ix_spayform_space",
        "space_payment_form_overrides",
        ["space"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_spayform_space", table_name="space_payment_form_overrides")
    op.drop_table("space_payment_form_overrides")
    op.drop_index("ix_exch_svc_space_fiat_type_act", table_name="exchange_services")
    op.drop_column("exchange_services", "payment_code")
    op.drop_column("exchange_services", "description")
    op.drop_column("exchange_services", "space")
    op.create_index(
        "ix_exchange_services_fiat_type_active",
        "exchange_services",
        ["fiat_currency_code", "service_type", "is_active"],
        unique=False,
    )
