"""NotifyService: события Ramp / multisig и тексты."""

import pytest

from services.notify import NotifyService, RampNotifyEvent


def test_message_for_event_ru_wallet_created():
    t = NotifyService._message_for_event(
        RampNotifyEvent.RAMP_WALLET_CREATED,
        {"wallet_name": "W1", "wallet_id": 7, "role": "external", "tron_address": "TABC"},
        language="ru",
    )
    assert "W1" in t
    assert "external" in t
    assert "TABC" in t
    assert "7" in t


def test_message_for_event_ru_wallet_deleted():
    t = NotifyService._message_for_event(
        RampNotifyEvent.RAMP_WALLET_DELETED,
        {"wallet_name": "Del", "wallet_id": 42, "role": "multisig", "tron_address": "TX"},
        language="ru",
    )
    assert "Del" in t
    assert "multisig" in t
    assert "TX" in t
    assert "42" in t


def test_message_for_event_missing_keys_uses_dash():
    t = NotifyService._message_for_event(
        RampNotifyEvent.MULTISIG_CONFIGURED_ACTIVE,
        {"wallet_name": "M"},
        language="ru",
    )
    assert "M" in t
    assert "—" in t


def test_message_for_event_unknown_lang_falls_back_ru():
    t = NotifyService._message_for_event(
        RampNotifyEvent.RAMP_WALLET_CREATED,
        {"wallet_name": "X", "wallet_id": 1, "role": "multisig", "tron_address": ""},
        language="fr",
    )
    assert "корпоративный" in t.lower()


def test_message_for_event_en():
    t = NotifyService._message_for_event(
        RampNotifyEvent.MULTISIG_RECONFIGURED_NOOP,
        {"wallet_name": "Ms", "wallet_id": 3, "role": "multisig", "tron_address": "TX"},
        language="en",
    )
    assert "blockchain" in t.lower()


def test_message_for_event_unknown_event():
    t = NotifyService._message_for_event(
        "not_a_real_event", {"wallet_id": 99}, language="ru"
    )
    assert "not_a_real_event" in t
    assert "99" in t
