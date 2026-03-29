"""
Ожидаемая нумерация шага мастера Multisig в UI.

Должна совпадать с web/static/main/js/multisig_config_modal.js:
- multisigWizardDisplayStep
- multisigTronLinkPermissionSetupIncomplete (ветка TronLink до broadcast)
"""

import pytest


def multisig_wizard_display_step(
    *,
    status: str | None,
    meta: dict | None,
    wizard_ui_force_step_1: bool,
) -> int:
    """Копия логики Vue computed (без active-ветки для пустого wallet)."""
    if status is None:
        return 1
    if status == "active":
        return 3
    if wizard_ui_force_step_1:
        return 1
    m = meta or {}
    if (
        status == "ready_for_permissions"
        and bool(m.get("permission_sign_via_tronlink"))
        and not (str(m.get("permission_tx_id") or "").strip())
    ):
        return 2
    if status == "reconfigure":
        return 1
    if status == "awaiting_funding":
        return 2
    if status in (
        "ready_for_permissions",
        "permissions_submitted",
        "failed",
        "active",
    ):
        return 3
    return 1


@pytest.mark.parametrize(
    ("status", "meta", "force1", "want"),
    [
        ("reconfigure", {}, False, 1),
        ("awaiting_funding", {}, False, 2),
        ("ready_for_permissions", {}, False, 3),
        (
            "ready_for_permissions",
            {"permission_sign_via_tronlink": True},
            False,
            2,
        ),
        (
            "ready_for_permissions",
            {
                "permission_sign_via_tronlink": True,
                "permission_tx_id": "abc123",
            },
            False,
            3,
        ),
        (
            "ready_for_permissions",
            {"permission_sign_via_tronlink": True, "permission_tx_id": "  "},
            False,
            2,
        ),
        ("permissions_submitted", {}, False, 3),
        ("failed", {}, False, 3),
        ("pending_config", {}, False, 1),
        ("ready_for_permissions", {}, True, 1),
    ],
)
def test_wizard_display_step_tronlink_stays_on_step2(
    status: str,
    meta: dict,
    force1: bool,
    want: int,
) -> None:
    assert multisig_wizard_display_step(
        status=status,
        meta=meta,
        wizard_ui_force_step_1=force1,
    ) == want
