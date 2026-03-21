"""exchange_services + exchange_service_fee_tiers

Revision ID: f7a8b9c0d1e2
Revises: d4e1f2a3b5c6
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "d4e1f2a3b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exchange_services",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Идентификатор конфигурации сервиса обмена",
        ),
        sa.Column(
            "service_type",
            sa.String(length=20),
            nullable=False,
            comment="Тип: on_ramp (фиат+залог стейблом), off_ramp (крипта→фиат)",
        ),
        sa.Column(
            "fiat_currency_code",
            sa.String(length=3),
            nullable=False,
            comment="Код фиатной валюты (ISO 4217)",
        ),
        sa.Column(
            "stablecoin_symbol",
            sa.String(length=32),
            nullable=False,
            comment="Символ стейблкоина (как CollateralStablecoinToken.symbol)",
        ),
        sa.Column(
            "network",
            sa.String(length=64),
            nullable=False,
            comment="Имя сети блокчейна",
        ),
        sa.Column(
            "contract_address",
            sa.String(length=128),
            nullable=False,
            comment="Адрес контракта токена",
        ),
        sa.Column(
            "stablecoin_base_currency",
            sa.String(length=3),
            nullable=True,
            comment="Базовая валюта привязки стейбла (USD, RUB, …), опционально",
        ),
        sa.Column(
            "rate_mode",
            sa.String(length=20),
            nullable=False,
            comment="Режим курса: manual, on_request, ratios",
        ),
        sa.Column(
            "manual_rate",
            sa.Numeric(precision=28, scale=12),
            nullable=True,
            comment="Ручной курс: фиат за 1 стейбл; для rate_mode=manual",
        ),
        sa.Column(
            "manual_rate_valid_until",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="До какого момента действует ручной курс; NULL = без срока",
        ),
        sa.Column(
            "ratios_engine_key",
            sa.String(length=255),
            nullable=True,
            comment="Ключ пары/источника в движке Ratios при rate_mode=ratios",
        ),
        sa.Column(
            "ratios_commission_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
            comment="Комиссия поверх котировки Ratios, %",
        ),
        sa.Column(
            "min_fiat_amount",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            comment="Минимальная сумма сделки в фиатной валюте",
        ),
        sa.Column(
            "max_fiat_amount",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            comment="Максимальная сумма сделки в фиатной валюте",
        ),
        sa.Column(
            "requisites_form_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="JSON Schema (и опц. ui_hints) формы запроса реквизитов",
        ),
        sa.Column(
            "verification_requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment="KYC/KYB: тип субъекта, список документов и т.п. (JSON)",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
            comment="Сервис доступен для выбора",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
            comment="Мягкое удаление",
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
        sa.PrimaryKeyConstraint("id", name="pk_exchange_services"),
        sa.CheckConstraint(
            "min_fiat_amount < max_fiat_amount",
            name="ck_exchange_services_fiat_amount_range",
        ),
        sa.CheckConstraint(
            "service_type IN ('on_ramp','off_ramp')",
            name="ck_exchange_services_service_type",
        ),
        sa.CheckConstraint(
            "rate_mode IN ('manual','on_request','ratios')",
            name="ck_exchange_services_rate_mode",
        ),
    )
    op.create_index(
        "ix_exchange_services_fiat_type_active",
        "exchange_services",
        ["fiat_currency_code", "service_type", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_exchange_services_id",
        "exchange_services",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_exchange_services_network_contract",
        "exchange_services",
        ["network", "contract_address"],
        unique=False,
    )
    op.create_index(
        "ix_exchange_services_rate_mode",
        "exchange_services",
        ["rate_mode"],
        unique=False,
    )
    op.create_index(
        "ix_exchange_services_service_type",
        "exchange_services",
        ["service_type"],
        unique=False,
    )
    op.create_index(
        "ix_exchange_services_fiat_currency_code",
        "exchange_services",
        ["fiat_currency_code"],
        unique=False,
    )
    op.create_index(
        "ix_exchange_services_requisites_schema",
        "exchange_services",
        ["requisites_form_schema"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_exchange_services_verification_req",
        "exchange_services",
        ["verification_requirements"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "exchange_service_fee_tiers",
        sa.Column(
            "id",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="Идентификатор строки сетки",
        ),
        sa.Column(
            "exchange_service_id",
            sa.BigInteger(),
            nullable=False,
            comment="Сервис обмена",
        ),
        sa.Column(
            "fiat_min",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            comment="Нижняя граница суммы в фиате (включительно)",
        ),
        sa.Column(
            "fiat_max",
            sa.Numeric(precision=20, scale=8),
            nullable=False,
            comment="Верхняя граница суммы в фиате (включительно или по правилу приложения)",
        ),
        sa.Column(
            "fee_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
            comment="Комиссия для диапазона, %",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Порядок отображения / разрешения при пересечениях (меньше — раньше)",
        ),
        sa.ForeignKeyConstraint(
            ["exchange_service_id"],
            ["exchange_services.id"],
            name="fk_exchange_fee_tiers_service_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exchange_service_fee_tiers"),
        sa.CheckConstraint(
            "fiat_min < fiat_max",
            name="ck_exchange_fee_tiers_fiat_range",
        ),
        sa.CheckConstraint(
            "fee_percent >= 0",
            name="ck_exchange_fee_tiers_fee_nonnegative",
        ),
    )
    op.create_index(
        "ix_exchange_fee_tiers_service_id",
        "exchange_service_fee_tiers",
        ["exchange_service_id"],
        unique=False,
    )
    op.create_index(
        "ix_exchange_service_fee_tiers_id",
        "exchange_service_fee_tiers",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_exchange_service_fee_tiers_id",
        table_name="exchange_service_fee_tiers",
    )
    op.drop_index(
        "ix_exchange_fee_tiers_service_id",
        table_name="exchange_service_fee_tiers",
    )
    op.drop_table("exchange_service_fee_tiers")

    op.drop_index(
        "ix_exchange_services_verification_req",
        table_name="exchange_services",
    )
    op.drop_index(
        "ix_exchange_services_requisites_schema",
        table_name="exchange_services",
    )
    op.drop_index(
        "ix_exchange_services_fiat_currency_code",
        table_name="exchange_services",
    )
    op.drop_index(
        "ix_exchange_services_service_type",
        table_name="exchange_services",
    )
    op.drop_index(
        "ix_exchange_services_rate_mode",
        table_name="exchange_services",
    )
    op.drop_index(
        "ix_exchange_services_network_contract",
        table_name="exchange_services",
    )
    op.drop_index(
        "ix_exchange_services_id",
        table_name="exchange_services",
    )
    op.drop_index(
        "ix_exchange_services_fiat_type_active",
        table_name="exchange_services",
    )
    op.drop_table("exchange_services")
