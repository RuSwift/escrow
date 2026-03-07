"""
Роутер Web3/TRON авторизации через кошельки.
Ориентир: https://github.com/RuSwift/garantex/blob/main/routers/auth.py
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from services.tron_auth import TronAuth
from services.web3_auth import Web3Auth
from web.endpoints.dependencies import (
    TronAuthDep,
    WalletUserServiceDep,
    Web3AuthDep,
    get_tron_auth,
    get_web3_auth,
)

router = APIRouter(prefix="/auth", tags=["Авторизация"])

# --- Схемы запросов/ответов ---


class NonceRequest(BaseModel):
    """Запрос nonce для подписи."""

    wallet_address: str = Field(..., description="Адрес кошелька пользователя")


class NonceResponse(BaseModel):
    """Ответ с nonce и сообщением для подписи."""

    nonce: str = Field(..., description="Nonce для подписи")
    message: str = Field(..., description="Сообщение для подписи")


class VerifyRequest(BaseModel):
    """Запрос верификации подписи."""

    wallet_address: str = Field(..., description="Адрес кошелька пользователя")
    signature: str = Field(..., description="Подпись сообщения")
    message: Optional[str] = Field(
        None,
        description="Сообщение (опционально, если отличается от стандартного)",
    )


class AuthResponse(BaseModel):
    """Ответ с JWT и адресом после успешной верификации."""

    token: str = Field(..., description="JWT токен для авторизации")
    wallet_address: str = Field(..., description="Адрес кошелька")


class UserInfo(BaseModel):
    """Информация о текущем пользователе."""

    wallet_address: str = Field(
        ..., description="Адрес кошелька пользователя"
    )


security = HTTPBearer()


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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    web3_auth: Web3Auth = Depends(get_web3_auth),
) -> UserInfo:
    """Зависимость: текущий пользователь из JWT (Ethereum)."""
    token = credentials.credentials
    payload = web3_auth.verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    wallet_address = payload.get("wallet_address")
    if not wallet_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return UserInfo(wallet_address=wallet_address)


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: UserInfo = Depends(get_current_user),
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


@router.post("/tron/verify", response_model=AuthResponse)
async def verify_tron_signature(
    request: VerifyRequest,
    wallet_service: WalletUserServiceDep,
    tron_auth: TronAuthDep,
):
    """Проверить TRON подпись и получить JWT токен."""
    wallet_address = request.wallet_address.strip()
    if not tron_auth.validate_tron_address(wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TRON address format",
        )
    if request.message is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message is required for verification",
        )
    if not tron_auth.verify_signature(
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
        nickname = f"User_{wallet_address[:6]}"
        try:
            await wallet_service.create_user(
                wallet_address=wallet_address,
                blockchain="tron",
                nickname=nickname,
            )
        except ValueError:
            user = await wallet_service.get_by_wallet_address(wallet_address)
    token = tron_auth.generate_jwt_token(wallet_address)
    return AuthResponse(token=token, wallet_address=wallet_address)


async def get_current_tron_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    tron_auth: TronAuth = Depends(get_tron_auth),
) -> UserInfo:
    """Зависимость: текущий TRON-пользователь из JWT."""
    token = credentials.credentials
    payload = tron_auth.verify_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    wallet_address = payload.get("wallet_address")
    if not wallet_address:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    if payload.get("blockchain") != "tron":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: not a TRON token",
        )
    return UserInfo(wallet_address=wallet_address)


@router.get("/tron/me", response_model=UserInfo)
async def get_current_tron_user_info(
    current_user: UserInfo = Depends(get_current_tron_user),
):
    """Информация о текущем TRON-пользователе."""
    return current_user
