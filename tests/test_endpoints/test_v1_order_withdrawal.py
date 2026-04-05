"""POST withdrawal, GET order-sign по dedupe_key в БД, DELETE заявки, submit подписи external."""

from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mnemonic import Mnemonic
from sqlalchemy import select

from db import get_db
from db.models import Order, Wallet, WalletUser
from repos.order import ORDER_CATEGORY_WITHDRAWAL, withdrawal_dedupe_key
from services.order import OrderService, WITHDRAWAL_KIND, WITHDRAWAL_STATUS_AWAITING_SIGNATURES
from services.tron.utils import keypair_from_mnemonic
from services.multisig_wallet.constants import MULTISIG_STATUS_ACTIVE
from services.multisig_wallet.meta import default_meta_dict
from web.endpoints.dependencies import (
    get_redis,
    get_required_wallet_address_for_space,
    get_settings,
    ResolvedSettings,
)
from web.main import create_app

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"
_SIGNER_IN_MS = "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi"
_STRANGER_TRON = "TYDkyTwMF7ti5R8VstRruqz4N9mGne2CdF"


class _FakeTronGridForRefresh:
    """Заглушка TronGrid для refresh_withdrawal_statuses (без HTTP)."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return None

    async def get_transaction_success(self, _txid: str):
        return True

    async def get_transaction_info(self, _txid: str):
        return {"receipt": {"result": "SUCCESS"}}


@pytest_asyncio.fixture
async def main_app_withdrawal(test_db, test_redis, test_settings):
    owner = WalletUser(
        nickname="wd_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:wd_space",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w = Wallet(
        name="ramp_ext",
        encrypted_mnemonic=None,
        role="external",
        tron_address="TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi",
        owner_did=owner.did,
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        return ResolvedSettings(
            settings=test_settings,
            has_key=True,
            is_admin_configured=True,
            is_node_initialized=True,
        )

    async def override_wallet_address_for_space():
        return _OWNER_TRON

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_required_wallet_address_for_space] = (
        override_wallet_address_for_space
    )

    yield app, w.id
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def main_app_withdrawal_external_mnemonic(test_db, test_redis, test_settings):
    """
    External ramp-кошелёк: TRON-адрес из случайной BIP39-мнемоники (как у TronWeb-кошелька).
    """
    phrase = Mnemonic("english").generate(strength=128)
    external_tron, _ = keypair_from_mnemonic(phrase, account_index=0)
    dest_tron, _ = keypair_from_mnemonic(phrase, account_index=1)

    owner = WalletUser(
        nickname="wd_ext_mnem",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:web:escrow.ruswift.ru:wd_ext_mnem",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    w = Wallet(
        name="ramp_ext_mnem",
        encrypted_mnemonic=None,
        role="external",
        tron_address=external_tron,
        owner_did=owner.did,
    )
    test_db.add(w)
    await test_db.commit()
    await test_db.refresh(w)

    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        return ResolvedSettings(
            settings=test_settings,
            has_key=True,
            is_admin_configured=True,
            is_node_initialized=True,
        )

    async def override_wallet_address_for_space():
        return _OWNER_TRON

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_required_wallet_address_for_space] = (
        override_wallet_address_for_space
    )

    yield app, w.id, external_tron, dest_tron
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_withdrawal_201(main_app_withdrawal, test_redis):
    app, wallet_id = main_app_withdrawal
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
            with patch("services.order.NotifyService", autospec=True) as mock_notify_cls:
                mock_notify = mock_notify_cls.return_value
                
                # Let's use a simpler way to mock async method
                async def fake_send(*args, **kwargs): pass
                mock_notify.send_message.side_effect = fake_send
                mock_notify._message_for_event.return_value = "Withdrawal created text"
                mock_notify._language_for_scope.return_value = "ru"

                r = await client.post(
                    "/v1/spaces/wd_space/orders/withdrawal",
                    json={
                        "wallet_id": wallet_id,
                        "token_type": "native",
                        "symbol": "TRX",
                        "contract_address": None,
                        "amount_raw": 1_000_000,
                        "destination_address": "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi",
                        "purpose": "Тестовое назначение",
                    },
                )
                assert r.status_code == 201, r.text
                
                # Check notification
                assert mock_notify.send_message.called
                args, _ = mock_notify.send_message.call_args
                recipients = args[0]
                text = args[1]
                assert len(recipients) >= 1
                assert recipients[0]["scope"] == "wd_space"
                assert text == "Withdrawal created text"
                data = r.json()
                assert data["order"]["payload"].get("purpose") == "Тестовое назначение"
                assert "sign_url" in data
                assert "/o/" in data["sign_url"]
                assert data["order"]["payload"]["kind"] == "withdrawal_request"
                assert data["order"]["category"] == ORDER_CATEGORY_WITHDRAWAL
                dedupe = data["order"]["dedupe_key"]
                assert dedupe.startswith("withdrawal:")
                sign_token = dedupe.split("withdrawal:", 1)[1]
                assert sign_token in data["sign_url"]
                assert dedupe == withdrawal_dedupe_key(sign_token)
                r_sign = await client.get(f"/v1/order-sign/{sign_token}")
                assert r_sign.status_code == 200, r_sign.text
                assert r_sign.json()["order_id"] == data["order"]["id"]
                assert r_sign.json().get("purpose") == "Тестовое назначение"


@pytest.mark.asyncio
async def test_order_sign_get_404(main_app_withdrawal):
    app, _ = main_app_withdrawal
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/order-sign/invalidtoken00000000000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_withdrawal_204(main_app_withdrawal):
    app, wallet_id = main_app_withdrawal
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/spaces/wd_space/orders/withdrawal",
            json={
                "wallet_id": wallet_id,
                "token_type": "native",
                "symbol": "TRX",
                "contract_address": None,
                "amount_raw": 1_000_000,
                "destination_address": "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi",
                "purpose": "Выплата контрагенту",
            },
        )
        assert r.status_code == 201
        order_id = r.json()["order"]["id"]
        r_del = await client.delete(f"/v1/spaces/wd_space/orders/{order_id}")
    assert r_del.status_code == 204


@pytest.mark.asyncio
async def test_delete_withdrawal_400_when_confirmed(main_app_withdrawal, test_db):
    app, wallet_id = main_app_withdrawal
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/spaces/wd_space/orders/withdrawal",
            json={
                "wallet_id": wallet_id,
                "token_type": "native",
                "symbol": "TRX",
                "contract_address": None,
                "amount_raw": 1_000_000,
                "destination_address": "TV6ZVcKH24NzWxwdRbCvVD5gqAwaypdkRi",
                "purpose": "Тест",
            },
        )
        assert r.status_code == 201
        order_id = r.json()["order"]["id"]
        row_res = await test_db.execute(select(Order).where(Order.id == order_id))
        row = row_res.scalar_one()
        payload = dict(row.payload or {})
        payload["status"] = "confirmed"
        row.payload = payload
        test_db.add(row)
        await test_db.commit()
        r_del = await client.delete(f"/v1/spaces/wd_space/orders/{order_id}")
    assert r_del.status_code == 400
    assert "Cannot delete withdrawal" in r_del.json()["detail"]


@pytest.mark.asyncio
async def test_external_withdrawal_mnemonic_submit_then_confirmed_trongrid_mock(
    main_app_withdrawal_external_mnemonic,
    test_db,
    test_redis,
    test_settings,
):
    """
    External-кошелёк с адресом из мнемоники: POST submit → broadcast_submitted;
    TronGrid замокан → refresh как в cron → GET /orders видит confirmed.
    """
    app, wallet_id, external_tron, dest_tron = main_app_withdrawal_external_mnemonic
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/spaces/wd_ext_mnem/orders/withdrawal",
            json={
                "wallet_id": wallet_id,
                "token_type": "native",
                "symbol": "TRX",
                "contract_address": None,
                "amount_raw": 1_000_000,
                "destination_address": dest_tron,
                "purpose": "mnemonic external flow",
            },
        )
        assert r.status_code == 201, r.text
        sign_token = r.json()["order"]["dedupe_key"].split("withdrawal:", 1)[1]
        fake_tx_id = "a1" * 32
        r_sub = await client.post(
            f"/v1/order-sign/{sign_token}/submit",
            json={
                "signer_address": external_tron,
                "signed_transaction": {"txID": fake_tx_id, "visible": True},
            },
        )
        assert r_sub.status_code == 200, r_sub.text
        assert r_sub.json()["payload"]["status"] == "broadcast_submitted"
        assert r_sub.json()["payload"]["broadcast_tx_id"] == fake_tx_id

        with patch(
            "services.order.TronGridClient",
            _FakeTronGridForRefresh,
        ), patch("services.order.NotifyService", autospec=True) as mock_notify_cls:
            mock_notify = mock_notify_cls.return_value
            async def fake_send(*args, **kwargs): pass
            mock_notify.send_message.side_effect = fake_send
            mock_notify._message_for_event.return_value = "Confirmed text"
            mock_notify._language_for_scope.return_value = "ru"

            svc = OrderService(test_db, test_redis, test_settings)
            # Force commit before refresh
            await test_db.commit()
            stats = await svc.refresh_withdrawal_statuses()
            await test_db.commit()
            
            # Check notification
            assert mock_notify.send_message.called
            args, _ = mock_notify.send_message.call_args
            assert args[1] == "Confirmed text"

        assert stats.get("updated", 0) >= 1

        r_list = await client.get("/v1/spaces/wd_ext_mnem/orders")
        assert r_list.status_code == 200, r_list.text
        match = next(
            (
                x
                for x in r_list.json()["items"]
                if x.get("dedupe_key") == f"withdrawal:{sign_token}"
            ),
            None,
        )
        assert match is not None
        assert match["payload"]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_order_sign_submit_second_time_not_awaiting_400(
    main_app_withdrawal_external_mnemonic,
):
    """После submit заявка не в awaiting* — повторный submit даёт 400."""
    app, wallet_id, external_tron, dest_tron = main_app_withdrawal_external_mnemonic
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/v1/spaces/wd_ext_mnem/orders/withdrawal",
            json={
                "wallet_id": wallet_id,
                "token_type": "native",
                "symbol": "TRX",
                "contract_address": None,
                "amount_raw": 500_000,
                "destination_address": dest_tron,
                "purpose": "double submit",
            },
        )
        assert r.status_code == 201, r.text
        sign_token = r.json()["order"]["dedupe_key"].split("withdrawal:", 1)[1]
        r1 = await client.post(
            f"/v1/order-sign/{sign_token}/submit",
            json={
                "signer_address": external_tron,
                "signed_transaction": {"txID": "d4" * 32},
            },
        )
        assert r1.status_code == 200, r1.text
        r2 = await client.post(
            f"/v1/order-sign/{sign_token}/submit",
            json={
                "signer_address": external_tron,
                "signed_transaction": {"txID": "e5" * 32},
            },
        )
    assert r2.status_code == 400
    assert "not awaiting" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_order_sign_submit_multisig_rejects_signer_not_in_actors(
    main_app_withdrawal, test_db
):
    """POST /order-sign/.../submit: multisig — адрес не из actors_snapshot → 400."""
    app, _ = main_app_withdrawal

    owner_res = await test_db.execute(
        select(WalletUser).where(WalletUser.nickname == "wd_space")
    )
    owner = owner_res.scalar_one()

    w_ms = Wallet(
        name="ramp_ms_submit",
        encrypted_mnemonic="enc",
        role="multisig",
        tron_address="TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5B",
        owner_did=owner.did,
        multisig_setup_status=MULTISIG_STATUS_ACTIVE,
        multisig_setup_meta={
            **default_meta_dict(),
            "actors": [_SIGNER_IN_MS],
            "threshold_n": 1,
            "threshold_m": 1,
        },
    )
    test_db.add(w_ms)
    await test_db.commit()
    await test_db.refresh(w_ms)

    sign_tok = "endpoint_ms_actor_test_tok_01"
    order = Order(
        category=ORDER_CATEGORY_WITHDRAWAL,
        dedupe_key=withdrawal_dedupe_key(sign_tok),
        space_wallet_id=w_ms.id,
        payload={
            "kind": WITHDRAWAL_KIND,
            "status": WITHDRAWAL_STATUS_AWAITING_SIGNATURES,
            "wallet_role": "multisig",
            "tron_address": w_ms.tron_address,
            "threshold_n": 1,
            "threshold_m": 1,
            "actors_snapshot": [_SIGNER_IN_MS],
            "long_expiration_ms": False,
        },
    )
    test_db.add(order)
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.post(
            f"/v1/order-sign/{sign_tok}/submit",
            json={
                "signer_address": _STRANGER_TRON,
                "signed_transaction": {"txID": "x"},
            },
        )
    assert r.status_code == 400
    assert "actors" in r.json().get("detail", "").lower()
