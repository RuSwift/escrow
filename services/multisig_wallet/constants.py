"""Статусы и константы жизненного цикла Ramp multisig (TRON Account Permission)."""

from __future__ import annotations

MULTISIG_STATUS_PENDING_CONFIG = "pending_config"
MULTISIG_STATUS_AWAITING_FUNDING = "awaiting_funding"
MULTISIG_STATUS_READY_FOR_PERMISSIONS = "ready_for_permissions"
MULTISIG_STATUS_PERMISSIONS_SUBMITTED = "permissions_submitted"
MULTISIG_STATUS_ACTIVE = "active"
MULTISIG_STATUS_FAILED = "failed"

MULTISIG_DEFAULT_MIN_TRX_SUN = 150_000_000  # 150 TRX — запас под fee (как в garantex sample)

# Разрешённые операции для custom active permission (как в tests/samples/multisig garantex).
DEFAULT_ACTIVE_OPERATIONS_HEX = (
    "7fff1fc0033e0000000000000000000000000000000000000000000000000000"
)

TERMINAL_STATUSES = frozenset({MULTISIG_STATUS_ACTIVE})
