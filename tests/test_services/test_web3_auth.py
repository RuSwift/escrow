"""
Тесты Web3Auth: nonce, verify_signature, JWT.
"""
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from services.web3_auth import Web3Auth


@pytest.fixture
def web3_auth(test_redis, test_settings) -> Web3Auth:
    return Web3Auth(redis=test_redis, settings=test_settings)


WALLET_ETH = "0x1234567890123456789012345678901234567890"


# --- get_nonce ---


@pytest.mark.asyncio
async def test_get_nonce_returns_hex_string(web3_auth):
    """get_nonce возвращает hex-строку и сохраняет в Redis."""
    nonce = await web3_auth.get_nonce(WALLET_ETH)
    assert isinstance(nonce, str)
    assert len(nonce) == 32  # 16 bytes hex
    assert all(c in "0123456789abcdef" for c in nonce)
    # Проверяем, что в Redis лежит тот же nonce
    key = f"auth:nonce:eth:{WALLET_ETH.lower()}"
    stored = await web3_auth._redis.get(key)
    assert stored == nonce


@pytest.mark.asyncio
async def test_get_nonce_different_each_time(web3_auth):
    """Каждый вызов get_nonce даёт новый nonce."""
    n1 = await web3_auth.get_nonce(WALLET_ETH)
    n2 = await web3_auth.get_nonce(WALLET_ETH)
    assert n1 != n2


# --- verify_signature ---


def _eth_sign_message(message: str, private_key_hex: str) -> str:
    """Подписать сообщение (EIP-191) и вернуть hex подписи."""
    account = Account.from_key(private_key_hex)
    message_hash = encode_defunct(text=message)
    signed = account.sign_message(message_hash)
    return signed.signature.hex()


@pytest.fixture
def eth_private_key():
    """Тестовый приватный ключ (32 bytes hex)."""
    return "0x" + "1" * 64


@pytest.fixture
def eth_account(eth_private_key):
    """Account с тестовым ключом."""
    return Account.from_key(eth_private_key)


def test_verify_signature_valid(web3_auth, eth_private_key, eth_account):
    """Валидная подпись от известного адреса проходит проверку."""
    message = "Please sign this message to authenticate:\n\nNonce: abc123"
    signature = _eth_sign_message(message, eth_private_key)
    wallet = eth_account.address
    assert web3_auth.verify_signature(wallet, signature, message) is True
    assert web3_auth.verify_signature(wallet.upper(), signature, message) is True


def test_verify_signature_wrong_message(web3_auth, eth_private_key, eth_account):
    """Подпись от другого сообщения не проходит."""
    message = "Hello"
    signature = _eth_sign_message(message, eth_private_key)
    other_message = "Other message"
    assert web3_auth.verify_signature(eth_account.address, signature, other_message) is False


def test_verify_signature_wrong_address(web3_auth, eth_private_key):
    """Подпись, восстановленный адрес которой не совпадает с переданным, не проходит."""
    message = "Hello"
    signature = _eth_sign_message(message, eth_private_key)
    assert web3_auth.verify_signature(WALLET_ETH, signature, message) is False


def test_verify_signature_empty_inputs(web3_auth):
    """Пустой адрес или подпись — False."""
    assert web3_auth.verify_signature("", "0x" + "00" * 65, "msg") is False
    assert web3_auth.verify_signature(WALLET_ETH, "", "msg") is False


def test_verify_signature_invalid_hex(web3_auth):
    """Невалидная hex-подпись — False."""
    assert web3_auth.verify_signature(WALLET_ETH, "not-hex", "msg") is False


def test_verify_signature_wrong_length(web3_auth):
    """Подпись не 65 байт — False."""
    assert web3_auth.verify_signature(WALLET_ETH, "00" * 32, "msg") is False


# --- JWT ---


def test_generate_jwt_token(web3_auth):
    """generate_jwt_token возвращает строку, verify_jwt_token возвращает payload."""
    token = web3_auth.generate_jwt_token(WALLET_ETH)
    assert isinstance(token, str)
    payload = web3_auth.verify_jwt_token(token)
    assert payload is not None
    assert payload.get("wallet_address") == WALLET_ETH.lower()
    assert payload.get("blockchain") == "ethereum"
    assert "exp" in payload


def test_verify_jwt_token_invalid_returns_none(web3_auth):
    """Невалидный или поддельный токен — None."""
    assert web3_auth.verify_jwt_token("invalid") is None
    assert web3_auth.verify_jwt_token("eyJhbGciOiJIUzI1NiJ9.e30.x") is None
