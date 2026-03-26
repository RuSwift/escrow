"""wallet_users: DID спейсов -> did:web:escrow.ruswift.ru:{nickname}

Revision ID: didweb20260326
Revises: m5n6o7p8q9r0
Create Date: 2026-03-26
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "didweb20260326"
down_revision: Union[str, None] = "m5n6o7p8q9r0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Переопределяем DID только для DID, которые были построены по старой схеме:
    - did:tron:{nickname}
    - did:ethr:{nickname}

    Участников нод (did:peer:...) не трогаем.
    """
    conn = op.get_bind()

    # Сначала обновим wallets.owner_did, пока wallet_users.did еще в старом формате.
    conn.execute(
        text(
            """
            UPDATE wallets w
            SET owner_did = 'did:web:escrow.ruswift.ru:' || wu.nickname
            FROM wallet_users wu
            WHERE w.owner_did = wu.did
              AND wu.did ~ '^did:(tron|ethr):';
            """
        )
    )

    # Затем обновим wallet_users.did.
    conn.execute(
        text(
            """
            UPDATE wallet_users
            SET did = 'did:web:escrow.ruswift.ru:' || nickname
            WHERE did ~ '^did:(tron|ethr):';
            """
        )
    )


def downgrade() -> None:
    """
    Обратная миграция: did:web:escrow.ruswift.ru:{nickname} -> did:{blockchain}:{nickname}
    (для ethereum method возвращаем did:ethr:{nickname} как в get_user_did).
    """
    conn = op.get_bind()

    # wallets.owner_did -> старый формат
    conn.execute(
        text(
            """
            UPDATE wallets w
            SET owner_did =
                'did:' ||
                CASE
                    WHEN wu.blockchain = 'ethereum' THEN 'ethr'
                    ELSE wu.blockchain
                END ||
                ':' || wu.nickname
            FROM wallet_users wu
            WHERE w.owner_did = wu.did
              AND wu.did LIKE 'did:web:escrow.ruswift.ru:%';
            """
        )
    )

    # wallet_users.did -> старый формат
    conn.execute(
        text(
            """
            UPDATE wallet_users
            SET did =
                'did:' ||
                CASE
                    WHEN blockchain = 'ethereum' THEN 'ethr'
                    ELSE blockchain
                END ||
                ':' || nickname
            WHERE did LIKE 'did:web:escrow.ruswift.ru:%';
            """
        )
    )

