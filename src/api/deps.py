"""Dependencias centrales y gestión de sesiones para la API REST de StockAgent."""

from __future__ import annotations

import hashlib
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..auth import User, UserStore
from ..auth.store import register_session_revocation_listener
from ..inventory import StockManager
from ..orders import OrderStore
from ..paths import application_root
from ..products import ProductStore

# Configuración de sesiones
SESSION_TTL_SECONDS = 24 * 3600  # 24 horas de vigencia por token
DOC_TOKEN_TTL_SECONDS = 300  # 5 minutos para tokens efímeros de visor/descarga web
_sesiones_activas: Dict[str, Dict[str, Any]] = {}
_doc_tokens: Dict[str, Dict[str, Any]] = {}


def _on_user_store_session_revocation(
    event: str, user_id: Optional[int], token_hash: Optional[str]
) -> None:
    """Mantiene sincronizada la caché en memoria ante revocaciones en UserStore."""
    if event == "all":
        _sesiones_activas.clear()
        _doc_tokens.clear()
    elif event == "token" and token_hash:
        _sesiones_activas.pop(token_hash, None)
    elif event == "user" and user_id is not None:
        objetivo = int(user_id)
        for th in [k for k, v in _sesiones_activas.items() if int(v.get("user_id", 0) or 0) == objetivo]:
            _sesiones_activas.pop(th, None)
        for dh in [k for k, v in _doc_tokens.items() if int(v.get("user_id", 0) or 0) == objetivo]:
            _doc_tokens.pop(dh, None)


register_session_revocation_listener(_on_user_store_session_revocation)

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


def _normalizar_recurso_doc(recurso: str) -> str:
    return str(recurso or "").strip().replace("\\", "/").lstrip("/")


def _limpiar_doc_tokens_expirados(ahora: Optional[float] = None) -> None:
    ref = time.time() if ahora is None else ahora
    expirados = [dh for dh, info in _doc_tokens.items() if ref > float(info.get("exp", 0))]
    for dh in expirados:
        _doc_tokens.pop(dh, None)


def crear_token_documento(
    usuario: User | Dict[str, Any],
    recurso: str = "",
    ttl_seconds: int = DOC_TOKEN_TTL_SECONDS,
) -> str:
    """Genera un token efímero acotado exclusivamente a lectura/descarga de un documento."""
    ahora = time.time()
    _limpiar_doc_tokens_expirados(ahora)

    if isinstance(usuario, dict):
        uid = int(usuario.get("user_id", 0) or 0)
        username = str(usuario.get("username", ""))
        role = str(usuario.get("role", "operador"))
        nombre = str(usuario.get("nombre", "") or username)
        email = str(usuario.get("email", ""))
    else:
        uid = int(getattr(usuario, "id", 0) or 0)
        username = str(getattr(usuario, "username", ""))
        role = str(getattr(usuario, "role", "operador"))
        nombre = str(getattr(usuario, "nombre", "") or username)
        email = str(getattr(usuario, "email", ""))

    raw_token = f"doc_{secrets.token_urlsafe(24)}"
    token_hash = _hash_token(raw_token)
    _doc_tokens[token_hash] = {
        "user_id": uid,
        "username": username,
        "role": role,
        "nombre": nombre,
        "email": email,
        "recurso": _normalizar_recurso_doc(recurso),
        "exp": ahora + max(1, int(ttl_seconds)),
        "is_doc_token": True,
    }
    return raw_token


def validar_token_documento(
    raw_token: str,
    recurso_solicitado: str = "",
    user_store: Optional[UserStore] = None,
) -> Optional[Dict[str, Any]]:
    """Valida un token efímero de documento verificando vigencia, recurso y usuario activo."""
    if not raw_token or not raw_token.strip():
        return None
    ahora = time.time()
    _limpiar_doc_tokens_expirados(ahora)
    token_hash = _hash_token(raw_token)
    entry = _doc_tokens.get(token_hash)
    if not entry or ahora > float(entry.get("exp", 0)):
        _doc_tokens.pop(token_hash, None)
        return None

    recurso_esperado = entry.get("recurso", "")
    if recurso_esperado:
        recurso_norm = _normalizar_recurso_doc(recurso_solicitado)
        if recurso_norm != recurso_esperado:
            return None

    uid = int(entry.get("user_id", 0) or 0)
    if user_store is not None and uid > 0:
        try:
            db_user = user_store.get_user(uid)
        except Exception:
            db_user = None
        if isinstance(db_user, User):
            if not db_user.active:
                _doc_tokens.pop(token_hash, None)
                return None
        elif db_user is None:
            _doc_tokens.pop(token_hash, None)
            return None

    return dict(entry)


def _validar_y_sincronizar_usuario(
    sesion: Dict[str, Any],
    token_hash: str,
    user_store: UserStore,
) -> Dict[str, Any]:
    uid = int(sesion.get("user_id", 0) or 0)
    if uid > 0:
        try:
            db_user = user_store.get_user(uid)
        except Exception:
            db_user = None
        if isinstance(db_user, User):
            if not db_user.active:
                _sesiones_activas.pop(token_hash, None)
                try:
                    user_store.revoke_api_session(token_hash)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="La cuenta de usuario se encuentra deshabilitada.",
                )
            sesion["role"] = db_user.role
            sesion["username"] = db_user.username
            sesion["nombre"] = db_user.nombre or db_user.username
            sesion["email"] = db_user.email
        elif db_user is None:
            _sesiones_activas.pop(token_hash, None)
            try:
                user_store.revoke_api_session(token_hash)
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario inexistente o sesión revocada.",
            )
    return sesion


async def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
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

    # 2. Autenticación mediante token de sesión en encabezado HTTP
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

    token_hash = _hash_token(token)
    ahora = time.time()
    sesion = _sesiones_activas.get(token_hash)

    if sesion and ahora - float(sesion.get("last_active", 0)) > SESSION_TTL_SECONDS:
        _sesiones_activas.pop(token_hash, None)
        try:
            user_store.revoke_api_session(token_hash)
        except Exception:
            pass
        sesion = None

    # 3. Si no está en memoria, consultar SQLite (ej: tras reinicio del servidor)
    if not sesion:
        try:
            db_session = user_store.get_api_session(token_hash)
            if db_session:
                if ahora - float(db_session.get("last_active", 0)) <= SESSION_TTL_SECONDS:
                    sesion = db_session
                    _sesiones_activas[token_hash] = sesion
                else:
                    user_store.revoke_api_session(token_hash)
        except Exception:
            pass

    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o sesión expirada. Inicie sesión nuevamente.",
        )

    sesion = _validar_y_sincronizar_usuario(sesion, token_hash, user_store)

    # Actualizar última actividad
    sesion["last_active"] = ahora
    try:
        user_store.update_api_session_activity(token_hash, ahora)
    except Exception:
        pass

    return sesion


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
        if rol == "master":  # El rol master tiene acceso total
            return user
        if rol not in roles_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Se requiere uno de los siguientes roles: {', '.join(roles_permitidos)}",
            )
        return user
    return _role_checker
