"""Тесты на учет комиссии арбитра в системном слоте PaymentRequest."""

from unittest.mock import AsyncMock, patch
from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from decimal import Decimal
from sqlalchemy import select

from db import get_db
from db.models import Wallet, WalletUser, GuarantorProfile, PrimaryWallet
from web.endpoints.dependencies import (
    UserInfo,
    get_current_wallet_user,
    get_redis,
    get_settings,
    ResolvedSettings,
)
from web.main import create_app

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"
_ARBITER_TRON = "TArbiterCommissionTest11111111111"
SIMPLE_ARBITER_DID = "did:peer:arbiter_commission_test"

@pytest_asyncio.fixture
async def arbiter_app(test_db, test_redis, test_settings):
    # 1. Создаем арбитра как WalletUser
    arbiter_user = WalletUser(
        nickname="arbiter_space",
        wallet_address=_ARBITER_TRON,
        blockchain="tron",
        did=SIMPLE_ARBITER_DID,
    )
    test_db.add(arbiter_user)
    
    # 2. Создаем владельца заявки
    owner = WalletUser(
        nickname="owner_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:tron:owner_hs",
    )
    test_db.add(owner)
    await test_db.commit()
    
    # ПЕРЕПРОЧИТЫВАЕМ ИЗ БД ЧТОБЫ ИМЕТЬ ЧИСТЫЕ ОБЪЕКТЫ
    res_arb = await test_db.execute(select(WalletUser).where(WalletUser.did == SIMPLE_ARBITER_DID))
    arbiter_user = res_arb.scalar_one()
    res_own = await test_db.execute(select(WalletUser).where(WalletUser.did == "did:tron:owner_hs"))
    owner = res_own.scalar_one()

    # 3. Настраиваем профиль гаранта (комиссия 1.5%)
    profile = GuarantorProfile(
        wallet_user_id=arbiter_user.id,
        space="owner_space", # Профиль арбитра в спейсе владельца
        commission_percent=Decimal("1.5"),
        arbiter_public_slug="test-arbiter-slug", # Добавляем slug
    )
    test_db.add(profile)
    
    # 4. Настраиваем первичный кошелек арбитра для выплат
    pw = PrimaryWallet(
        wallet_user_id=arbiter_user.id,
        address=_ARBITER_TRON,
        blockchain="tron",
    )
    test_db.add(pw)
    
    await test_db.commit()

    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        # Устанавливаем системную комиссию 0.2%
        test_settings.commission_wallet.percent = Decimal("0.2")
        return ResolvedSettings(
            settings=test_settings,
            has_key=True,
            is_admin_configured=True,
            is_node_initialized=True,
        )

    async def override_current_user():
        # ВАЖНО: DID должен совпадать с тем, что в БД
        return UserInfo(
            standard="tron",
            wallet_address=_OWNER_TRON,
            did="did:tron:owner_hs",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_wallet_user] = override_current_user

    yield app, owner, arbiter_user
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_pr_includes_arbiter_commission(arbiter_app, test_db, test_redis, test_settings):
    app, owner, arbiter = arbiter_app
    
    # Используем DID напрямую в URL
    arbiter_path = quote(SIMPLE_ARBITER_DID, safe='')
    url = f"/v1/arbiter/{arbiter_path}/payment-requests"
    
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
            "amount": "1000",
            "side": "receive",
        },
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(url, json=payload)
        assert response.status_code == 201, response.text
        
        pr = response.json()["payment_request"]
        comm = pr["commissioners"]
        assert "system" in comm
        
        sys_slot = comm["system"]
        # Системная комиссия (0.2%)
        assert sys_slot["commission"]["value"] == "0.2"
        # Комиссия арбитра (1.5%)
        assert sys_slot["arbiter_commission"]["value"] == "1.5"
        assert sys_slot["arbiter_payout_address"] == _ARBITER_TRON
        
        # Проверяем снимки (snapshots)
        # B = 1000 USDT
        # fee_system = 1000 * 0.002 = 2.0
        # fee_arbiter = 1000 * 0.015 = 15.0
        # total borrow_amount = 17.0
        assert sys_slot["borrow_amount"] == "17"
        
        # payment_amount (на фиатной ноге 10000 CNY)
        # fee_system = 10000 * 0.002 = 20.0
        # fee_arbiter = 10000 * 0.015 = 150.0
        # total payment_amount = 170.0
        assert sys_slot["payment_amount"] == "170"

@pytest.mark.asyncio
async def test_create_pr_with_slug_includes_arbiter_commission(arbiter_app, test_db, test_redis, test_settings):
    app, owner, arbiter = arbiter_app
    
    # Используем slug в URL
    url = f"/v1/arbiter/test-arbiter-slug/payment-requests"
    
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
            "amount": "1000",
            "side": "receive",
        },
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(url, json=payload)
        assert response.status_code == 201, response.text
        
        pr = response.json()["payment_request"]
        sys_slot = pr["commissioners"]["system"]
        assert sys_slot["arbiter_commission"]["value"] == "1.5"
        assert sys_slot["arbiter_payout_address"] == _ARBITER_TRON
