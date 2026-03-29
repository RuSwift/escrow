"""Валидация multisig_setup_meta (actors / thresholds)."""

import pytest

from services.multisig_wallet.meta import validate_actors_threshold, validate_owners_list

_MAIN = "TUEZSdKsoDHQMeZwihtdoBiN46zxhGWYdH"
_SIGNER = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"


def test_validate_actors_rejects_wallet_address_in_actors():
    with pytest.raises(ValueError, match="must not be listed"):
        validate_actors_threshold(
            [_SIGNER, _MAIN],
            1,
            2,
            main_tron_address=_MAIN,
        )


def test_validate_actors_ok_signers_only():
    validate_actors_threshold(
        [_SIGNER],
        1,
        1,
        main_tron_address=_MAIN,
    )


def test_validate_owners_list_ok():
    out = validate_owners_list([_SIGNER, _MAIN])
    assert len(out) == 2


def test_validate_owners_list_rejects_duplicate():
    with pytest.raises(ValueError, match="Duplicate"):
        validate_owners_list([_SIGNER, _SIGNER])
