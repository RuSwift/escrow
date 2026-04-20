"""
Роутер Web3/TRON авторизации через кошельки.
Ориентир: https://github.com/RuSwift/garantex/blob/main/routers/auth.py
"""
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from services.tron_auth import JWT_EXP_SEC
from web.endpoints.dependencies import (
    MAIN_AUTH_TOKEN_COOKIE,
    CurrentTronUser,
    CurrentWeb3User,
    UserInfo,
    TronAuthDep,
    WalletUserServiceDep,
    Web3AuthDep,
)
from sqlalchemy import select, func

from db.models import PrimaryWallet, WalletUser
from web.endpoints.v1.schemas.auth import (
    AuthResponse,
    EnsureSpaceResponse,
    InitRequest,
    InitResponse,
    NonceRequest,
    NonceResponse,
    VerifyRequest,
)

router = APIRouter(prefix="/auth", tags=["Авторизация"])

# --- Ethereum ---


@router.post("/nonce", response_model=NonceResponse)
async def get_nonce(
    request: NonceRequest,
    web3_auth: Web3AuthDep,
):
    """
    Получить nonce для авторизации через Web3 кошелёк (Ethereum).
    Поддерживаются MetaMask, TrustWallet, WalletConnect.
    """
    wallet_address = request.wallet_address.strip()
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid wallet address format",
        )
    nonce = await web3_auth.get_nonce(wallet_address)
    message = f"Please sign this message to authenticate:\n\nNonce: {nonce}"
    return NonceResponse(nonce=nonce, message=message)


@router.post("/verify", response_model=AuthResponse)
async def verify_signature(
    request: VerifyRequest,
    wallet_service: WalletUserServiceDep,
    web3_auth: Web3AuthDep,
):
    """Проверить подпись и получить JWT токен (Ethereum)."""
    wallet_address = request.wallet_address.strip().lower()
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid wallet address format",
        )
    if request.message is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message is required for verification",
        )
    if not web3_auth.verify_signature(
        wallet_address=wallet_address,
        signature=request.signature,
        message=request.message,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    user = await wallet_service.get_by_wallet_address(wallet_address)
    if not user:
        nickname = f"User_{wallet_address[:8]}"
        try:
            await wallet_service.create_user(
                wallet_address=wallet_address,
                blockchain="ethereum",
                nickname=nickname,
            )
        except ValueError:
            user = await wallet_service.get_by_wallet_address(wallet_address)
    token = web3_auth.generate_jwt_token(wallet_address)
    return AuthResponse(token=token, wallet_address=wallet_address)


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: CurrentWeb3User,
):
    """Информация о текущем авторизованном пользователе (Ethereum)."""
    return current_user


# --- TRON ---


@router.post("/tron/nonce", response_model=NonceResponse)
async def get_tron_nonce(
    request: NonceRequest,
    tron_auth: TronAuthDep,
):
    """Получить nonce для авторизации через TRON кошелёк (TronLink и др.)."""
    wallet_address = request.wallet_address.strip()
    if not tron_auth.validate_tron_address(wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TRON address format. Address must start with 'T' and be 34 characters long.",
        )
    nonce = await tron_auth.get_nonce(wallet_address)
    message = f"Please sign this message to authenticate:\n\nNonce: {nonce}"
    return NonceResponse(nonce=nonce, message=message)


@router.post("/tron/verify")
async def verify_tron_signature(
    request: Request,
    body: VerifyRequest,
    wallet_service: WalletUserServiceDep,
    tron_auth: TronAuthDep,
):
    """Проверить TRON подпись и получить JWT токен. Устанавливает cookie для перехода на /{space}."""
    wallet_address = body.wallet_address.strip()
    if not tron_auth.validate_tron_address(wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TRON address format",
        )
    if body.message is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message is required for verification",
        )
    if not tron_auth.verify_signature(
        wallet_address=wallet_address,
        signature=body.signature,
        message=body.message,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    spaces = await wallet_service.get_spaces_for_address(wallet_address, "tron")
    main_user = await wallet_service.get_by_wallet_address(wallet_address)
    own_space = main_user.nickname if main_user else None
    token = tron_auth.generate_jwt_token(wallet_address)
    host = (request.base_url.hostname or "").lower()
    secure = host not in ("localhost", "127.0.0.1")
    content = {
        "token": token,
        "wallet_address": wallet_address,
        "spaces": spaces,
        "own_space": own_space,
    }
    response = JSONResponse(content=content)
    response.set_cookie(
        key=MAIN_AUTH_TOKEN_COOKIE,  # from dependencies
        value=token,
        httponly=True,
        max_age=JWT_EXP_SEC,
        path="/",
        samesite="lax",
        secure=secure,
    )
    return response


@router.post("/logout")
async def logout_clear_cookie():
    """Сбрасывает cookie авторизации (для перехода на /{space}). Клиент также очищает localStorage."""
    response = JSONResponse(content={})
    response.delete_cookie(key=MAIN_AUTH_TOKEN_COOKIE, path="/")
    return response


@router.post("/tron/init", response_model=InitResponse)
async def init_tron_user(
    request: InitRequest,
    current_user: CurrentTronUser,
    wallet_service: WalletUserServiceDep,
):
    """
    Инициация нового WalletUser (свой space), если для адреса ещё нет строки владельца.
    Участие в чужих space как субаккаунт не мешает: блокируем только при существующем WalletUser с этим wallet_address.
    """
    wallet_address = current_user.wallet_address
    if await wallet_service.get_by_wallet_address(wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet already has its own space; choose it instead of init",
        )
    nickname = request.nickname.strip()
    try:
        await wallet_service.create_user_for_init(
            wallet_address=wallet_address,
            blockchain="tron",
            nickname=nickname,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return InitResponse(space=nickname)


@router.post("/tron/ensure-space", response_model=EnsureSpaceResponse)
async def ensure_tron_space(
    current_user: CurrentTronUser,
    wallet_service: WalletUserServiceDep,
):
    """
    Гарантирует, что для текущего TRON-адреса есть выбранный space:
    - если spaces не пусты: выбирает space, где primary wallet совпадает с адресом
      (PrimaryWallet.address или fallback на WalletUser.wallet_address).
    - если spaces пусты: создаёт новый space с nickname вида simple_<first6> (с суффиксом при коллизии).
    """
    wallet_address = (current_user.wallet_address or "").strip()
    spaces = await wallet_service.get_spaces_for_address(wallet_address, "tron")

    # 1) Если spaces уже есть — пытаемся найти primary-match
    if spaces:
        # stable order for fallback
        sorted_spaces = sorted([s for s in spaces if s])

        stmt = (
            select(WalletUser.nickname)
            .select_from(WalletUser)
            .outerjoin(PrimaryWallet, PrimaryWallet.wallet_user_id == WalletUser.id)
            .where(WalletUser.nickname.in_(sorted_spaces))
            .where(func.coalesce(PrimaryWallet.address, WalletUser.wallet_address) == wallet_address)
            .order_by(WalletUser.nickname.asc())
            .limit(1)
        )
        res = await wallet_service._session.execute(stmt)  # service owns session; private but consistent across codebase
        match = res.scalar_one_or_none()
        if match:
            return EnsureSpaceResponse(space=match, created=False, primary_matched=True)
        return EnsureSpaceResponse(space=sorted_spaces[0], created=False, primary_matched=False)

    # 2) Нет spaces — создаём новый nickname автоматически
    prefix = "simple"
    base = wallet_address[:6] if wallet_address else "anon"
    base_nick = f"{prefix}_{base}"

    # try base, then base_2, base_3 ...
    created_nick = None
    for i in range(1, 50):
        nick = base_nick if i == 1 else f"{base_nick}_{i}"
        existing = await wallet_service.get_by_nickname(nick)
        if existing:
            continue
        try:
            await wallet_service.create_user_for_init(
                wallet_address=wallet_address,
                blockchain="tron",
                nickname=nick,
            )
            created_nick = nick
            break
        except ValueError:
            # Nickname could be taken concurrently; try next suffix
            continue

    if not created_nick:
        raise HTTPException(status_code=500, detail="Failed to allocate space nickname")

    return EnsureSpaceResponse(space=created_nick, created=True, primary_matched=False)


@router.get("/tron/me", response_model=UserInfo)
async def get_current_tron_user_info(
    current_user: CurrentTronUser,
    wallet_service: WalletUserServiceDep,
    x_space: str | None = Header(default=None, alias="X-Space"),
):
    """Информация о текущем TRON-пользователе. Опционально X-Space: возвращает spaces и space_nickname."""
    wallet_address = current_user.wallet_address
    spaces = await wallet_service.get_spaces_for_address(wallet_address, "tron")
    main_user = await wallet_service.get_by_wallet_address(wallet_address)
    own_space = main_user.nickname if main_user else None
    space_nickname = None
    if x_space and (x_space.strip() in spaces):
        space_nickname = x_space.strip()
    return UserInfo(
        standard=current_user.standard,
        wallet_address=wallet_address,
        did=current_user.did,
        space_nickname=space_nickname,
        spaces=spaces,
        own_space=own_space,
    )
