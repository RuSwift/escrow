import pytest

from core.guarantor_slug import normalize_arbiter_public_slug


def test_normalize_arbiter_public_slug_ok():
    assert normalize_arbiter_public_slug("My-Nick") == "my-nick"
    assert normalize_arbiter_public_slug("abc") == "abc"


def test_normalize_arbiter_public_slug_clear():
    assert normalize_arbiter_public_slug(None) is None
    assert normalize_arbiter_public_slug("") is None
    assert normalize_arbiter_public_slug("   ") is None


@pytest.mark.parametrize(
    "raw",
    ["ab", "a" * 33, "bad_", "_bad", "bad space", "x_"],
)
def test_normalize_arbiter_public_slug_invalid(raw: str):
    with pytest.raises(ValueError):
        normalize_arbiter_public_slug(raw)
