"""Dependencias centrales y gestión de sesiones para la API REST de StockAgent."""

from __future__ import annotations

import hashlib
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


# --- Gestión de Sesiones Persistentes y Tokens ---

def _hash_token(raw_token: str) -> str:
    """Calcula el hash SHA-256 de un token para almacenamiento y consulta segura."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def crear_sesion(user: User, store: UserStore | None = None) -> str:
    """Crea una nueva sesión para el usuario, guardándola con hash seguro en SQLite y memoria."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    ahora = time.time()
    sesion_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "nombre": user.nombre or user.username,
        "email": user.email,
        "created_at": ahora,
        "last_active": ahora,
    }

    # 1. Guardar en memoria caché para ultra-alta velocidad
    _sesiones_activas[token_hash] = sesion_data

    # 2. Persistir en SQLite para sobrevivir reinicios de servidor
    try:
        (store or get_user_store()).create_api_session(
            token_hash=token_hash,
            user_id=user.id,
            username=user.username,
            role=user.role,
            nombre=user.nombre or user.username,
            email=user.email,
            created_at=ahora,
            last_active=ahora,
        )
    except Exception:
        pass

    _limpiar_sesiones_expiradas()
    return raw_token


def revocar_sesion(raw_token: str) -> bool:
    """Revoca de forma atómica una sesión activa tanto en memoria como en SQLite."""
    token_hash = _hash_token(raw_token)
    mem_revocada = _sesiones_activas.pop(token_hash, None) is not None
    try:
        db_revocada = get_user_store().revoke_api_session(token_hash)
    except Exception:
        db_revocada = False
    return mem_revocada or db_revocada


def _limpiar_sesiones_expiradas() -> None:
    """Elimina sesiones vencidas de memoria y de la base de datos."""
    ahora = time.time()
    expirados = [
        th for th, data in _sesiones_activas.items()
        if ahora - data.get("last_active", ahora) > SESSION_TTL_SECONDS
    ]
    for th in expirados:
        _sesiones_activas.pop(th, None)

    try:
        get_user_store().cleanup_expired_api_sessions(SESSION_TTL_SECONDS)
    except Exception:
        pass


async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    token_param: Optional[str] = Query(None, alias="token"),
    user_store: UserStore = Depends(get_user_store),
) -> Dict[str, Any]:
    """Valida el token enviado por encabezado Bearer, X-Auth-Token o X-API-Key externa."""
    # 1. Autenticación mediante API Key para integraciones externas (B2B / ERP)
    if x_api_key and x_api_key.strip():
        api_data = user_store.validate_api_key(x_api_key.strip())
        if not api_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-API-Key inválida o revocada.",
            )
        return {
            "user_id": 0,
            "username": f"api:{api_data['client_name']}",
            "role": api_data["role"],
            "nombre": f"API ({api_data['client_name']})",
            "email": "",
            "is_api_key": True,
            "created_at": time.time(),
            "last_active": time.time(),
        }

    # 2. Autenticación mediante token de sesión
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

    token_hash = _hash_token(token)
    sesion = _sesiones_activas.get(token_hash)

    # 3. Si no está en memoria, consultar SQLite (ej: tras reinicio del servidor)
    if not sesion:
        try:
            db_session = user_store.get_api_session(token_hash)
            if db_session:
                ahora = time.time()
                if ahora - db_session["last_active"] <= SESSION_TTL_SECONDS:
                    sesion = db_session
                    _sesiones_activas[token_hash] = sesion
        except Exception:
            pass

    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o sesión expirada. Inicie sesión nuevamente.",
        )

    # Actualizar última actividad
    ahora = time.time()
    sesion["last_active"] = ahora
    try:
        user_store.update_api_session_activity(token_hash, ahora)
    except Exception:
        pass

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
