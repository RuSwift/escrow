"""add bestchange_yaml_snapshots (bc.yaml hash + exported_at)

Revision ID: c3d0e1f2a4b5
Revises: b8c9d0e1f2a3
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d0e1f2a4b5"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bestchange_yaml_snapshots",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Идентификатор записи",
        ),
        sa.Column(
            "file_hash",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 (hex) содержимого файла bc.yaml",
        ),
        sa.Column(
            "exported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="meta.exported_at из YAML (момент выгрузки из BestChange)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Время сохранения записи в БД (UTC)",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_hash", name="uq_bestchange_yaml_snapshots_file_hash"),
    )


def downgrade() -> None:
    op.drop_table("bestchange_yaml_snapshots")
