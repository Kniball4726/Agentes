"""Endpoints de Autenticación para clientes móviles y web."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status

from ..deps import crear_sesion, get_current_user, get_user_store, require_roles, revocar_sesion
from ..schemas import ApiKeyCreateRequest, LoginRequest, LoginResponse, UsuarioResponse
from ...auth import USER_ROLES, UserStore

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Rate limiting en memoria por IP
_RATE_LIMIT_WINDOW = 60.0  # 1 minuto
_MAX_LOGIN_ATTEMPTS_PER_IP = 10
_ip_attempts: Dict[str, List[float]] = defaultdict(list)


def _verificar_rate_limit_ip(ip: str) -> None:
    """Valida que una IP no supere el umbral máximo de intentos por minuto."""
    ahora = time.time()
    intentos = _ip_attempts[ip]
    _ip_attempts[ip] = [t for t in intentos if ahora - t < _RATE_LIMIT_WINDOW]
    if len(_ip_attempts[ip]) >= _MAX_LOGIN_ATTEMPTS_PER_IP:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesión desde esta dirección IP. Por favor espere 1 minuto.",
        )
    _ip_attempts[ip].append(ahora)


@router.post("/login", response_model=LoginResponse, summary="Iniciar sesión")
async def login(
    req: LoginRequest,
    request: Request,
    user_store: UserStore = Depends(get_user_store),
):
    """Valida usuario y contraseña y emite un token de sesión para la app móvil."""
    client_ip = request.client.host if request.client else "unknown"
    _verificar_rate_limit_ip(client_ip)

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
    if getattr(user, "must_change_password", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debe actualizar su contraseña obligatoria desde el panel web/escritorio antes de acceder a la API.",
        )

    token = crear_sesion(user, user_store)
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
        id=int(user_sesion.get("user_id", 0)),
        username=str(user_sesion.get("username", "")),
        role=str(user_sesion.get("role", "")),
        nombre=str(user_sesion.get("nombre", "")),
        email=str(user_sesion.get("email", "")),
    )


@router.post("/logout", summary="Cerrar sesión")
async def logout(
    request: Request,
    user_sesion: Dict[str, Any] = Depends(get_current_user),
):
    """Invalida de forma inmediata el token de sesión actual."""
    auth_h = request.headers.get("Authorization", "")
    token = ""
    if auth_h.startswith("Bearer "):
        token = auth_h[7:].strip()
    elif "X-Auth-Token" in request.headers:
        token = request.headers["X-Auth-Token"].strip()

    if token:
        revocar_sesion(token)

    return {"ok": True, "message": "Sesión cerrada correctamente."}


# --- Endpoints de Gestión de API Keys (B2B / ERP) ---

@router.post("/api-keys", summary="Crear API Key para integración externa (Exclusivo Master)")
async def crear_api_key(
    payload: Optional[ApiKeyCreateRequest] = Body(None),
    client_name: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_roles("master")),
    user_store: UserStore = Depends(get_user_store),
):
    """Genera una nueva API Key para conectar ERPs o scripts externos (acepta JSON body preferentemente)."""
    nombre_cliente = (payload.client_name if payload is not None else (client_name or "")).strip()
    rol_solicitado = (payload.role if payload is not None else (role or "operador")).strip().lower()

    if not nombre_cliente:
        raise HTTPException(status_code=400, detail="Debe indicar el nombre del cliente o sistema externo.")

    if rol_solicitado not in USER_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Rol no válido. Roles permitidos: {', '.join(USER_ROLES)}.",
        )

    raw_key, key_hash = user_store.create_api_key(nombre_cliente, role=rol_solicitado)
    return {
        "ok": True,
        "client_name": nombre_cliente,
        "role": rol_solicitado,
        "api_key": raw_key,
        "message": "Guarde esta clave API en un lugar seguro. No se volverá a mostrar completa.",
    }


@router.get("/api-keys", summary="Listar API Keys registradas (Exclusivo Master)")
async def listar_api_keys(
    user: Dict[str, Any] = Depends(require_roles("master")),
    user_store: UserStore = Depends(get_user_store),
):
    """Lista las claves de integración registradas con su estado y fecha de último uso."""
    keys = user_store.list_api_keys()
    return {"ok": True, "api_keys": keys}


@router.delete("/api-keys/{key_hash}", summary="Revocar API Key (Exclusivo Master)")
async def revocar_api_key(
    key_hash: str,
    user: Dict[str, Any] = Depends(require_roles("master")),
    user_store: UserStore = Depends(get_user_store),
):
    """Revoca el acceso a una clave de integración externa."""
    revocada = user_store.revoke_api_key(key_hash)
    if not revocada:
        raise HTTPException(status_code=404, detail="Clave no encontrada.")
    return {"ok": True, "message": "Clave API revocada exitosamente."}
