"""Dependencias centrales y gestión de sesiones para la API REST de StockAgent."""

from __future__ import annotations

import secrets
import time
from typing import Any, Dict, List, Optional
from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..paths import application_root
from ..user_store import User, UserStore
from ..product_store import ProductStore
from ..orders_store import OrderStore
from ..stock_manager import StockManager

# Configuración de sesiones
SESSION_TTL_SECONDS = 24 * 3600  # 24 horas de vigencia por token
_sesiones_activas: Dict[str, Dict[str, Any]] = {}

security_bearer = HTTPBearer(auto_error=False)

# Instancias compartidas singleton (Lazy initialization)
_user_store: Optional[UserStore] = None
_product_store: Optional[ProductStore] = None
_order_store: Optional[OrderStore] = None
_stock_manager: Optional[StockManager] = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        db_path = application_root() / "data" / "usuarios.sqlite3"
        _user_store = UserStore(db_path)
    return _user_store


def get_product_store() -> ProductStore:
    global _product_store
    if _product_store is None:
        db_path = application_root() / "data" / "productos.sqlite3"
        _product_store = ProductStore(db_path)
    return _product_store


def get_order_store() -> OrderStore:
    global _order_store
    if _order_store is None:
        db_path = application_root() / "data" / "pedidos.sqlite3"
        _order_store = OrderStore(db_path)
    return _order_store


def get_stock_manager() -> StockManager:
    global _stock_manager
    if _stock_manager is None:
        excel_path = application_root() / "Descuentos" / "Productos.xlsx"
        _stock_manager = StockManager(excel_path)
    return _stock_manager


# --- Gestión de Sesiones / Tokens ---

def crear_sesion(user: User) -> str:
    """Crea una nueva sesión para el usuario y devuelve el token opaco seguro."""
    token = secrets.token_urlsafe(32)
    ahora = time.time()
    _sesiones_activas[token] = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "nombre": user.nombre or user.username,
        "email": user.email,
        "created_at": ahora,
        "last_active": ahora,
    }
    _limpiar_sesiones_expiradas()
    return token


def revocar_sesion(token: str) -> bool:
    """Revoca una sesión activa existente."""
    return _sesiones_activas.pop(token, None) is not None


def _limpiar_sesiones_expiradas() -> None:
    ahora = time.time()
    expirados = [
        t for t, data in _sesiones_activas.items()
        if ahora - data.get("last_active", ahora) > SESSION_TTL_SECONDS
    ]
    for t in expirados:
        _sesiones_activas.pop(t, None)


async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    token_param: Optional[str] = Query(None, alias="token"),
    user_store: UserStore = Depends(get_user_store),
) -> Dict[str, Any]:
    """Valida el token enviado por encabezado Bearer, X-Auth-Token o parámetro query."""
    token: Optional[str] = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif x_token:
        token = x_token
    elif token_param:
        token = token_param

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere token de autenticación (Header Authorization: Bearer <token> o X-Auth-Token)",
        )

    sesion = _sesiones_activas.get(token)
    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o sesión expirada. Inicie sesión nuevamente.",
        )

    # Actualizar última actividad
    sesion["last_active"] = time.time()
    return sesion


def require_roles(*roles_permitidos: str):
    """Filtro de autorización por rol de usuario."""
    async def _role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        rol = user.get("role", "")
        if rol == "master":  # El rol master tiene acceso total
            return user
        if rol not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Se requiere uno de los siguientes roles: {', '.join(roles_permitidos)}",
            )
        return user
    return _role_checker
