"""Валидация multisig_setup_meta (actors / thresholds)."""

import pytest

from services.multisig_wallet.meta import validate_actors_threshold

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
