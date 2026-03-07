"""
Тесты TronAuth: validate_tron_address, get_nonce, verify_signature, JWT.
"""
import pytest

from services.tron_auth import TronAuth

# Валидный base58 TRON-адрес (34 символа, T + base58)
WALLET_TRON = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


@pytest.fixture
def tron_auth(test_redis, test_settings) -> TronAuth:
    return TronAuth(redis=test_redis, settings=test_settings)


# --- validate_tron_address ---


def test_validate_tron_address_valid(tron_auth):
    """Валидный формат T + 34 base58 проходит."""
    assert tron_auth.validate_tron_address(WALLET_TRON) is True


def test_validate_tron_address_static():
    """Метод статический, можно вызывать без экземпляра."""
    assert TronAuth.validate_tron_address(WALLET_TRON) is True


def test_validate_tron_address_invalid(tron_auth):
    """Не T, не 34 символа или не base58 — False."""
    assert tron_auth.validate_tron_address("") is False
    assert tron_auth.validate_tron_address("0x1234567890123456789012345678901234567890") is False
    assert tron_auth.validate_tron_address("T" + "0" * 33) is False  # base58 не содержит '0'
    assert tron_auth.validate_tron_address("T123") is False  # слишком короткий


def test_validate_tron_address_strips_whitespace(tron_auth):
    """Пробелы по краям обрезаются."""
    assert tron_auth.validate_tron_address(f"  {WALLET_TRON}  ") is True


# --- get_nonce ---


@pytest.mark.asyncio
async def test_tron_get_nonce_returns_hex(tron_auth):
    """get_nonce возвращает hex и сохраняет в Redis."""
    nonce = await tron_auth.get_nonce(WALLET_TRON)
    assert isinstance(nonce, str)
    assert len(nonce) == 32
    key = f"auth:nonce:tron:{WALLET_TRON}"
    stored = await tron_auth._redis.get(key)
    assert stored == nonce


@pytest.mark.asyncio
async def test_tron_get_nonce_different_each_time(tron_auth):
    """Каждый вызов даёт новый nonce."""
    n1 = await tron_auth.get_nonce(WALLET_TRON)
    n2 = await tron_auth.get_nonce(WALLET_TRON)
    assert n1 != n2


# --- verify_signature (если tronpy доступен) ---


def test_tron_verify_signature_empty_message_returns_false(tron_auth):
    """Пустое сообщение — False."""
    sig_hex = "0" * 130
    assert tron_auth.verify_signature(WALLET_TRON, sig_hex, "") is False
    assert tron_auth.verify_signature(WALLET_TRON, sig_hex, None) is False


def test_tron_verify_signature_invalid_hex_returns_false(tron_auth):
    """Невалидная подпись — False (или исключение внутри, результат False)."""
    assert tron_auth.verify_signature(WALLET_TRON, "zz", "msg") is False


# --- JWT ---


def test_tron_generate_jwt_token(tron_auth):
    """generate_jwt_token возвращает токен, verify — payload с blockchain=tron."""
    token = tron_auth.generate_jwt_token(WALLET_TRON)
    assert isinstance(token, str)
    payload = tron_auth.verify_jwt_token(token)
    assert payload is not None
    assert payload.get("wallet_address") == WALLET_TRON
    assert payload.get("blockchain") == "tron"
    assert "exp" in payload


def test_tron_verify_jwt_token_invalid_returns_none(tron_auth):
    """Невалидный токен — None."""
    assert tron_auth.verify_jwt_token("invalid") is None
