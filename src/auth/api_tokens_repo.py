"""Mixin de persistencia para sesiones API (`api_sessions`) y claves API (`api_keys`)."""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime

from .events import notify_session_revocation
from .validators import validar_rol


class ApiTokensRepositoryMixin:
    """Operaciones SQLite para sesiones de API REST y claves API B2B."""

    def create_api_session(
        self,
        token_hash: str,
        user_id: int,
        username: str,
        role: str,
        nombre: str = "",
        email: str = "",
        created_at: float | None = None,
        last_active: float | None = None,
    ) -> None:
        """Persiste una sesión de usuario con hash seguro del token."""
        ahora = time.time()
        c_at = created_at if created_at is not None else ahora
        l_act = last_active if last_active is not None else ahora
        with self._connect() as connection, connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO api_sessions (
                    token_hash, user_id, username, role, nombre, email, created_at, last_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (token_hash, user_id, username, role, nombre, email, c_at, l_act),
            )

    def get_api_session(self, token_hash: str) -> dict | None:
        """Recupera una sesión persistida por su hash de token."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT user_id, username, role, nombre, email, created_at, last_active
                FROM api_sessions WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row:
                return dict(row)
        return None

    def update_api_session_activity(
        self, token_hash: str, last_active: float | None = None
    ) -> None:
        """Actualiza la marca de última actividad de una sesión."""
        with self._connect() as connection, connection:
            l_act = last_active if last_active is not None else time.time()
            connection.execute(
                "UPDATE api_sessions SET last_active = ? WHERE token_hash = ?",
                (l_act, token_hash),
            )

    def revoke_api_session(self, token_hash: str) -> bool:
        """Revoca y elimina permanentemente una sesión activa."""
        with self._connect() as connection, connection:
            cur = connection.execute(
                "DELETE FROM api_sessions WHERE token_hash = ?", (token_hash,)
            )
            revocada = cur.rowcount > 0
        notify_session_revocation("token", token_hash=token_hash)
        return revocada

    def revoke_user_api_sessions(self, user_id: int) -> int:
        """Revoca todas las sesiones activas asociadas a un usuario específico."""
        with self._connect() as connection, connection:
            cur = connection.execute(
                "DELETE FROM api_sessions WHERE user_id = ?", (user_id,)
            )
            cantidad = cur.rowcount
        notify_session_revocation("user", user_id=user_id)
        return cantidad

    def cleanup_expired_api_sessions(self, max_age_seconds: float) -> int:
        """Limpia de SQLite sesiones que superaron el tiempo máximo de inactividad."""
        limite = time.time() - max_age_seconds
        with self._connect() as connection, connection:
            cur = connection.execute(
                "DELETE FROM api_sessions WHERE last_active < ?", (limite,)
            )
            return cur.rowcount

    def create_api_key(
        self, client_name: str, role: str = "operador"
    ) -> tuple[str, str]:
        """Genera una clave API estática para integración externa (ej: B2B/ERP).

        Retorna (raw_key, key_hash).
        """
        validated_role = validar_rol(role)
        raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        ahora = datetime.now().isoformat(sep=" ", timespec="seconds")
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO api_keys (key_hash, client_name, role, active, created_at) VALUES (?, ?, ?, 1, ?)",
                (key_hash, client_name.strip(), validated_role, ahora),
            )
        return raw_key, key_hash

    def validate_api_key(self, raw_key: str) -> dict | None:
        """Valida una API Key externa contra su hash en base de datos."""
        if not raw_key:
            return None
        key_hash = hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()
        with self._connect() as connection, connection:
            row = connection.execute(
                "SELECT key_hash, client_name, role, active FROM api_keys WHERE key_hash = ? AND active = 1",
                (key_hash,),
            ).fetchone()
            if row:
                connection.execute(
                    "UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE key_hash = ?",
                    (key_hash,),
                )
                return dict(row)
        return None

    def list_api_keys(self) -> list[dict]:
        """Lista todas las claves API registradas para control del administrador."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key_hash, client_name, role, active, created_at, last_used FROM api_keys ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def revoke_api_key(self, key_hash: str) -> bool:
        """Revoca de forma inmediata una clave API."""
        with self._connect() as connection, connection:
            cur = connection.execute(
                "UPDATE api_keys SET active = 0 WHERE key_hash = ?", (key_hash,)
            )
            return cur.rowcount > 0

    def delete_api_key(self, key_hash: str) -> bool:
        """Elimina de forma permanente una clave API de la base de datos."""
        with self._connect() as connection, connection:
            cur = connection.execute(
                "DELETE FROM api_keys WHERE key_hash = ?", (key_hash,)
            )
            return cur.rowcount > 0

    def list_api_sessions(self, max_records: int = 100) -> list[dict]:
        """Lista las sesiones API persistidas ordenadas por última actividad reciente."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT token_hash, user_id, username, role, nombre, email, created_at, last_active
                FROM api_sessions
                ORDER BY last_active DESC
                LIMIT ?
                """,
                (max_records,),
            ).fetchall()
            return [dict(r) for r in rows]

    def revoke_all_sessions(self) -> int:
        """Revoca todas las sesiones activas persistidas."""
        with self._connect() as connection, connection:
            cur = connection.execute("DELETE FROM api_sessions")
            total = cur.rowcount
        notify_session_revocation("all")
        return total
