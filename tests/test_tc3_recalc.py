import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from web.endpoints.dependencies import get_current_wallet_user, UserInfo
from db.models import WalletUser, Wallet
from web.main import create_app
from db import get_db
import pytest_asyncio
from urllib.parse import quote

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"
_OTHER_TRON = "TF4BB2BNnnpLHBBTG2GEWHhGXT7PoYVyxL"
_COMMISSIONER_TRON = "TP8PmmcgrTv1ASwJ7UPe8fDCmbUtTYLxnd"
SIMPLE_HANDSHAKE_ARBITER = "did:peer:handshake_arbiter"

def _v1():
    return f"/v1/arbiter/{quote(SIMPLE_HANDSHAKE_ARBITER, safe='')}"

@pytest_asyncio.fixture
async def tc3_app_setup(test_db, test_redis, test_settings):
    owner = WalletUser(
        nickname="tc3_owner",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:tron:tc3_owner",
    )
    other = WalletUser(
        nickname="tc3_other",
        wallet_address=_OTHER_TRON,
        blockchain="tron",
        did="did:tron:tc3_other",
    )
    comm = WalletUser(
        nickname="tc3_comm",
        wallet_address=_COMMISSIONER_TRON,
        blockchain="tron",
        did=f"did:tron:{_COMMISSIONER_TRON}",
    )
    test_db.add(owner)
    test_db.add(other)
    test_db.add(comm)
    
    test_db.add(
        Wallet(
            name="arb_tc3",
            role="arbiter",
            tron_address="TArbiterTC3Test11111111111",
            owner_did=SIMPLE_HANDSHAKE_ARBITER,
        )
    )
    await test_db.commit()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: test_db
    # Note: in real tests we use async generators for get_db, but for simplicity here:
    async def override_get_db():
        yield test_db
    app.dependency_overrides[get_db] = override_get_db

    yield app, owner, other, comm

@pytest.mark.asyncio
async def test_tc3_commission_recalculation_on_accept(tc3_app_setup):
    """
    TC-3: Проверка пересчета комиссий при фиксации суммы акцептором.
    """
    app, owner, other, comm = tc3_app_setup
    
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "CNY",
            "amount": "10000",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": None,
            "side": "receive",
            "amount_discussed": True,
        },
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create PR as Owner
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron", wallet_address=_OWNER_TRON, did=owner.did
        )
        c = await client.post(_v1() + "/payment-requests", json=payload)
        assert c.status_code == 201
        uid = c.json()["payment_request"]["uid"]
        pk = c.json()["payment_request"]["pk"]

        # 2. Commissioner sets 0.7%
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron", wallet_address=_COMMISSIONER_TRON, did=comm.did
        )
        r = await client.post(_v1() + f"/payment-requests/{uid}/resell", json={"intermediary_percent": "0.7"})
        assert r.status_code == 200

        # 3. Acceptor accepts and sets 1000 USDT
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron", wallet_address=_OTHER_TRON, did=other.did
        )
        a = await client.post(_v1() + f"/payment-requests/{pk}/accept", json={"counter_stable_amount": "1000"})
        assert a.status_code == 200
        
        pr = a.json()["payment_request"]
        commissioners = pr["commissioners"]
        
        # 4. Verify recalculation
        interm_slot = next((s for s in commissioners.values() if s.get("role") == "intermediary"), None)
        assert interm_slot is not None
        # borrow_amount can be "7" or "7.00" depending on formatting in build_slot_snapshots
        assert float(interm_slot["borrow_amount"]) == 7.0
        
        system_slot = commissioners.get("system")
        assert system_slot is not None
        assert system_slot["borrow_amount"] != ""
        assert float(system_slot["borrow_amount"]) > 0
