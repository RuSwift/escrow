"""
Тесты NodeService на реальной БД и Redis (fixtures из tests/conftest.py).
"""
import pytest
from didcomm.crypto import EthKeyPair, KeyPair as BaseKeyPair

from services.node import NodeService


@pytest.fixture
def valid_mnemonic():
    """Валидная мнемоническая фраза для тестов."""
    from mnemonic import Mnemonic
    mnemo = Mnemonic("english")
    return mnemo.generate(strength=128)


@pytest.fixture
def node_service(test_db, test_redis, test_settings) -> NodeService:
    """NodeService с тестовой сессией, Redis и настройками."""
    return NodeService(session=test_db, redis=test_redis, settings=test_settings)


# --- has_key ---


@pytest.mark.asyncio
async def test_has_key_empty(node_service):
    """Без инициализации has_key() возвращает False."""
    assert await node_service.has_key() is False


@pytest.mark.asyncio
async def test_has_key_after_init_mnemonic(node_service, valid_mnemonic):
    """После init_from_mnemonic has_key() возвращает True."""
    await node_service.init_from_mnemonic(valid_mnemonic)
    assert await node_service.has_key() is True


# --- init_from_mnemonic ---


@pytest.mark.asyncio
async def test_init_from_mnemonic_success(node_service, valid_mnemonic):
    """init_from_mnemonic создаёт ноду и возвращает NodeInitResponseSchema."""
    out = await node_service.init_from_mnemonic(valid_mnemonic)
    assert out.did.startswith("did:peer:1:")
    assert out.address is not None
    assert len(out.address) == 42
    assert out.key_type == "mnemonic"
    assert out.public_key
    assert "id" in out.did_document
    assert out.did_document["id"] == out.did


@pytest.mark.asyncio
async def test_init_from_mnemonic_twice_raises(node_service, valid_mnemonic):
    """Повторный init_from_mnemonic поднимает ValueError."""
    await node_service.init_from_mnemonic(valid_mnemonic)
    with pytest.raises(ValueError, match="Нода инициализируется только один раз"):
        await node_service.init_from_mnemonic(valid_mnemonic)


@pytest.mark.asyncio
async def test_init_from_mnemonic_invalid_raises(node_service):
    """Невалидная мнемоника поднимает ValueError."""
    with pytest.raises(ValueError, match="Invalid mnemonic phrase"):
        await node_service.init_from_mnemonic("not a valid mnemonic phrase here")


# --- init_from_pem ---


@pytest.mark.asyncio
async def test_init_from_pem_success(node_service):
    """init_from_pem создаёт ноду и возвращает NodeInitResponseSchema."""
    key = BaseKeyPair.generate_ec()
    pem_str = key.to_pem(format="PKCS8").decode("utf-8")
    out = await node_service.init_from_pem(pem_str)
    assert out.did.startswith("did:peer:1:")
    assert out.key_type == "pem"
    assert out.public_key
    assert "id" in out.did_document


@pytest.mark.asyncio
async def test_init_from_pem_twice_raises(node_service):
    """Повторный init_from_pem поднимает ValueError."""
    key = BaseKeyPair.generate_ec()
    pem_str = key.to_pem(format="PKCS8").decode("utf-8")
    await node_service.init_from_pem(pem_str)
    with pytest.raises(ValueError, match="Нода инициализируется только один раз"):
        await node_service.init_from_pem(pem_str)


@pytest.mark.asyncio
async def test_init_from_pem_no_private_key_raises(node_service):
    """PEM без приватного ключа поднимает ValueError."""
    pem_public = "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA\n-----END PUBLIC KEY-----"
    with pytest.raises(ValueError, match="PEM данные не содержат приватный ключ"):
        await node_service.init_from_pem(pem_public)


# --- get_active_keypair ---


@pytest.mark.asyncio
async def test_get_active_keypair_after_mnemonic(node_service, valid_mnemonic):
    """После init_from_mnemonic get_active_keypair возвращает EthKeyPair."""
    await node_service.init_from_mnemonic(valid_mnemonic)
    kp = await node_service.get_active_keypair()
    assert kp is not None
    assert isinstance(kp, EthKeyPair)


@pytest.mark.asyncio
async def test_get_active_keypair_after_pem(node_service):
    """После init_from_pem get_active_keypair возвращает KeyPair."""
    key = BaseKeyPair.generate_ec()
    pem_str = key.to_pem(format="PKCS8").decode("utf-8")
    await node_service.init_from_pem(pem_str)
    kp = await node_service.get_active_keypair()
    assert kp is not None
    assert isinstance(kp, BaseKeyPair)


@pytest.mark.asyncio
async def test_get_active_keypair_empty(node_service):
    """Без ноды get_active_keypair возвращает None."""
    assert await node_service.get_active_keypair() is None


# --- set_service_endpoint / get_service_endpoint ---


@pytest.mark.asyncio
async def test_set_service_endpoint_success(node_service, valid_mnemonic):
    """set_service_endpoint обновляет endpoint, get_service_endpoint возвращает его."""
    await node_service.init_from_mnemonic(valid_mnemonic)
    ok = await node_service.set_service_endpoint("https://node.example.com/didcomm")
    assert ok is True
    assert await node_service.get_service_endpoint() == "https://node.example.com/didcomm"


@pytest.mark.asyncio
async def test_set_service_endpoint_no_node_returns_false(node_service):
    """Без инициализированной ноды set_service_endpoint возвращает False."""
    ok = await node_service.set_service_endpoint("https://node.example.com/")
    assert ok is False


@pytest.mark.asyncio
async def test_get_service_endpoint_empty(node_service):
    """Без ноды get_service_endpoint возвращает None."""
    assert await node_service.get_service_endpoint() is None


# --- is_service_endpoint_configured ---


@pytest.mark.asyncio
async def test_is_service_endpoint_configured_false_when_empty(node_service):
    """Без ноды is_service_endpoint_configured возвращает False."""
    assert await node_service.is_service_endpoint_configured() is False


@pytest.mark.asyncio
async def test_is_service_endpoint_configured_true_after_set(node_service, valid_mnemonic):
    """После set_service_endpoint is_service_endpoint_configured возвращает True."""
    await node_service.init_from_mnemonic(valid_mnemonic)
    await node_service.set_service_endpoint("https://node.test/")
    assert await node_service.is_service_endpoint_configured() is True


# --- get_service_endpoint_response ---


@pytest.mark.asyncio
async def test_get_service_endpoint_response(node_service, valid_mnemonic):
    """get_service_endpoint_response возвращает ServiceEndpointResponseSchema."""
    await node_service.init_from_mnemonic(valid_mnemonic)
    await node_service.set_service_endpoint("https://api.example/")
    resp = await node_service.get_service_endpoint_response()
    assert resp.service_endpoint == "https://api.example/"


@pytest.mark.asyncio
async def test_get_service_endpoint_response_empty(node_service):
    """Без ноды get_service_endpoint_response возвращает schema с None."""
    resp = await node_service.get_service_endpoint_response()
    assert resp.service_endpoint is None


# --- is_node_initialized ---


@pytest.mark.asyncio
async def test_is_node_initialized_false_without_admin(node_service, valid_mnemonic):
    """Без настроенного админа (env) is_node_initialized возвращает False даже при ключе и endpoint."""
    await node_service.init_from_mnemonic(valid_mnemonic)
    await node_service.set_service_endpoint("https://node.test/")
    # test_settings по умолчанию не имеет админа из env
    assert await node_service.is_node_initialized() is False

