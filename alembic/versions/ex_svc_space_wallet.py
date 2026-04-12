"""exchange_services.space_wallet_id -> wallets (offRamp корп. кошелёк)

Revision ID: exsvcspwal01
Revises: exsvctitle01
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "exsvcspwal01"
down_revision: Union[str, None] = "exsvctitle01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "exchange_services",
        sa.Column(
            "space_wallet_id",
            sa.Integer(),
            nullable=True,
            comment="Корпоративный кошелёк спейса (wallets.id); обязателен для off_ramp",
        ),
    )
    op.create_index(
        "ix_exchange_services_space_wallet_id",
        "exchange_services",
        ["space_wallet_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_exchange_services_space_wallet_id_wallets",
        "exchange_services",
        "wallets",
        ["space_wallet_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_exchange_services_space_wallet_id_wallets",
        "exchange_services",
        type_="foreignkey",
    )
    op.drop_index("ix_exchange_services_space_wallet_id", table_name="exchange_services")
    op.drop_column("exchange_services", "space_wallet_id")
