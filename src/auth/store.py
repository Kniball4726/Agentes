"""Persistencia SQLite y lógica de negocio de usuarios, roles, sesiones y API keys."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from ..core.delegation import DelegadoAtributo
from ..core.exceptions import UserStoreError
from ..core.sqlite_utils import sqlite_connection
from .api_tokens_repo import ApiTokensRepository
from .events import notify_session_revocation, register_session_revocation_listener
from .lockout_repo import LockoutRepository
from .models import (
    DEFAULT_MASTER_PASSWORD,
    DEFAULT_MASTER_USERNAME,
    AuthResult,
    User,
)
from .password import hash_clave, validar_clave, verificar_clave
from .schema import inicializar_esquema, migrar_columnas
from .validators import (
    normalizar_usuario,
    validar_email,
    validar_nombre,
    validar_rol,
    verificar_email_unico,
)

_notify_session_revocation = notify_session_revocation

_USER_COLUMNS = (
    "id, username, role, active, must_change_password, nombre, email, created_at, updated_at"
)
_DUMMY_PASSWORD_HASH: str | None = None
_MAX_PASSWORD_INPUT_LEN = 256


def _obtener_dummy_password_hash() -> str:
    """Genera una única vez un hash PBKDF2 dummy para igualar tiempos ante usuarios inexistentes."""
    global _DUMMY_PASSWORD_HASH
    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = hash_clave("invalid-user-dummy-password")
    return _DUMMY_PASSWORD_HASH


class UserStore:
    """Gestor de acceso a datos para usuarios, credenciales, sesiones y claves API."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.lockout_repo = LockoutRepository(self._connect)
        self.api_tokens_repo = ApiTokensRepository(self._connect)
        self._initialize()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        with sqlite_connection(self.database_path) as connection:
            yield connection

    def _initialize(self) -> None:
        with self._connect() as connection, connection:
            inicializar_esquema(connection, self.database_path)

    _migrar_columnas = staticmethod(migrar_columnas)
    _normalizar_usuario = staticmethod(normalizar_usuario)
    _validar_clave = staticmethod(validar_clave)
    _validar_rol = staticmethod(validar_rol)
    _validar_nombre = staticmethod(validar_nombre)
    _validar_email = staticmethod(validar_email)
    _verificar_email_unico = staticmethod(verificar_email_unico)
    _hash_clave = staticmethod(hash_clave)
    _verificar_clave = staticmethod(verificar_clave)

    @property
    def has_users(self) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def create_initial_admin(
        self,
        username: str,
        password: str,
        nombre: str = "",
        email: str = "",
    ) -> User:
        username = normalizar_usuario(username)
        validar_clave(password)
        nombre_valido = validar_nombre(nombre)
        email_valido = validar_email(email)
        password_hash = hash_clave(password)
        try:
            with self._connect() as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM users WHERE role = 'administrador' LIMIT 1"
                ).fetchone():
                    raise UserStoreError("La configuración inicial ya fue completada.")
                verificar_email_unico(connection, email_valido)
                cursor = connection.execute(
                    """
                    INSERT INTO users (username, password_hash, role, nombre, email)
                    VALUES (?, ?, 'administrador', ?, ?)
                    """,
                    (username, password_hash, nombre_valido, email_valido),
                )
                row = connection.execute(
                    f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            if "email" in str(error).lower():
                raise ValueError("Ese correo electrónico ya está registrado.") from error
            raise ValueError("Ese nombre de usuario ya existe.") from error
        return self._row_to_user(row)

    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        creator_role: str | None = None,
        nombre: str = "",
        email: str = "",
    ) -> User:
        username = normalizar_usuario(username)
        validar_clave(password)
        validated_role = validar_rol(role)
        nombre_valido = validar_nombre(nombre)
        email_valido = validar_email(email)
        if validated_role in ("master", "administrador") and creator_role is not None and creator_role != "master":
            raise UserStoreError("Solo un usuario con rol master puede crear administradores.")
        password_hash = hash_clave(password)
        try:
            with self._connect() as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                verificar_email_unico(connection, email_valido)
                cursor = connection.execute(
                    """
                    INSERT INTO users (username, password_hash, role, nombre, email)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (username, password_hash, validated_role, nombre_valido, email_valido),
                )
                row = connection.execute(
                    f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            if "email" in str(error).lower():
                raise ValueError("Ese correo electrónico ya está registrado.") from error
            raise ValueError("Ese nombre de usuario ya existe.") from error
        return self._row_to_user(row)

    def update_user_info(
        self,
        user_id: int,
        nombre: str | None = None,
        email: str | None = None,
        updater_role: str | None = None,
    ) -> User:
        """Actualiza el nombre identificador y/o el email de un usuario."""
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if current is None:
                raise UserStoreError("No se encontró el usuario.")
            if current["role"] == "master" and updater_role is not None and updater_role != "master":
                raise UserStoreError("Solo el usuario master puede modificar los datos del usuario master.")
            nuevo_nombre = validar_nombre(nombre) if nombre is not None else (current["nombre"] or "")
            nuevo_email = validar_email(email) if email is not None else (current["email"] or "")
            if email is not None:
                verificar_email_unico(connection, nuevo_email, except_user_id=user_id)
            connection.execute(
                "UPDATE users SET nombre = ?, email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (nuevo_nombre, nuevo_email, user_id),
            )
            updated_row = connection.execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._row_to_user(updated_row)

    def authenticate(self, username: str, password: str) -> User | None:
        return self.authenticate_detailed(username, password).user

    def authenticate_detailed(self, username: str, password: str) -> AuthResult:
        """Autentica aplicando bloqueo temporal y permitiendo usuario o correo electrónico."""
        identificador = username.strip()
        ahora = time.time()
        restante = self.segundos_bloqueo_restantes(identificador, ahora)
        if restante > 0:
            return AuthResult(None, "locked", retry_after=restante)
        if len(str(password or "")) > _MAX_PASSWORD_INPUT_LEN:
            return self._registrar_fallo(identificador, ahora)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, username, password_hash, role, active, must_change_password, nombre, email, created_at, updated_at
                FROM users
                WHERE username = ? COLLATE NOCASE OR (email != '' AND email = ? COLLATE NOCASE)
                """,
                (identificador, identificador),
            ).fetchone()
        if row is None:
            if identificador.lower() == "desarrollo":
                with self._connect() as conn_fb:
                    row = conn_fb.execute(
                        "SELECT id, username, password_hash, role, active, must_change_password, nombre, email, created_at, updated_at FROM users WHERE username = ? COLLATE NOCASE",
                        (DEFAULT_MASTER_USERNAME,),
                    ).fetchone()
            if row is None:
                verificar_clave(password, _obtener_dummy_password_hash())
                return self._registrar_fallo(identificador, ahora)

        nombre_cuenta = row["username"]
        if nombre_cuenta.lower() != identificador.lower():
            restante_real = self.segundos_bloqueo_restantes(nombre_cuenta, ahora)
            if restante_real > 0:
                return AuthResult(None, "locked", retry_after=restante_real)

        if not verificar_clave(password, row["password_hash"]):
            return self._registrar_fallo(nombre_cuenta, ahora)
        if not row["active"]:
            return AuthResult(None, "inactive")
        self._limpiar_intentos(nombre_cuenta)
        if nombre_cuenta.lower() != identificador.lower():
            self._limpiar_intentos(identificador)
        return AuthResult(self._row_to_user(row), "ok")

    def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        """Cambia la clave del propio usuario verificando la actual."""
        validar_clave(new_password)
        if new_password == DEFAULT_MASTER_PASSWORD:
            raise ValueError("La nueva contraseña no puede ser la contraseña por defecto del sistema.")
        if new_password == current_password:
            raise ValueError("La nueva contraseña debe ser distinta de la actual.")
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row is None:
                raise UserStoreError("No se encontró el usuario.")
            if not verificar_clave(current_password, row["password_hash"]):
                raise UserStoreError("La contraseña actual no es correcta.")
            connection.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (hash_clave(new_password), user_id),
            )
            connection.execute("DELETE FROM api_sessions WHERE user_id = ?", (user_id,))
        notify_session_revocation("user", user_id=user_id)

    def reset_password(
        self,
        user_id: int,
        new_password: str,
        updater_role: str | None = None,
        must_change: bool = True,
    ) -> None:
        """Restablece la clave de otro usuario y revoca sus sesiones activas."""
        validar_clave(new_password)
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row is None:
                raise UserStoreError("No se encontró el usuario.")
            if updater_role != "master" and row["role"] in ("master", "administrador"):
                raise UserStoreError("Solo el usuario master puede restablecer la clave de un administrador.")
            connection.execute(
                "UPDATE users SET password_hash = ?, must_change_password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (hash_clave(new_password), 1 if must_change else 0, user_id),
            )
            connection.execute("DELETE FROM login_attempts WHERE username = ?", (row["username"],))
            connection.execute("DELETE FROM api_sessions WHERE user_id = ?", (user_id,))
        notify_session_revocation("user", user_id=user_id)

    def list_users(
        self,
        include_master: bool = True,
        exclude_other_admins: bool = False,
        current_user_id: int | None = None,
    ) -> list[User]:
        with self._connect() as connection:
            query = f"SELECT {_USER_COLUMNS} FROM users"
            conditions: list[str] = []
            params: list[Any] = []
            if not include_master:
                conditions.append("role != 'master'")
            if exclude_other_admins:
                if current_user_id is not None:
                    conditions.append("(role != 'administrador' OR id = ?)")
                    params.append(current_user_id)
                else:
                    conditions.append("role != 'administrador'")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY username COLLATE NOCASE"
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user(self, user_id: int) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return self._row_to_user(row) if row is not None else None

    def get_user_by_username(self, username: str) -> User | None:
        cand = DEFAULT_MASTER_USERNAME if username.strip().lower() == "desarrollo" else username.strip()
        user = self._buscar_usuario_por_nombre(cand)
        if user is None and cand != username.strip():
            user = self._buscar_usuario_por_nombre(username.strip())
        return user

    def _buscar_usuario_por_nombre(self, username: str) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE username = ? COLLATE NOCASE",
                (username.strip(),),
            ).fetchone()
        return self._row_to_user(row) if row is not None else None

    def get_user_by_email(self, email: str) -> User | None:
        email_norm = email.strip().lower()
        if not email_norm:
            return None
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE email = ? COLLATE NOCASE",
                (email_norm,),
            ).fetchone()
        return self._row_to_user(row) if row is not None else None

    def get_user_by_identifier(self, identifier: str) -> User | None:
        ident = identifier.strip()
        if not ident:
            return None
        user = self.get_user_by_username(ident)
        if user is None and "@" in ident:
            user = self.get_user_by_email(ident)
        return user

    def update_role(
        self, user_id: int, role: str, updater_role: str | None = None
    ) -> None:
        validated_role = validar_rol(role)
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT username, role, active FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if current is None:
                raise UserStoreError("No se encontró el usuario.")
            if current["role"] == "master" and validated_role != "master":
                raise UserStoreError("No se puede cambiar el rol del usuario master.")
            if validated_role == "master" and updater_role != "master":
                raise UserStoreError("Solo el rol master puede asignar el rol master.")
            if (
                validated_role == "administrador"
                and current["role"] != "administrador"
                and updater_role is not None
                and updater_role != "master"
            ):
                raise UserStoreError("Solo el usuario master puede promover a administrador.")
            if (
                current["role"] == "administrador"
                and updater_role is not None
                and updater_role != "master"
            ):
                raise UserStoreError("Solo el usuario master puede modificar el rol de un administrador.")
            if (
                current["role"] == "administrador"
                and current["active"]
                and validated_role != "administrador"
            ):
                self._require_another_active_admin(connection, user_id)
            connection.execute(
                "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (validated_role, user_id),
            )
            if validated_role != current["role"]:
                connection.execute("DELETE FROM api_sessions WHERE user_id = ?", (user_id,))
        if validated_role != current["role"]:
            notify_session_revocation("user", user_id=user_id)

    def set_active(
        self, user_id: int, active: bool, updater_role: str | None = None
    ) -> None:
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT username, role, active FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if current is None:
                raise UserStoreError("No se encontró el usuario.")
            if current["role"] == "master" and not active:
                raise UserStoreError("El usuario master no puede ser desactivado.")
            if (
                current["role"] == "administrador"
                and updater_role is not None
                and updater_role != "master"
            ):
                raise UserStoreError("Solo el usuario master puede desactivar o activar a un administrador.")
            if current["role"] == "administrador" and current["active"] and not active:
                self._require_another_active_admin(connection, user_id)
            connection.execute(
                "UPDATE users SET active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (int(active), user_id),
            )
            if not active:
                connection.execute("DELETE FROM api_sessions WHERE user_id = ?", (user_id,))
        if not active:
            notify_session_revocation("user", user_id=user_id)

    @staticmethod
    def _require_another_active_admin(
        connection: sqlite3.Connection, except_user_id: int
    ) -> None:
        another_admin = connection.execute(
            "SELECT 1 FROM users WHERE role = 'administrador' AND active = 1 AND id != ? LIMIT 1",
            (except_user_id,),
        ).fetchone()
        if another_admin is None:
            raise UserStoreError("No se puede quitar o desactivar al único administrador activo.")

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> User:
        keys = row.keys()
        return User(
            id=row["id"],
            username=row["username"],
            role=validar_rol(row["role"]),
            active=bool(row["active"]),
            must_change_password=bool(row["must_change_password"]) if "must_change_password" in keys else False,
            nombre=str(row["nombre"] or "") if "nombre" in keys and row["nombre"] is not None else "",
            email=str(row["email"] or "") if "email" in keys and row["email"] is not None else "",
            created_at=str(row["created_at"] or "") if "created_at" in keys and row["created_at"] is not None else "",
            updated_at=str(row["updated_at"] or "") if "updated_at" in keys and row["updated_at"] is not None else "",
        )

    # Delegación por descriptor a repositorios especializados (bloqueo y sesiones/claves API)
    segundos_bloqueo_restantes = DelegadoAtributo("lockout_repo", LockoutRepository)
    _registrar_fallo = DelegadoAtributo("lockout_repo", LockoutRepository, "registrar_fallo")
    _limpiar_intentos = DelegadoAtributo("lockout_repo", LockoutRepository, "limpiar_intentos")
    unlock_user = DelegadoAtributo("lockout_repo", LockoutRepository)
    list_locked_usernames = DelegadoAtributo("lockout_repo", LockoutRepository)

    create_api_session = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    get_api_session = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    update_api_session_activity = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    revoke_api_session = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    revoke_user_api_sessions = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    cleanup_expired_api_sessions = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    create_api_key = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    validate_api_key = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    list_api_keys = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    revoke_api_key = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    delete_api_key = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    list_api_sessions = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
    revoke_all_sessions = DelegadoAtributo("api_tokens_repo", ApiTokensRepository)
