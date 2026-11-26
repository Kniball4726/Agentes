"""Dependencias FastAPI y fachada modular de autenticación/almacenes para la API REST."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..auth import UserStore
from .stores import (
    get_order_store,
    get_product_store,
    get_stock_manager,
    get_user_store,
    reset_api_stores,
)
from .tokens import (
    DOC_TOKEN_TTL_SECONDS,
    SESSION_ABSOLUTE_TTL_SECONDS,
    SESSION_TTL_SECONDS,
    _doc_tokens,
    _hash_token,
    _limpiar_doc_tokens_expirados,
    _limpiar_sesiones_expiradas,
    _normalizar_recurso_doc,
    _on_user_store_session_revocation,
    _sesion_expirada,
    _sesiones_activas,
    crear_sesion,
    crear_token_documento,
    resolver_sesion_activa,
    revocar_sesion,
    validar_token_documento,
    validar_y_sincronizar_usuario as _validar_y_sincronizar_usuario,
)

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user_store: UserStore = Depends(get_user_store),
) -> Dict[str, Any]:
    """Valida el token enviado por encabezado Bearer, X-Auth-Token o X-API-Key externa."""
    if x_api_key and x_api_key.strip():
        api_data = user_store.validate_api_key(x_api_key.strip())
        if not api_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-API-Key inválida o revocada.",
            )
        ahora = time.time()
        return {
            "user_id": 0,
            "username": f"api:{api_data['client_name']}",
            "role": api_data["role"],
            "nombre": f"API ({api_data['client_name']})",
            "email": "",
            "is_api_key": True,
            "created_at": ahora,
            "last_active": ahora,
        }

    token: Optional[str] = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif x_token:
        token = x_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token de autenticación (Header Authorization: Bearer <token> o X-Auth-Token)",
        )

    return resolver_sesion_activa(token, user_store)


async def get_optional_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    user_store: UserStore = Depends(get_user_store),
) -> Optional[Dict[str, Any]]:
    """Devuelve la sesión autenticada si se enviaron credenciales válidas, o None si no hay sesión."""
    if not (auth_header and auth_header.credentials) and not x_token and not (x_api_key and x_api_key.strip()):
        return None
    try:
        return await get_current_user(
            auth_header=auth_header,
            x_token=x_token,
            x_api_key=x_api_key,
            user_store=user_store,
        )
    except HTTPException:
        return None


async def require_document_access(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    dt: Optional[str] = Query(None, alias="dt", description="Token efímero acotado al documento"),
    user_store: UserStore = Depends(get_user_store),
) -> Dict[str, Any]:
    """Exige sesión API válida o token efímero `dt` emitido para el recurso solicitado."""
    if (auth_header and auth_header.credentials) or x_token or (x_api_key and x_api_key.strip()):
        return await get_current_user(
            auth_header=auth_header,
            x_token=x_token,
            x_api_key=x_api_key,
            user_store=user_store,
        )

    if dt:
        recurso_req = (
            request.query_params.get("p")
            or request.path_params.get("nombre_archivo")
            or Path(request.url.path).name
        )
        doc_sesion = validar_token_documento(dt, recurso_solicitado=recurso_req, user_store=user_store)
        if doc_sesion:
            return doc_sesion
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de documento inválido, expirado o no autorizado para este archivo.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Se requiere autenticación para acceder a documentos o informes.",
    )


def require_roles(*roles_permitidos: str):
    """Filtro de autorización por rol de usuario."""
    async def _role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        rol = user.get("role", "")
        if rol == "master":
            return user
        if rol not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Se requiere uno de los siguientes roles: {', '.join(roles_permitidos)}",
            )
        return user
    return _role_checker


__all__ = [
    "DOC_TOKEN_TTL_SECONDS",
    "SESSION_ABSOLUTE_TTL_SECONDS",
    "SESSION_TTL_SECONDS",
    "_doc_tokens",
    "_hash_token",
    "_limpiar_doc_tokens_expirados",
    "_limpiar_sesiones_expiradas",
    "_normalizar_recurso_doc",
    "_on_user_store_session_revocation",
    "_sesion_expirada",
    "_sesiones_activas",
    "_validar_y_sincronizar_usuario",
    "crear_sesion",
    "crear_token_documento",
    "get_current_user",
    "get_optional_current_user",
    "get_order_store",
    "get_product_store",
    "get_stock_manager",
    "get_user_store",
    "require_document_access",
    "require_roles",
    "reset_api_stores",
    "revocar_sesion",
    "security_bearer",
    "validar_token_documento",
]
