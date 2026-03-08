"""add_node_did

Revision ID: dc8e0c98cb6e
Revises: 80fff5fb203c
Create Date: 2026-03-09 02:02:04.109886

"""
import base64
import hashlib
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


revision: str = 'dc8e0c98cb6e'
down_revision: Union[str, None] = '80fff5fb203c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _decrypt(encrypted_b64: str, secret: str) -> str:
    """AES-GCM decrypt (same as BaseRepository.decrypt_data)."""
    key = hashlib.sha256(secret.encode('utf-8')).digest()
    data = json.loads(base64.b64decode(encrypted_b64).decode('utf-8'))
    iv = base64.b64decode(data["iv"])
    tag = base64.b64decode(data["tag"])
    ciphertext = base64.b64decode(data["ciphertext"])
    cipher = Cipher(
        algorithms.AES(key),
        modes.GCM(iv, tag),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    return plaintext.decode('utf-8')


def _compute_did_for_row(row, secret: str) -> str | None:
    """Compute Peer DID from stored key (mnemonic or PEM)."""
    try:
        from didcomm.crypto import EthKeyPair
        from didcomm.crypto import KeyPair as BaseKeyPair
        from didcomm.did import create_peer_did_from_keypair
    except ImportError:
        return None
    encrypted = row.encrypted_mnemonic if row.key_type == 'mnemonic' else row.encrypted_pem
    if not encrypted:
        return None
    try:
        plain = _decrypt(encrypted, secret)
    except Exception:
        return None
    try:
        if row.key_type == 'mnemonic':
            keypair = EthKeyPair.from_mnemonic(plain)
        else:
            keypair = BaseKeyPair.from_pem(plain)
        did_obj = create_peer_did_from_keypair(keypair)
        return did_obj.did
    except Exception:
        return None


def upgrade() -> None:
    op.add_column(
        'node_settings',
        sa.Column('did', sa.String(length=255), nullable=True, comment='Peer DID (did:peer:1:...)')
    )
    op.create_index(op.f('ix_node_settings_did'), 'node_settings', ['did'], unique=False)

    # Backfill: compute did for existing active rows using current algorithm
    conn = op.get_bind()
    try:
        from settings import Settings
        settings = Settings()
        secret = settings.secret.get_secret_value()
    except Exception:
        secret = None
    if secret:
        result = conn.execute(
            text("SELECT id, key_type, encrypted_mnemonic, encrypted_pem FROM node_settings WHERE is_active = true")
        )
        rows = result.fetchall()
        for row in rows:
            did_val = _compute_did_for_row(row, secret)
            if did_val:
                conn.execute(
                    text("UPDATE node_settings SET did = :did WHERE id = :id"),
                    {"did": did_val, "id": row.id}
                )


def downgrade() -> None:
    op.drop_index(op.f('ix_node_settings_did'), table_name='node_settings')
    op.drop_column('node_settings', 'did')
