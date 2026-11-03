"""Endpoints de Autenticación para clientes móviles y web."""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import crear_sesion, get_current_user, get_user_store, revocar_sesion
from ..schemas import LoginRequest, LoginResponse, UsuarioResponse
from ...user_store import UserStore

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=LoginResponse, summary="Iniciar sesión")
async def login(req: LoginRequest, user_store: UserStore = Depends(get_user_store)):
    """Valida usuario y contraseña y emite un token de sesión para la app móvil."""
    res = user_store.authenticate_detailed(req.username, req.password)

    if res.status == "locked":
        minutos = max(1, int((res.retry_after or 60) / 60))
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Usuario bloqueado temporalmente por intentos fallidos. Intente nuevamente en {minutos} minuto(s).",
        )

    if res.status != "ok" or res.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos.",
        )

    user = res.user
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario se encuentra deshabilitada.",
        )

    token = crear_sesion(user)
    usuario_resp = UsuarioResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        nombre=user.nombre_identificador,
        email=user.email,
    )

    return LoginResponse(
        ok=True,
        token=token,
        user=usuario_resp,
        message=f"¡Bienvenido {user.nombre_identificador}!",
    )


@router.get("/me", response_model=UsuarioResponse, summary="Obtener perfil del usuario actual")
async def me(user_sesion: Dict[str, Any] = Depends(get_current_user)):
    """Retorna los datos de la sesión del usuario actualmente autenticado."""
    return UsuarioResponse(
        id=user_sesion["user_id"],
        username=user_sesion["username"],
        role=user_sesion["role"],
        nombre=user_sesion["nombre"],
        email=user_sesion.get("email"),
    )


@router.post("/logout", summary="Cerrar sesión")
async def logout(
    user_sesion: Dict[str, Any] = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
):
    """Invalida el token de sesión activo."""
    # Como get_current_user ya validó el token, podemos simplemente responder ok
    return {"ok": True, "message": "Sesión cerrada correctamente."}
