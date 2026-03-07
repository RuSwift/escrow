"""
Тесты NodeRepository на реальной БД и Redis (fixtures из tests/conftest.py).
"""
import pytest
from didcomm.crypto import EthKeyPair, KeyPair as BaseKeyPair

from repos.node import NodeRepository, NodeResource


@pytest.fixture
def valid_mnemonic():
    """Валидная мнемоническая фраза для тестов."""
    from mnemonic import Mnemonic
    mnemo = Mnemonic("english")
    return mnemo.generate(strength=128)


@pytest.fixture
def node_repo(test_db, test_redis, test_settings) -> NodeRepository:
    """Репозиторий ноды с тестовой сессией, Redis и настройками."""
    return NodeRepository(
        session=test_db,
        redis=test_redis,
        settings=test_settings,
    )


# --- get() ---


@pytest.mark.asyncio
async def test_get_empty_returns_none(node_repo):
    """Без записей get() возвращает None."""
    assert await node_repo.get() is None


# --- create() ---


@pytest.mark.asyncio
async def test_create_with_mnemonic_success(node_repo, valid_mnemonic):
    """create() с мнемоникой создаёт активную запись и возвращает Get."""
    data = NodeResource.Create(
        key_type="mnemonic",
        ethereum_address=None,
        service_endpoint="https://node.test/",
    )
    out = await node_repo.create(data, mnemonic=valid_mnemonic)
    assert out is not None
    assert out.id >= 1
    assert out.key_type == "mnemonic"
    assert out.is_active is True
    assert out.service_endpoint == "https://node.test/"


@pytest.mark.asyncio
async def test_create_twice_raises(node_repo, valid_mnemonic):
    """Второй вызов create() поднимает ValueError."""
    data = NodeResource.Create(key_type="mnemonic")
    await node_repo.create(data, mnemonic=valid_mnemonic)
    with pytest.raises(ValueError, match="Нода инициализируется только один раз"):
        await node_repo.create(data, mnemonic=valid_mnemonic)


# --- get_plain_mnemonic / get_plain_pem ---


@pytest.mark.asyncio
async def test_get_plain_mnemonic_after_create(node_repo, valid_mnemonic):
    """После create(mnemonic=...) get_plain_mnemonic() возвращает ту же фразу."""
    data = NodeResource.Create(key_type="mnemonic")
    await node_repo.create(data, mnemonic=valid_mnemonic)
    plain = await node_repo.get_plain_mnemonic()
    assert plain == valid_mnemonic


@pytest.mark.asyncio
async def test_get_plain_mnemonic_no_row_returns_none(node_repo):
    """Без активной ноды get_plain_mnemonic() возвращает None."""
    assert await node_repo.get_plain_mnemonic() is None


@pytest.mark.asyncio
async def test_get_plain_pem_after_create_with_pem(node_repo):
    """После create(pem=...) get_plain_pem() возвращает тот же PEM."""
    key = BaseKeyPair.generate_ec()
    pem_bytes = key.to_pem(format="PKCS8")
    pem_str = pem_bytes.decode("utf-8")
    data = NodeResource.Create(key_type="pem")
    await node_repo.create(data, pem=pem_str)
    plain = await node_repo.get_plain_pem()
    assert plain == pem_str


@pytest.mark.asyncio
async def test_get_plain_pem_no_row_returns_none(node_repo):
    """Без активной ноды get_plain_pem() возвращает None."""
    assert await node_repo.get_plain_pem() is None


# --- get_active_keypair ---


@pytest.mark.asyncio
async def test_get_active_keypair_mnemonic(node_repo, valid_mnemonic):
    """При key_type=mnemonic get_active_keypair() возвращает EthKeyPair."""
    data = NodeResource.Create(key_type="mnemonic")
    await node_repo.create(data, mnemonic=valid_mnemonic)
    kp = await node_repo.get_active_keypair()
    assert kp is not None
    assert isinstance(kp, EthKeyPair)


@pytest.mark.asyncio
async def test_get_active_keypair_pem(node_repo):
    """При key_type=pem get_active_keypair() возвращает KeyPair (EC)."""
    key = BaseKeyPair.generate_ec()
    pem_str = key.to_pem(format="PKCS8").decode("utf-8")
    data = NodeResource.Create(key_type="pem")
    await node_repo.create(data, pem=pem_str)
    kp = await node_repo.get_active_keypair()
    assert kp is not None
    assert isinstance(kp, BaseKeyPair)


@pytest.mark.asyncio
async def test_get_active_keypair_no_row_returns_none(node_repo):
    """Без активной ноды get_active_keypair() возвращает None."""
    assert await node_repo.get_active_keypair() is None


# --- patch_active ---


@pytest.mark.asyncio
async def test_patch_active_service_endpoint(node_repo, valid_mnemonic):
    """patch_active() обновляет service_endpoint."""
    data = NodeResource.Create(
        key_type="mnemonic",
        service_endpoint="https://old.example/",
    )
    await node_repo.create(data, mnemonic=valid_mnemonic)
    updated = await node_repo.patch_active(
        NodeResource.Patch(service_endpoint="https://new.example/")
    )
    assert updated is not None
    assert updated.service_endpoint == "https://new.example/"


@pytest.mark.asyncio
async def test_patch_active_empty_payload_returns_current(node_repo, valid_mnemonic):
    """patch_active() без полей возвращает текущую запись."""
    data = NodeResource.Create(key_type="mnemonic")
    await node_repo.create(data, mnemonic=valid_mnemonic)
    before = await node_repo.get()
    updated = await node_repo.patch_active(NodeResource.Patch())
    assert updated is not None
    assert updated.id == before.id
