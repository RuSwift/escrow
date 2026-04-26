"""GET /v1/arbiter/{arbiter_space_did}/resolve/{uid} — контекст страницы Simple."""

from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from db.models import Deal, Wallet, WalletUser
from services.payment_request_commission_graph import intermediary_slot_keys_for_did
from web.endpoints.dependencies import (
    UserInfo,
    get_current_wallet_user,
    get_redis,
    get_settings,
    ResolvedSettings,
)
from web.main import create_app

_OWNER_TRON = "TLrJJkGK4puQGZLFbrPxK2icPgADaNTq5A"
_OTHER_TRON = "TQOtherSimpleResolveWallet999999999"

SIMPLE_RESOLVE_ARBITER = "did:peer:resolve_arbiter"


def _intermediary_slot_for_did(comm: dict, did: str) -> dict:
    """Слот посредника (не system/counterparty) с данным did — любой ключ JSON."""
    for v in comm.values():
        if not isinstance(v, dict):
            continue
        if (v.get("did") or "").strip() != did:
            continue
        role = str(v.get("role") or "").strip().lower()
        if role != "intermediary":
            continue
        return v
    raise AssertionError(f"no intermediary slot for did={did!r}")


def _any_slot_for_did(comm: dict, did: str) -> dict:
    """Любой слот (кроме system) с данным did — в т.ч. participant."""
    for v in comm.values():
        if not isinstance(v, dict):
            continue
        if (v.get("did") or "").strip() != did:
            continue
        role = str(v.get("role") or "").strip().lower()
        if role == "system":
            continue
        return v
    raise AssertionError(f"no slot for did={did!r}")


def _expected_intermediary_parent_id(comm: dict, root_public_ref: str) -> str:
    """Как в _resell_parent_ref: родитель посредника — алиас system или public_ref заявки."""
    sys_slot = comm.get("system")
    if isinstance(sys_slot, dict):
        a = (sys_slot.get("alias_public_ref") or "").strip()
        if a:
            return a
    return root_public_ref


def _resolve_v1() -> str:
    return f"/v1/arbiter/{quote(SIMPLE_RESOLVE_ARBITER, safe='')}"


@pytest_asyncio.fixture
async def main_app_simple_resolve(test_db, test_redis, test_settings):
    owner = WalletUser(
        nickname="simple_resolve_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:tron:simple_resolve_owner",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    other = WalletUser(
        nickname="simple_resolve_other",
        wallet_address=_OTHER_TRON,
        blockchain="tron",
        did="did:tron:simple_resolve_other",
    )
    test_db.add(other)
    acceptor = WalletUser(
        nickname="simple_resolve_acceptor",
        wallet_address="TQAcceptorResolveWallet7777777777",
        blockchain="tron",
        did="did:tron:simple_resolve_acceptor",
    )
    test_db.add(acceptor)

    test_db.add(
        Wallet(
            name="arb_resolve_test",
            encrypted_mnemonic="enc",
            role="arbiter",
            tron_address="TArbiterResolveTest11111111111",
            ethereum_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            owner_did="did:peer:resolve_arbiter",
        )
    )
    await test_db.commit()

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

    async def override_current_user():
        return UserInfo(
            standard="tron",
            wallet_address=_OWNER_TRON,
            did=owner.did,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_wallet_user] = override_current_user

    yield app, owner, other, acceptor
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resolve_payment_request_only(main_app_simple_resolve):
    app, owner, _other, _acc = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "CNY",
            "amount": "862500",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "125000",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        uid = c.json()["payment_request"]["uid"]

        r = await client.get(f"{_resolve_v1()}/resolve/{uid}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["kind"] == "payment_request_only"
        assert body["viewer_did"] == owner.did
        assert body["payment_request"]["uid"] == uid
        assert body["payment_request"]["space_id"] == owner.id
        assert body["payment_request"]["owner_did"] == owner.did
        assert body["payment_request"]["arbiter_did"] == SIMPLE_RESOLVE_ARBITER
        assert body["deal"] is None

        pub = body["payment_request"]["public_ref"]
        assert isinstance(pub, str) and len(pub) >= 8
        comm = body["payment_request"]["commissioners"]
        assert set(comm.keys()) <= {"system"}
        assert not any(k.startswith("i_") or k == "resell" for k in comm)

        r2 = await client.get(f"{_resolve_v1()}/resolve/{pub}")
        assert r2.status_code == 200, r2.text
        assert r2.json()["payment_request"]["uid"] == uid
        assert r2.json()["payment_request"]["public_ref"] == pub


@pytest.mark.asyncio
async def test_resolve_payment_request_other_user_200(main_app_simple_resolve):
    app, owner, other, _acc = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "EUR",
            "amount": "100",
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        uid = c.json()["payment_request"]["uid"]
        pub_owner = c.json()["payment_request"]["public_ref"]

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        try:
            r = await client.get(f"{_resolve_v1()}/resolve/{uid}")
            assert r.status_code == 200
            body = r.json()
            assert body["kind"] == "payment_request_only"
            assert body["viewer_did"] == other.did
            pr = body["payment_request"]
            assert pr["uid"] == uid
            slot = _any_slot_for_did(pr["commissioners"], other.did)
            # По умолчанию роль не определена: participant с персональным alias, без комиссии
            assert slot.get("role") == "participant"
            assert slot.get("commission") is None
            alias = slot.get("alias_public_ref")
            assert alias and len(alias) >= 8
            assert pr["public_ref"] == alias
            assert pr["original_public_ref"] == pub_owner
            assert slot["parent_id"] == _expected_intermediary_parent_id(
                pr["commissioners"], pub_owner
            )
        finally:
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=owner.did,
            )


@pytest.mark.asyncio
async def test_resolve_payment_request_other_user_twice_idempotent(main_app_simple_resolve):
    """Повторный GET resolve тем же «чужим» кошельком не создаёт второй слот — тот же alias/public_ref."""
    app, owner, other, _acc = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "EUR",
            "amount": "100",
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        uid = c.json()["payment_request"]["uid"]

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        try:
            r1 = await client.get(f"{_resolve_v1()}/resolve/{uid}")
            r2 = await client.get(f"{_resolve_v1()}/resolve/{uid}")
            assert r1.status_code == 200, r1.text
            assert r2.status_code == 200, r2.text
            pr1 = r1.json()["payment_request"]
            pr2 = r2.json()["payment_request"]
            assert pr1["uid"] == pr2["uid"] == uid
            assert pr1["public_ref"] == pr2["public_ref"]
            assert pr1["original_public_ref"] == pr2["original_public_ref"]
            s1 = _any_slot_for_did(pr1["commissioners"], other.did)
            s2 = _any_slot_for_did(pr2["commissioners"], other.did)
            assert s1.get("alias_public_ref") == s2.get("alias_public_ref") == pr2["public_ref"]
        finally:
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=owner.did,
            )


@pytest.mark.asyncio
async def test_resolve_payment_request_other_user_uid_then_alias_same_view(main_app_simple_resolve):
    """После первого захода по uid посредник может открыть ту же заявку по своему public_ref (алиасу)."""
    app, owner, other, _acc = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "CHF",
            "amount": "500",
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
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        uid = c.json()["payment_request"]["uid"]
        pub_owner = c.json()["payment_request"]["public_ref"]

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        try:
            r_uid = await client.get(f"{_resolve_v1()}/resolve/{uid}")
            assert r_uid.status_code == 200, r_uid.text
            pr_u = r_uid.json()["payment_request"]
            alias = _any_slot_for_did(pr_u["commissioners"], other.did).get("alias_public_ref")
            assert alias and len(alias) >= 8
            assert pr_u["public_ref"] == alias

            r_alias = await client.get(f"{_resolve_v1()}/resolve/{alias}")
            assert r_alias.status_code == 200, r_alias.text
            pr_a = r_alias.json()["payment_request"]
            assert pr_a["uid"] == uid
            assert pr_a["public_ref"] == alias
            assert pr_a["original_public_ref"] == pub_owner
            assert _any_slot_for_did(pr_a["commissioners"], other.did).get("alias_public_ref") == alias
        finally:
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=owner.did,
            )


@pytest.mark.asyncio
async def test_resolve_not_found_404(main_app_simple_resolve):
    app, _owner, _other, _acc = main_app_simple_resolve
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        r = await client.get(
            f"{_resolve_v1()}/resolve/nonexistent_uid_xxxxxxxx"
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_resolve_payment_request_wrong_arbiter_404(main_app_simple_resolve):
    """Заявка с другим arbiter_did не отдаётся в чужом arbiter_space_did path."""
    app, _owner, _other, _acc = main_app_simple_resolve
    wrong_prefix = f"/v1/arbiter/{quote('did:peer:other_arbiter_context', safe='')}"
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "USD",
            "amount": "10",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "1",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        uid = c.json()["payment_request"]["uid"]
        r = await client.get(f"{wrong_prefix}/resolve/{uid}")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_resolve_deal_only(test_db, test_redis, test_settings):
    """Сделка по uid — вторая ветка resolver (без проверки участников)."""
    owner = WalletUser(
        nickname="simple_resolve_deal_space",
        wallet_address=_OWNER_TRON,
        blockchain="tron",
        did="did:tron:deal_resolve_owner",
    )
    test_db.add(owner)
    await test_db.commit()
    await test_db.refresh(owner)

    test_db.add(
        Wallet(
            name="arb_deal_resolve",
            encrypted_mnemonic="enc",
            role="arbiter",
            tron_address="TArbDealResolve2222222222222222",
            ethereum_address="0xcccccccccccccccccccccccccccccccccccccccc",
            owner_did="did:peer:deal_resolve_arb",
        )
    )

    deal_uid = "SimpleResolveDealUidXYZ01"
    test_db.add(
        Deal(
            uid=deal_uid,
            sender_did="did:s:1",
            receiver_did="did:r:1",
            arbiter_did="did:peer:deal_resolve_arb",
            label="Resolve test deal",
            status="wait_deposit",
        )
    )
    await test_db.commit()

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

    async def override_current_user():
        return UserInfo(
            standard="tron",
            wallet_address=_OWNER_TRON,
            did=owner.did,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_wallet_user] = override_current_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            deal_arb_prefix = f"/v1/arbiter/{quote('did:peer:deal_resolve_arb', safe='')}"
            r = await client.get(f"{deal_arb_prefix}/resolve/{deal_uid}")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["kind"] == "deal_only"
            assert body["deal"]["uid"] == deal_uid
            assert body["deal"]["label"] == "Resolve test deal"
            assert body["payment_request"] is None
            assert body["viewer_did"] == owner.did
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resell_owner_forbidden_400(main_app_simple_resolve):
    app, owner, _other, _acc = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "USD",
            "amount": "50",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "5",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        uid = c.json()["payment_request"]["uid"]
        r = await client.post(
            f"{_resolve_v1()}/payment-requests/{uid}/resell",
            json={},
        )
        assert r.status_code == 400
        assert "перепродаж" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_resell_percent_below_min_400(main_app_simple_resolve):
    app, owner, other, _acc = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "USD",
            "amount": "40",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "4",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        uid = c.json()["payment_request"]["uid"]
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        try:
            r = await client.post(
                f"{_resolve_v1()}/payment-requests/{uid}/resell",
                json={"intermediary_percent": "0.05"},
            )
            assert r.status_code == 400
            assert "0.1" in r.json().get("detail", "") or "процент" in r.json().get("detail", "").lower()
        finally:
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=owner.did,
            )


@pytest.mark.asyncio
async def test_resell_other_user_sets_resell_slot(main_app_simple_resolve):
    app, owner, other, acceptor = main_app_simple_resolve
    payload = {
        "direction": "fiat_to_stable",
        "primary_leg": {
            "asset_type": "fiat",
            "code": "GBP",
            "amount": "200",
            "side": "give",
        },
        "counter_leg": {
            "asset_type": "stable",
            "code": "USDT",
            "amount": "10",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        uid = c.json()["payment_request"]["uid"]

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        try:
            pub_owner = c.json()["payment_request"]["public_ref"]
            r = await client.post(
                f"{_resolve_v1()}/payment-requests/{uid}/resell",
                json={"intermediary_percent": "0.5"},
            )
            assert r.status_code == 200, r.text
            pr = r.json()["payment_request"]
            mid = _intermediary_slot_for_did(pr["commissioners"], other.did)
            assert mid["commission"]["kind"] == "percent"
            assert mid["commission"]["value"] == "0.5"
            alias = mid.get("alias_public_ref")
            assert alias and len(alias) >= 8
            assert pr["public_ref"] == alias
            assert pr["original_public_ref"] == pub_owner
            assert mid["parent_id"] == _expected_intermediary_parent_id(
                pr["commissioners"], pub_owner
            )

            ra = await client.get(f"{_resolve_v1()}/resolve/{alias}")
            assert ra.status_code == 200
            assert ra.json()["payment_request"]["uid"] == uid

            r2 = await client.post(
                f"{_resolve_v1()}/payment-requests/{uid}/resell",
                json={"intermediary_percent": "1"},
            )
            assert r2.status_code == 200
            pr2 = r2.json()["payment_request"]
            mid2 = _intermediary_slot_for_did(pr2["commissioners"], other.did)
            assert mid2["commission"]["value"] == "1"
        finally:
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=owner.did,
            )


@pytest.mark.asyncio
async def test_resolve_commissioner_alias_does_not_auto_resell_acceptor(main_app_simple_resolve):
    """Acceptor, открывший commissioner alias, не должен становиться intermediary автоматически."""
    app, owner, other, acceptor = main_app_simple_resolve
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
            "amount": "100",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        uid = c.json()["payment_request"]["uid"]

        # other user becomes intermediary via explicit resell (gets alias)
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        r = await client.post(
            f"{_resolve_v1()}/payment-requests/{uid}/resell",
            json={"intermediary_percent": "0.5"},
        )
        assert r.status_code == 200, r.text
        pr = r.json()["payment_request"]
        mid = _intermediary_slot_for_did(pr["commissioners"], other.did)
        alias = mid.get("alias_public_ref")
        assert alias

        # acceptor opens alias: should not auto-create intermediary slot
        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=acceptor.wallet_address,
            did=acceptor.did,
        )
        ra = await client.get(f"{_resolve_v1()}/resolve/{alias}")
        assert ra.status_code == 200, ra.text
        pr_acc = ra.json()["payment_request"]
        # Сервер создаёт participant слот и отдаёт персональный alias (а не исходный сегмент ссылки).
        slot_acc = _any_slot_for_did(pr_acc["commissioners"], acceptor.did)
        assert slot_acc.get("role") == "participant"
        assert slot_acc.get("commission") is None
        assert pr_acc["public_ref"] == slot_acc.get("alias_public_ref")
        assert pr_acc["public_ref"] != alias
        with pytest.raises(AssertionError):
            _intermediary_slot_for_did(pr_acc["commissioners"], acceptor.did)


@pytest.mark.asyncio
async def test_viewer_role_toggle_preserves_commission(main_app_simple_resolve):
    """
    Toggle viewer role should not clear commission for the same segment/alias.

    Flow:
    - other resolves uid -> participant slot (no commission, has alias)
    - set role intermediary -> default 0.5%
    - resell to 0.8%
    - set role counterparty -> commission must remain 0.8 (but ignored in calc)
    - set role intermediary -> commission must still be 0.8
    """
    app, owner, other, _acceptor = main_app_simple_resolve
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
            "amount": "100",
            "side": "receive",
        },
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        c = await client.post(_resolve_v1() + "/payment-requests", json=payload)
        assert c.status_code == 201, c.text
        uid = c.json()["payment_request"]["uid"]

        app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
            standard="tron",
            wallet_address=_OTHER_TRON,
            did=other.did,
        )
        try:
            r0 = await client.get(f"{_resolve_v1()}/resolve/{uid}")
            assert r0.status_code == 200, r0.text
            pr0 = r0.json()["payment_request"]
            slot0 = _any_slot_for_did(pr0["commissioners"], other.did)
            assert slot0.get("role") == "participant"
            assert slot0.get("commission") is None
            alias = slot0.get("alias_public_ref")
            assert alias

            # choose intermediary -> default 0.5
            vr1 = await client.post(
                f"{_resolve_v1()}/payment-requests/{pr0['pk']}/viewer-role",
                json={"role": "intermediary"},
            )
            assert vr1.status_code == 200, vr1.text
            pr1 = vr1.json()["payment_request"]
            mid1 = _intermediary_slot_for_did(pr1["commissioners"], other.did)
            assert mid1["commission"]["kind"] == "percent"
            assert mid1["commission"]["value"] == "0.5"
            assert mid1.get("alias_public_ref") == alias

            # resell -> 0.8
            rs = await client.post(
                f"{_resolve_v1()}/payment-requests/{uid}/resell",
                json={"intermediary_percent": "0.8"},
            )
            assert rs.status_code == 200, rs.text
            pr2 = rs.json()["payment_request"]
            mid2 = _intermediary_slot_for_did(pr2["commissioners"], other.did)
            assert mid2["commission"]["value"] == "0.8"

            # switch to counterparty: commission must stay 0.8
            vr2 = await client.post(
                f"{_resolve_v1()}/payment-requests/{pr0['pk']}/viewer-role",
                json={"role": "counterparty"},
            )
            assert vr2.status_code == 200, vr2.text
            pr3 = vr2.json()["payment_request"]
            slot3 = _any_slot_for_did(pr3["commissioners"], other.did)
            assert slot3.get("role") == "counterparty"
            assert slot3.get("commission", {}).get("value") == "0.8"

            # back to intermediary: still 0.8
            vr3 = await client.post(
                f"{_resolve_v1()}/payment-requests/{pr0['pk']}/viewer-role",
                json={"role": "intermediary"},
            )
            assert vr3.status_code == 200, vr3.text
            pr4 = vr3.json()["payment_request"]
            mid4 = _intermediary_slot_for_did(pr4["commissioners"], other.did)
            assert mid4["commission"]["value"] == "0.8"
        finally:
            app.dependency_overrides[get_current_wallet_user] = lambda: UserInfo(
                standard="tron",
                wallet_address=_OWNER_TRON,
                did=owner.did,
            )
