"""
Router для Admin API: логин (password/TRON), пароль, TRON-адреса.
Ориентир: garantex routers/admin.py. Использует существующий AdminService.
"""
from datetime import datetime, timedelta

import jwt

from fastapi import APIRouter, Depends, HTTPException, status

from services.admin import AdminService
from services.tron_auth import TronAuth
from web.endpoints.dependencies import (
    ADMIN_JWT_ALGORITHM,
    AdminDepends,
    AdminServiceDep,
    AppSettings,
    RequireAdminDepends,
    TronAuthDep,
)
from web.endpoints.v1.schemas.admin import (
    AddTronAddressRequest,
    AdminInfoResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminTronNonceRequest,
    AdminTronNonceResponse,
    AdminTronVerifyRequest,
    ChangePasswordRequest,
    ChangeResponse,
    SetPasswordRequest,
    ToggleTronAddressRequest,
    TronAddressItem,
    TronAddressList,
    UpdateTronAddressRequest,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _encode_admin_jwt(secret: str, payload: dict) -> str:
    """Кодирует JWT для админа (HS256, 24h)."""
    now = datetime.utcnow()
    payload.setdefault("exp", now + timedelta(hours=24))
    payload.setdefault("iat", now)
    return jwt.encode(payload, secret, algorithm=ADMIN_JWT_ALGORITHM)


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    request: AdminLoginRequest,
    admin_service: AdminServiceDep,
    settings: AppSettings,
):
    """
    Вход админа по логину и паролю. Возвращает JWT.
    """
    admin = await admin_service.verify_password_auth(
        request.username,
        request.password,
    )
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = _encode_admin_jwt(
        settings.secret.get_secret_value(),
        {"admin": True, "username": admin.username},
    )
    return AdminLoginResponse(
        success=True,
        token=token,
        message="Login successful",
    )


@router.post("/tron/nonce", response_model=AdminTronNonceResponse)
async def admin_tron_nonce(
    request: AdminTronNonceRequest,
    admin_service: AdminServiceDep,
    tron_auth: TronAuthDep,
):
    """
    Nonce для TRON-подписи. Адрес должен быть в whitelist.
    """
    is_whitelisted = await admin_service.verify_tron_auth(request.tron_address)
    if not is_whitelisted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TRON address not authorized for admin access",
        )
    nonce = await tron_auth.get_nonce(request.tron_address)
    message = f"Please sign this message to authenticate:\n\nNonce: {nonce}"
    return AdminTronNonceResponse(nonce=nonce, message=message)


@router.post("/tron/verify", response_model=AdminLoginResponse)
async def admin_tron_verify(
    request: AdminTronVerifyRequest,
    admin_service: AdminServiceDep,
    tron_auth: TronAuthDep,
    settings: AppSettings,
):
    """
    Верификация TRON-подписи и выдача JWT админа.
    """
    is_whitelisted = await admin_service.verify_tron_auth(request.tron_address)
    if not is_whitelisted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TRON address not authorized for admin access",
        )
    is_valid = tron_auth.verify_signature(
        request.tron_address,
        request.signature,
        request.message,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    payload = {
        "admin": True,
        "tron_address": request.tron_address,
        "blockchain": "tron",
    }
    token = _encode_admin_jwt(settings.secret.get_secret_value(), payload)
    return AdminLoginResponse(
        success=True,
        token=token,
        message="Authentication successful",
    )


@router.post("/logout")
async def admin_logout():
    """
    Выход. JWT stateless — клиент удаляет токен.
    """
    return {"success": True, "message": "Logged out successfully"}


@router.post("/set-password", response_model=ChangeResponse)
async def set_admin_password(
    request: SetPasswordRequest,
    admin_service: AdminServiceDep,
    settings: AppSettings,
    admin: AdminDepends,
):
    """
    Установка/обновление пароля админа.
    Если нода уже инициализирована — требуется авторизация.
    """
    if settings.is_node_initialized and admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
        )
    try:
        await admin_service.set_password(request.username, request.password)
        return ChangeResponse(
            success=True,
            message="Admin password configured successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error configuring password: {str(e)}",
        )


@router.get("/info", response_model=AdminInfoResponse)
async def get_admin_info(
    admin_service: AdminServiceDep,
    _admin: RequireAdminDepends,
):
    """
    Информация об админе. Требует авторизации.
    """
    admin = await admin_service.get_admin()
    if not admin:
        raise HTTPException(
            status_code=404,
            detail="Admin not configured",
        )
    addresses = await admin_service.get_tron_addresses(active_only=True)
    return AdminInfoResponse(
        id=admin.id,
        has_password=bool(admin.username and admin.password_hash),
        username=admin.username,
        tron_addresses_count=len(addresses),
        created_at=admin.created_at,
        updated_at=admin.updated_at,
    )


@router.post("/change-password", response_model=ChangeResponse)
async def change_admin_password(
    request: ChangePasswordRequest,
    admin_service: AdminServiceDep,
    _admin: RequireAdminDepends,
):
    """
    Смена пароля. Требует авторизации и текущего пароля.
    """
    try:
        await admin_service.change_password(
            request.old_password,
            request.new_password,
        )
        return ChangeResponse(
            success=True,
            message="Password changed successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error changing password: {str(e)}",
        )


@router.delete("/password", response_model=ChangeResponse)
async def remove_admin_password(
    admin_service: AdminServiceDep,
    _admin: RequireAdminDepends,
):
    """
    Удаление парольной авторизации (должен остаться хотя бы один TRON).
    """
    try:
        await admin_service.remove_password()
        return ChangeResponse(
            success=True,
            message="Password removed successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error removing password: {str(e)}",
        )


@router.get("/tron-addresses", response_model=TronAddressList)
async def get_tron_addresses(
    active_only: bool = True,
    admin_service: AdminServiceDep = None,
    _admin: RequireAdminDepends = None,
):
    """
    Список TRON-адресов админа. Требует авторизации.
    """
    addresses = await admin_service.get_tron_addresses(active_only=active_only)
    items = [
        TronAddressItem(
            id=addr.id,
            tron_address=addr.tron_address,
            label=addr.label,
            is_active=addr.is_active,
            created_at=addr.created_at,
            updated_at=addr.updated_at,
        )
        for addr in addresses
    ]
    return TronAddressList(addresses=items)


@router.post("/tron-addresses", response_model=ChangeResponse)
async def add_tron_address(
    request: AddTronAddressRequest,
    admin_service: AdminServiceDep,
    settings: AppSettings,
    admin: AdminDepends,
):
    """
    Добавление TRON-адреса в whitelist.
    Если нода уже инициализирована — требуется авторизация.
    """
    if settings.is_node_initialized and admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
        )
    try:
        await admin_service.add_tron_address(
            request.tron_address,
            label=request.label,
        )
        return ChangeResponse(
            success=True,
            message="TRON address added successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding TRON address: {str(e)}",
        )


@router.put("/tron-addresses/{tron_id}", response_model=ChangeResponse)
async def update_tron_address(
    tron_id: int,
    request: UpdateTronAddressRequest,
    admin_service: AdminServiceDep,
    _admin: RequireAdminDepends,
):
    """
    Обновление TRON-адреса или метки. Требует авторизации.
    """
    try:
        await admin_service.update_tron_address(
            tron_id,
            new_address=request.tron_address,
            new_label=request.label,
        )
        return ChangeResponse(
            success=True,
            message="TRON address updated successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400 if "not found" not in str(e).lower() else 404,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating TRON address: {str(e)}",
        )


@router.delete("/tron-addresses/{tron_id}", response_model=ChangeResponse)
async def delete_tron_address(
    tron_id: int,
    admin_service: AdminServiceDep,
    _admin: RequireAdminDepends,
):
    """
    Удаление TRON-адреса из whitelist. Требует авторизации.
    """
    try:
        await admin_service.delete_tron_address(tron_id)
        return ChangeResponse(
            success=True,
            message="TRON address deleted successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting TRON address: {str(e)}",
        )


@router.patch("/tron-addresses/{tron_id}/toggle", response_model=ChangeResponse)
async def toggle_tron_address(
    tron_id: int,
    request: ToggleTronAddressRequest,
    admin_service: AdminServiceDep,
    _admin: RequireAdminDepends,
):
    """
    Включение/выключение TRON-адреса. Требует авторизации.
    """
    try:
        await admin_service.toggle_tron_address(tron_id, request.is_active)
        return ChangeResponse(
            success=True,
            message=f"TRON address {'activated' if request.is_active else 'deactivated'} successfully",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400 if "not found" not in str(e).lower() else 404,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error toggling TRON address: {str(e)}",
        )
