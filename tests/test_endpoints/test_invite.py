"""
API-тесты user flow invite-link: создание ссылки, резолв, nonce, подтверждение подписью.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from db import get_db
from db.models import WalletUser, WalletUserSub
from web.main import create_app
from web.endpoints.dependencies import (
    MAIN_AUTH_TOKEN_COOKIE,
    get_redis,
    get_settings,
    ResolvedSettings,
)

try:
    from tronpy.keys import PrivateKey
except ImportError:
    PrivateKey = None


def _tron_key_and_address(passphrase: bytes):
    if PrivateKey is None:
        pytest.skip("tronpy not installed")
    priv = PrivateKey.from_passphrase(passphrase)
    addr = priv.public_key.to_base58check_address()
    return priv, addr


def _tron_sign_message(priv_key, message: str) -> str:
    return priv_key.sign_msg(message.encode("utf-8")).hex()


@pytest_asyncio.fixture
async def main_app(test_db, test_redis, test_settings):
    """Main app с подменёнными БД, Redis и настройками."""
    app = create_app()

    async def override_get_db():
        yield test_db

    async def override_get_redis():
        yield test_redis

    async def override_get_settings():
        return ResolvedSettings(
            settings=test_settings,
            has_key=False,
            is_admin_configured=False,
            is_node_initialized=False,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_settings] = override_get_settings
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_invite_link_full_flow(main_app, test_db):
    """
    Полный user flow: owner создаёт invite-link -> resolve -> nonce -> confirm подписью.
    После confirm токен потреблён (404), участник is_verified=True.
    """
    owner_priv, owner_addr = _tron_key_and_address(b"invite-test-owner")
    participant_priv, participant_addr = _tron_key_and_address(b"invite-test-participant")

    space_name = "invite_flow_space"
    owner = WalletUser(
        wallet_address=owner_addr,
        blockchain="tron",
        did="did:tron:" + owner_addr,
        nickname=space_name,
    )
    test_db.add(owner)
    await test_db.flush()
    sub = WalletUserSub(
        wallet_user_id=owner.id,
        wallet_address=participant_addr,
        blockchain="tron",
        nickname="participant_nick",
        roles=["reader"],
        is_verified=False,
        is_blocked=False,
    )
    test_db.add(sub)
    await test_db.flush()
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        # 1) Owner: auth (nonce + verify) -> JWT
        nonce_r = await client.post(
            "/v1/auth/tron/nonce",
            json={"wallet_address": owner_addr},
        )
        assert nonce_r.status_code == 200
        message = nonce_r.json()["message"]
        signature = _tron_sign_message(owner_priv, message)
        verify_r = await client.post(
            "/v1/auth/tron/verify",
            json={
                "wallet_address": owner_addr,
                "signature": signature,
                "message": message,
            },
        )
        assert verify_r.status_code == 200
        owner_token = verify_r.json()["token"]
        assert space_name in verify_r.json().get("spaces", [])

        # 2) Owner: create invite-link
        create_r = await client.post(
            f"/v1/spaces/{space_name}/participants/{sub.id}/invite-link",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert create_r.status_code == 200
        body = create_r.json()
        invite_link = body["invite_link"]
        assert "expires_at" in body
        assert "/v/" in invite_link
        token = invite_link.split("/v/")[-1].split("?")[0].rstrip("/")
        assert token

        # 3) Public: resolve invite (no auth)
        get_r = await client.get(f"/v1/invite/{token}")
        assert get_r.status_code == 200
        payload = get_r.json()
        assert payload["space_name"] == space_name
        assert payload["inviter_nickname"] == space_name
        assert payload["wallet_address"] == participant_addr
        assert "reader" in payload["roles"]
        assert payload.get("participant_nickname") == "participant_nick"

        # 4) Public: get nonce for participant address
        nonce_invite_r = await client.post(f"/v1/invite/{token}/nonce")
        assert nonce_invite_r.status_code == 200
        nonce_body = nonce_invite_r.json()
        nonce = nonce_body["nonce"]
        message_to_sign = nonce_body["message"]
        assert nonce and message_to_sign
        assert nonce in message_to_sign

        # 5) Public: confirm with participant's signature
        participant_sig = _tron_sign_message(participant_priv, message_to_sign)
        confirm_r = await client.post(
            f"/v1/invite/{token}/confirm",
            json={"signature": participant_sig},
        )
        assert confirm_r.status_code == 200
        confirm_body = confirm_r.json()
        assert confirm_body["space"] == space_name
        assert confirm_body["redirect_url"] == f"/{space_name}"
        assert confirm_body.get("token")
        set_cookie = confirm_r.headers.get("set-cookie") or confirm_r.headers.get("Set-Cookie") or ""
        assert f"{MAIN_AUTH_TOKEN_COOKIE}=" in set_cookie

        # 6) Token consumed: resolve again -> 404
        get_again_r = await client.get(f"/v1/invite/{token}")
        assert get_again_r.status_code == 404

    # 7) Participant is_verified in DB
    await test_db.refresh(sub)
    assert sub.is_verified is True


@pytest.mark.asyncio
async def test_invite_resolve_invalid_token_404(main_app):
    """GET /v1/invite/{token} и POST nonce/confirm по несуществующему токену возвращают 404."""
    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        r = await client.get("/v1/invite/nonexistent-token-xyz")
        assert r.status_code == 404
        r_nonce = await client.post("/v1/invite/nonexistent-token-xyz/nonce")
        assert r_nonce.status_code == 404
        r_confirm = await client.post(
            "/v1/invite/nonexistent-token-xyz/confirm",
            json={"signature": "deadbeef"},
        )
        assert r_confirm.status_code == 404


@pytest.mark.asyncio
async def test_invite_link_already_verified_400(main_app, test_db):
    """POST invite-link для уже верифицированного участника возвращает 400."""
    owner_priv, owner_addr = _tron_key_and_address(b"invite-owner-verified")
    _, participant_addr = _tron_key_and_address(b"invite-participant-verified")

    space_name = "invite_space_verified"
    owner = WalletUser(
        wallet_address=owner_addr,
        blockchain="tron",
        did="did:tron:" + owner_addr,
        nickname=space_name,
    )
    test_db.add(owner)
    await test_db.flush()
    sub = WalletUserSub(
        wallet_user_id=owner.id,
        wallet_address=participant_addr,
        blockchain="tron",
        roles=["reader"],
        is_verified=True,
        is_blocked=False,
    )
    test_db.add(sub)
    await test_db.flush()
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post("/v1/auth/tron/nonce", json={"wallet_address": owner_addr})
        assert nonce_r.status_code == 200
        msg = nonce_r.json()["message"]
        sig = _tron_sign_message(owner_priv, msg)
        verify_r = await client.post(
            "/v1/auth/tron/verify",
            json={"wallet_address": owner_addr, "signature": sig, "message": msg},
        )
        assert verify_r.status_code == 200
        token = verify_r.json()["token"]

        create_r = await client.post(
            f"/v1/spaces/{space_name}/participants/{sub.id}/invite-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_r.status_code == 400
        assert "already verified" in create_r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_invite_link_non_owner_403(main_app, test_db):
    """POST invite-link от не-владельца спейса возвращает 403."""
    owner_priv, owner_addr = _tron_key_and_address(b"invite-owner-403")
    other_priv, other_addr = _tron_key_and_address(b"invite-other-403")
    _, participant_addr = _tron_key_and_address(b"invite-participant-403")

    space_name = "invite_space_403"
    owner = WalletUser(
        wallet_address=owner_addr,
        blockchain="tron",
        did="did:tron:" + owner_addr,
        nickname=space_name,
    )
    test_db.add(owner)
    await test_db.flush()
    sub = WalletUserSub(
        wallet_user_id=owner.id,
        wallet_address=participant_addr,
        blockchain="tron",
        roles=["reader"],
        is_verified=False,
        is_blocked=False,
    )
    test_db.add(sub)
    other_user = WalletUser(
        wallet_address=other_addr,
        blockchain="tron",
        did="did:tron:" + other_addr,
        nickname="other_user_403",
    )
    test_db.add(other_user)
    await test_db.flush()
    await test_db.commit()

    async with AsyncClient(
        transport=ASGITransport(app=main_app),
        base_url="http://test",
    ) as client:
        nonce_r = await client.post("/v1/auth/tron/nonce", json={"wallet_address": other_addr})
        assert nonce_r.status_code == 200
        msg = nonce_r.json()["message"]
        sig = _tron_sign_message(other_priv, msg)
        verify_r = await client.post(
            "/v1/auth/tron/verify",
            json={"wallet_address": other_addr, "signature": sig, "message": msg},
        )
        assert verify_r.status_code == 200
        token = verify_r.json()["token"]

        create_r = await client.post(
            f"/v1/spaces/{space_name}/participants/{sub.id}/invite-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_r.status_code == 403
        assert "owner" in create_r.json().get("detail", "").lower()
