"""add primary_wallets table

Revision ID: 0ee60a74395c
Revises: ordwdsig2026
Create Date: 2026-04-05 23:30:12.098578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ee60a74395c'
down_revision: Union[str, None] = 'ordwdsig2026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'primary_wallets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('wallet_user_id', sa.Integer(), nullable=False, comment='Reference to owner WalletUser'),
        sa.Column('address', sa.String(length=255), nullable=False, comment='Primary wallet address'),
        sa.Column('blockchain', sa.String(length=20), nullable=False, comment='Blockchain type: tron, ethereum, etc.'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['wallet_user_id'], ['wallet_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('wallet_user_id')
    )
    op.create_index(op.f('ix_primary_wallets_blockchain'), 'primary_wallets', ['blockchain'], unique=False)
    op.create_index(op.f('ix_primary_wallets_id'), 'primary_wallets', ['id'], unique=False)
    op.create_index(op.f('ix_primary_wallets_wallet_user_id'), 'primary_wallets', ['wallet_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_primary_wallets_wallet_user_id'), table_name='primary_wallets')
    op.drop_index(op.f('ix_primary_wallets_id'), table_name='primary_wallets')
    op.drop_index(op.f('ix_primary_wallets_blockchain'), table_name='primary_wallets')
    op.drop_table('primary_wallets')
