"""Ciclo de vida de tokens de sesión persistentes y tokens efímeros de documentos."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from ..auth import User, UserStore
from ..auth.store import register_session_revocation_listener
from .stores import get_user_store, register_token_reset_listener

SESSION_TTL_SECONDS = 24 * 3600  # 24 horas de inactividad máxima por token
SESSION_ABSOLUTE_TTL_SECONDS = 7 * 24 * 3600  # 7 días de vida absoluta máxima por token
DOC_TOKEN_TTL_SECONDS = 300  # 5 minutos para tokens efímeros de visor/descarga web

_sesiones_activas: Dict[str, Dict[str, Any]] = {}
_doc_tokens: Dict[str, Dict[str, Any]] = {}


def _limpiar_caches_tokens_memoria() -> None:
    _sesiones_activas.clear()
    _doc_tokens.clear()


register_token_reset_listener(_limpiar_caches_tokens_memoria)


def _sesion_expirada(sesion: Dict[str, Any], ahora: float) -> bool:
    """Evalúa tanto expiración por inactividad (sliding) como vida absoluta máxima del token."""
    last_active = float(sesion.get("last_active", 0) or 0)
    if ahora - last_active > SESSION_TTL_SECONDS:
        return True
    created_at = float(sesion.get("created_at", 0) or 0)
    if created_at > 0 and ahora - created_at > SESSION_ABSOLUTE_TTL_SECONDS:
        return True
    return False


def _on_user_store_session_revocation(
    event: str, user_id: Optional[int], token_hash: Optional[str]
) -> None:
    """Mantiene sincronizada la caché en memoria ante revocaciones en UserStore."""
    if event == "all":
        _limpiar_caches_tokens_memoria()
    elif event == "token" and token_hash:
        _sesiones_activas.pop(token_hash, None)
    elif event == "user" and user_id is not None:
        objetivo = int(user_id)
        for th in [k for k, v in _sesiones_activas.items() if int(v.get("user_id", 0) or 0) == objetivo]:
            _sesiones_activas.pop(th, None)
        for dh in [k for k, v in _doc_tokens.items() if int(v.get("user_id", 0) or 0) == objetivo]:
            _doc_tokens.pop(dh, None)


register_session_revocation_listener(_on_user_store_session_revocation)


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

    _sesiones_activas[token_hash] = sesion_data
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

    recurso_norm_emitido = _normalizar_recurso_doc(recurso)
    if not recurso_norm_emitido:
        raise ValueError("Debe especificarse el recurso autorizado para emitir un token de documento.")

    raw_token = f"doc_{secrets.token_urlsafe(24)}"
    token_hash = _hash_token(raw_token)
    _doc_tokens[token_hash] = {
        "user_id": uid,
        "username": username,
        "role": role,
        "nombre": nombre,
        "email": email,
        "recurso": recurso_norm_emitido,
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
    recurso_norm = _normalizar_recurso_doc(recurso_solicitado)
    if not recurso_esperado or recurso_norm != recurso_esperado:
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


def _revocar_sesion_silenciosa(token_hash: str, user_store: UserStore) -> None:
    _sesiones_activas.pop(token_hash, None)
    try:
        user_store.revoke_api_session(token_hash)
    except Exception:
        pass


def validar_y_sincronizar_usuario(
    sesion: Dict[str, Any],
    token_hash: str,
    user_store: UserStore,
) -> Dict[str, Any]:
    """Sincroniza datos vigentes del usuario en SQLite y rechaza cuentas deshabilitadas o eliminadas."""
    uid = int(sesion.get("user_id", 0) or 0)
    if uid > 0:
        try:
            db_user = user_store.get_user(uid)
        except Exception:
            db_user = None
        if isinstance(db_user, User):
            if not db_user.active:
                _revocar_sesion_silenciosa(token_hash, user_store)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="La cuenta de usuario se encuentra deshabilitada.",
                )
            sesion["role"] = db_user.role
            sesion["username"] = db_user.username
            sesion["nombre"] = db_user.nombre or db_user.username
            sesion["email"] = db_user.email
        elif db_user is None:
            _revocar_sesion_silenciosa(token_hash, user_store)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario inexistente o sesión revocada.",
            )
    return sesion


def resolver_sesion_activa(token: str, user_store: UserStore) -> Dict[str, Any]:
    """Resuelve y refresca una sesión API desde memoria caché o SQLite."""
    token_hash = _hash_token(token)
    ahora = time.time()
    sesion = _sesiones_activas.get(token_hash)

    if sesion and _sesion_expirada(sesion, ahora):
        _revocar_sesion_silenciosa(token_hash, user_store)
        sesion = None

    if not sesion:
        try:
            db_session = user_store.get_api_session(token_hash)
            if db_session:
                if not _sesion_expirada(db_session, ahora):
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

    sesion = validar_y_sincronizar_usuario(sesion, token_hash, user_store)
    sesion["last_active"] = ahora
    try:
        user_store.update_api_session_activity(token_hash, ahora)
    except Exception:
        pass
    return sesion
