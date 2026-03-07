"""
Тесты WalletUserResource (схемы Create, Patch, Get) и _model_to_get.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from db.models import WalletUser
from repos.wallet_user import (
    WalletUserResource,
    _model_to_get,
)


# --- WalletUserResource.Create ---


def test_create_minimal_required_fields():
    """Create принимает только обязательные поля."""
    data = WalletUserResource.Create(
        wallet_address="TXyz123456789012345678901234567890AB",
        blockchain="tron",
        nickname="alice",
    )
    assert data.wallet_address == "TXyz123456789012345678901234567890AB"
    assert data.blockchain == "tron"
    assert data.nickname == "alice"
    assert data.avatar is None
    assert data.access_to_admin_panel is False
    assert data.is_verified is False


def test_create_with_all_fields():
    """Create принимает все поля с явными значениями."""
    data = WalletUserResource.Create(
        wallet_address="0x1234567890123456789012345678901234567890",
        blockchain="ethereum",
        nickname="bob",
        avatar="data:image/png;base64,abc",
        access_to_admin_panel=True,
        is_verified=True,
    )
    assert data.avatar == "data:image/png;base64,abc"
    assert data.access_to_admin_panel is True
    assert data.is_verified is True


def test_create_missing_required_raises():
    """Create без обязательного поля поднимает ValidationError."""
    with pytest.raises(ValidationError):
        WalletUserResource.Create(
            wallet_address="TXyz123456789012345678901234567890AB",
            blockchain="tron",
            # nickname missing
        )


def test_create_wallet_address_max_length():
    """Create допускает wallet_address длиной до 255 символов."""
    long_addr = "x" * 255
    data = WalletUserResource.Create(
        wallet_address=long_addr,
        blockchain="tron",
        nickname="u",
    )
    assert len(data.wallet_address) == 255


def test_create_wallet_address_too_long_raises():
    """Create с wallet_address длиннее 255 поднимает ValidationError."""
    with pytest.raises(ValidationError):
        WalletUserResource.Create(
            wallet_address="x" * 256,
            blockchain="tron",
            nickname="u",
        )


def test_create_blockchain_max_length():
    """Create допускает blockchain длиной до 20 символов."""
    data = WalletUserResource.Create(
        wallet_address="TXyz123456789012345678901234567890AB",
        blockchain="a" * 20,
        nickname="u",
    )
    assert len(data.blockchain) == 20


def test_create_blockchain_too_long_raises():
    """Create с blockchain длиннее 20 поднимает ValidationError."""
    with pytest.raises(ValidationError):
        WalletUserResource.Create(
            wallet_address="TXyz123456789012345678901234567890AB",
            blockchain="a" * 21,
            nickname="u",
        )


def test_create_nickname_max_length():
    """Create допускает nickname длиной до 100 символов."""
    data = WalletUserResource.Create(
        wallet_address="TXyz123456789012345678901234567890AB",
        blockchain="tron",
        nickname="n" * 100,
    )
    assert len(data.nickname) == 100


def test_create_nickname_too_long_raises():
    """Create с nickname длиннее 100 поднимает ValidationError."""
    with pytest.raises(ValidationError):
        WalletUserResource.Create(
            wallet_address="TXyz123456789012345678901234567890AB",
            blockchain="tron",
            nickname="n" * 101,
        )


def test_create_extra_ignored():
    """Create игнорирует лишние поля (extra='ignore')."""
    data = WalletUserResource.Create(
        wallet_address="TXyz123456789012345678901234567890AB",
        blockchain="tron",
        nickname="u",
        unknown_field="ignored",
    )
    assert not hasattr(data, "unknown_field")
    assert "unknown_field" not in data.model_dump()


# --- WalletUserResource.Patch ---


def test_patch_all_optional():
    """Patch допускает пустой набор полей."""
    data = WalletUserResource.Patch()
    assert data.model_dump(exclude_unset=True) == {}


def test_patch_partial_fields():
    """Patch сохраняет только переданные поля (exclude_unset)."""
    data = WalletUserResource.Patch(nickname="new_nick", is_verified=True)
    dumped = data.model_dump(exclude_unset=True)
    assert dumped == {"nickname": "new_nick", "is_verified": True}
    assert "avatar" not in dumped
    assert "balance_usdt" not in dumped


def test_patch_nickname_max_length():
    """Patch допускает nickname до 100 символов."""
    data = WalletUserResource.Patch(nickname="n" * 100)
    assert len(data.nickname) == 100


def test_patch_balance_usdt():
    """Patch принимает balance_usdt как Decimal."""
    data = WalletUserResource.Patch(balance_usdt=Decimal("123.45"))
    assert data.balance_usdt == Decimal("123.45")


def test_patch_avatar_clear():
    """Patch позволяет передать avatar=None."""
    data = WalletUserResource.Patch(avatar=None)
    dumped = data.model_dump(exclude_unset=True)
    assert "avatar" in dumped
    assert dumped["avatar"] is None


# --- WalletUserResource.Get ---


def test_get_construction():
    """Get собирается из всех обязательных полей."""
    now = datetime.now(timezone.utc)
    data = WalletUserResource.Get(
        id=1,
        wallet_address="TXyz123456789012345678901234567890AB",
        blockchain="tron",
        did="did:ruswift:tron:TXyz123",
        nickname="alice",
        avatar=None,
        access_to_admin_panel=False,
        is_verified=False,
        balance_usdt=Decimal("0"),
        created_at=now,
        updated_at=now,
    )
    assert data.id == 1
    assert data.wallet_address == "TXyz123456789012345678901234567890AB"
    assert data.did == "did:ruswift:tron:TXyz123"
    assert data.balance_usdt == Decimal("0")
    assert data.created_at == now
    assert data.updated_at == now


def test_get_avatar_optional():
    """Get допускает avatar как None или строку."""
    now = datetime.now(timezone.utc)
    r1 = WalletUserResource.Get(
        id=1,
        wallet_address="a",
        blockchain="tron",
        did="did:x",
        nickname="n",
        avatar=None,
        access_to_admin_panel=False,
        is_verified=False,
        balance_usdt=Decimal("0"),
        created_at=now,
        updated_at=now,
    )
    assert r1.avatar is None
    r2 = WalletUserResource.Get(
        id=2,
        wallet_address="b",
        blockchain="tron",
        did="did:y",
        nickname="m",
        avatar="data:image/png;base64,xyz",
        access_to_admin_panel=False,
        is_verified=False,
        balance_usdt=Decimal("0"),
        created_at=now,
        updated_at=now,
    )
    assert r2.avatar == "data:image/png;base64,xyz"


# --- _model_to_get ---


def test_model_to_get():
    """_model_to_get преобразует WalletUser в WalletUserResource.Get."""
    now = datetime.now(timezone.utc)
    model = WalletUser(
        id=42,
        wallet_address="TXyz123456789012345678901234567890AB",
        blockchain="tron",
        did="did:ruswift:tron:TXyz123",
        nickname="alice",
        avatar="data:image/png;base64,a",
        access_to_admin_panel=True,
        is_verified=True,
        balance_usdt=Decimal("100.5"),
        created_at=now,
        updated_at=now,
    )
    got = _model_to_get(model)
    assert isinstance(got, WalletUserResource.Get)
    assert got.id == 42
    assert got.wallet_address == model.wallet_address
    assert got.blockchain == model.blockchain
    assert got.did == model.did
    assert got.nickname == model.nickname
    assert got.avatar == model.avatar
    assert got.access_to_admin_panel is True
    assert got.is_verified is True
    assert got.balance_usdt == Decimal("100.5")
    assert got.created_at == now
    assert got.updated_at == now


def test_model_to_get_avatar_none():
    """_model_to_get корректно передаёт avatar=None."""
    now = datetime.now(timezone.utc)
    model = WalletUser(
        id=1,
        wallet_address="a",
        blockchain="tron",
        did="did:x",
        nickname="n",
        avatar=None,
        access_to_admin_panel=False,
        is_verified=False,
        balance_usdt=Decimal("0"),
        created_at=now,
        updated_at=now,
    )
    got = _model_to_get(model)
    assert got.avatar is None
