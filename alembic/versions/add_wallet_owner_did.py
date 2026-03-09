"""add wallet owner_did

Revision ID: a1b2c3d4e5f6
Revises: dc8e0c98cb6e
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'dc8e0c98cb6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'wallets',
        sa.Column('owner_did', sa.String(length=255), nullable=True, comment='Owner node DID (did:peer:1:...)'),
    )
    op.create_index('ix_wallets_owner_did', 'wallets', ['owner_did'], unique=False)

    # Backfill: set owner_did from active NodeSettings.did
    conn = op.get_bind()
    conn.execute(
        text("""
            UPDATE wallets
            SET owner_did = (SELECT did FROM node_settings WHERE is_active = true LIMIT 1)
            WHERE owner_did IS NULL
        """)
    )

    # Replace unique constraints to include owner_did
    op.drop_constraint('uq_wallets_tron_address_role', 'wallets', type_='unique')
    op.drop_constraint('uq_wallets_ethereum_address_role', 'wallets', type_='unique')
    op.create_unique_constraint(
        'uq_wallets_tron_address_role',
        'wallets',
        ['tron_address', 'role', 'owner_did'],
    )
    op.create_unique_constraint(
        'uq_wallets_ethereum_address_role',
        'wallets',
        ['ethereum_address', 'role', 'owner_did'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_wallets_tron_address_role', 'wallets', type_='unique')
    op.drop_constraint('uq_wallets_ethereum_address_role', 'wallets', type_='unique')
    op.create_unique_constraint(
        'uq_wallets_tron_address_role',
        'wallets',
        ['tron_address', 'role'],
    )
    op.create_unique_constraint(
        'uq_wallets_ethereum_address_role',
        'wallets',
        ['ethereum_address', 'role'],
    )
    op.drop_index('ix_wallets_owner_did', table_name='wallets')
    op.drop_column('wallets', 'owner_did')
