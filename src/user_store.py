"""SQLite persistence and authentication for local application users."""

import hashlib
import hmac
import os
import sqlite3
import time
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Literal


UserRole = Literal["master", "administrador", "operador", "consulta"]
USER_ROLES: tuple[UserRole, ...] = ("master", "administrador", "operador", "consulta")
DEFAULT_MASTER_USERNAME = "Desarrollo"
DEFAULT_MASTER_PASSWORD = "master1713"
PASSWORD_ITERATIONS = 600_000
PASSWORD_MIN_LENGTH = 10
MAX_FAILED_ATTEMPTS = 5
FAILED_WINDOW_SECONDS = 15 * 60
LOCKOUT_SECONDS = 15 * 60


class UserStoreError(Exception):
    """Raised when a user store operation cannot be completed safely."""


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: UserRole
    active: bool
    must_change_password: bool = False


@dataclass(frozen=True)
class AuthResult:
    """Resultado detallado de un intento de inicio de sesión."""

    user: User | None
    status: str  # "ok" | "invalid" | "inactive" | "locked"
    retry_after: int = 0  # segundos restantes de bloqueo (solo si status == "locked")
    attempts_left: int | None = None

    @property
    def locked(self) -> bool:
        return self.status == "locked"

    @property
    def remaining_attempts(self) -> int | None:
        return self.attempts_left

    @property
    def error(self) -> str:
        if self.status == "ok":
            return ""
        if self.status == "locked":
            mins = max(1, (self.retry_after + 59) // 60)
            return f"Cuenta bloqueada temporalmente por seguridad. Intentá de nuevo en {mins} min."
        if self.status == "inactive":
            return "Esta cuenta se encuentra deshabilitada. Contactá a un administrador."
        if self.attempts_left is not None:
            return f"Usuario o contraseña incorrectos ({self.attempts_left} intento(s) restante(s))."
        return "Usuario o contraseña incorrectos."


class UserStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 10000")
            yield connection

    def _initialize(self) -> None:
        with self._connect() as connection, connection:
            self._migrar_esquema(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (
                        role IN ('master', 'administrador', 'operador', 'consulta')
                    ),
                    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS login_attempts (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    first_failed_at REAL NOT NULL DEFAULT 0,
                    locked_until REAL NOT NULL DEFAULT 0
                )
                """
            )
            self._migrar_columna_cambio_clave(connection)
            self._asegurar_usuario_master(connection)

    def _migrar_columna_cambio_clave(self, connection: sqlite3.Connection) -> None:
        columnas = {r["name"] for r in connection.execute("PRAGMA table_info(users)")}
        if "must_change_password" in columnas:
            return
        connection.execute(
            "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
        )
        # Si el Master todavía usa la clave por defecto publicada, obligar a cambiarla.
        master = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (DEFAULT_MASTER_USERNAME,),
        ).fetchone()
        if master is not None and self._verificar_clave(
            DEFAULT_MASTER_PASSWORD, master["password_hash"]
        ):
            connection.execute(
                "UPDATE users SET must_change_password = 1 WHERE id = ?", (master["id"],)
            )

    @staticmethod
    def _migrar_esquema(connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if row and row[0] and "'master'" not in row[0]:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """
                CREATE TABLE users_migracion (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (
                        role IN ('master', 'administrador', 'operador', 'consulta')
                    ),
                    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO users_migracion (id, username, password_hash, role, active, created_at)
                SELECT id, username, password_hash, role, active, created_at FROM users
                """
            )
            connection.execute("DROP TABLE users")
            connection.execute("ALTER TABLE users_migracion RENAME TO users")
            connection.execute("PRAGMA foreign_keys = ON")

    def _asegurar_usuario_master(self, connection: sqlite3.Connection) -> None:
        master_row = connection.execute(
            "SELECT id, role, active FROM users WHERE username = ? COLLATE NOCASE",
            (DEFAULT_MASTER_USERNAME,),
        ).fetchone()
        if master_row is None:
            pwd_hash = self._hash_clave(DEFAULT_MASTER_PASSWORD)
            connection.execute(
                """
                INSERT INTO users (username, password_hash, role, active, must_change_password)
                VALUES (?, ?, 'master', 1, 1)
                """,
                (DEFAULT_MASTER_USERNAME, pwd_hash),
            )
        else:
            if master_row["role"] != "master" or not master_row["active"]:
                connection.execute(
                    "UPDATE users SET role = 'master', active = 1 WHERE id = ?",
                    (master_row["id"],),
                )

    @staticmethod
    def _normalizar_usuario(username: str) -> str:
        username = username.strip()
        if not 3 <= len(username) <= 64:
            raise ValueError("El usuario debe tener entre 3 y 64 caracteres.")
        if any(character.isspace() for character in username):
            raise ValueError("El usuario no puede contener espacios.")
        return username

    @staticmethod
    def _validar_clave(password: str) -> None:
        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres."
            )

    @staticmethod
    def _validar_rol(role: str) -> UserRole:
        if role in ("master", "administrador", "operador", "consulta"):
            return role  # type: ignore[return-value]
        raise ValueError("El rol seleccionado no es válido.")

    @staticmethod
    def _hash_clave(password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS,
        )
        return f"{salt.hex()}:{digest.hex()}"

    @staticmethod
    def _verificar_clave(password: str, stored_hash: str) -> bool:
        try:
            salt_text, digest_text = stored_hash.split(":", maxsplit=1)
            salt = bytes.fromhex(salt_text)
            expected = bytes.fromhex(digest_text)
        except ValueError:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS,
        )
        return hmac.compare_digest(actual, expected)

    @property
    def has_users(self) -> bool:
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None

    def create_initial_admin(self, username: str, password: str) -> User:
        username = self._normalizar_usuario(username)
        self._validar_clave(password)
        password_hash = self._hash_clave(password)
        try:
            with self._connect() as connection, connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT 1 FROM users WHERE role = 'administrador' LIMIT 1").fetchone():
                    raise UserStoreError(
                        "La configuración inicial ya fue completada."
                    )
                cursor = connection.execute(
                    """
                    INSERT INTO users (username, password_hash, role)
                    VALUES (?, ?, 'administrador')
                    """,
                    (username, password_hash),
                )
                row = connection.execute(
                    "SELECT id, username, role, active FROM users WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ValueError("Ese nombre de usuario ya existe.") from error
        return self._row_to_user(row)

    def create_user(
        self, username: str, password: str, role: str, creator_role: str | None = None
    ) -> User:
        username = self._normalizar_usuario(username)
        self._validar_clave(password)
        validated_role = self._validar_rol(role)
        if validated_role in ("master", "administrador") and creator_role is not None and creator_role != "master":
            raise UserStoreError("Solo un usuario con rol master puede crear administradores.")
        password_hash = self._hash_clave(password)
        try:
            with self._connect() as connection, connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users (username, password_hash, role)
                    VALUES (?, ?, ?)
                    """,
                    (username, password_hash, validated_role),
                )
                row = connection.execute(
                    "SELECT id, username, role, active FROM users WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ValueError("Ese nombre de usuario ya existe.") from error
        return self._row_to_user(row)

    def authenticate(self, username: str, password: str) -> User | None:
        return self.authenticate_detailed(username, password).user

    def authenticate_detailed(self, username: str, password: str) -> AuthResult:
        """Autentica aplicando bloqueo temporal tras varios intentos fallidos."""
        username = username.strip()
        ahora = time.time()
        restante = self.segundos_bloqueo_restantes(username, ahora)
        if restante > 0:
            return AuthResult(None, "locked", retry_after=restante)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, username, password_hash, role, active, must_change_password
                FROM users WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if row is None:
            self._verificar_clave(password, self._hash_clave("invalid-user-password"))
            return self._registrar_fallo(username, ahora)
        password_valid = self._verificar_clave(password, row["password_hash"])
        if not password_valid:
            return self._registrar_fallo(username, ahora)
        if not row["active"]:
            return AuthResult(None, "inactive")
        self._limpiar_intentos(username)
        return AuthResult(self._row_to_user(row), "ok")

    def segundos_bloqueo_restantes(self, username: str, ahora: float | None = None) -> int:
        ahora = time.time() if ahora is None else ahora
        with self._connect() as connection:
            row = connection.execute(
                "SELECT locked_until FROM login_attempts WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        if row is None or row["locked_until"] <= ahora:
            return 0
        return int(row["locked_until"] - ahora) + 1

    def _registrar_fallo(self, username: str, ahora: float) -> AuthResult:
        if not username:
            return AuthResult(None, "invalid")
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT failed_count, first_failed_at FROM login_attempts WHERE username = ?",
                (username,),
            ).fetchone()
            if row is None or ahora - row["first_failed_at"] > FAILED_WINDOW_SECONDS:
                cantidad, primero = 1, ahora
            else:
                cantidad, primero = row["failed_count"] + 1, row["first_failed_at"]
            if cantidad >= MAX_FAILED_ATTEMPTS:
                connection.execute(
                    """
                    INSERT INTO login_attempts (username, failed_count, first_failed_at, locked_until)
                    VALUES (?, 0, 0, ?)
                    ON CONFLICT(username) DO UPDATE SET
                        failed_count = 0, first_failed_at = 0, locked_until = excluded.locked_until
                    """,
                    (username, ahora + LOCKOUT_SECONDS),
                )
                return AuthResult(None, "locked", retry_after=LOCKOUT_SECONDS)
            connection.execute(
                """
                INSERT INTO login_attempts (username, failed_count, first_failed_at, locked_until)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(username) DO UPDATE SET
                    failed_count = excluded.failed_count,
                    first_failed_at = excluded.first_failed_at
                """,
                (username, cantidad, primero),
            )
        return AuthResult(None, "invalid", attempts_left=MAX_FAILED_ATTEMPTS - cantidad)

    def _limpiar_intentos(self, username: str) -> None:
        with self._connect() as connection, connection:
            connection.execute("DELETE FROM login_attempts WHERE username = ?", (username,))

    def unlock_user(self, username: str) -> None:
        """Desbloquea manualmente una cuenta (acción de administración)."""
        self._limpiar_intentos(username.strip())

    def list_locked_usernames(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT username FROM login_attempts WHERE locked_until > ?", (time.time(),)
            ).fetchall()
        return [r["username"] for r in rows]

    def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        """Cambia la clave del propio usuario verificando la actual."""
        self._validar_clave(new_password)
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
            if not self._verificar_clave(current_password, row["password_hash"]):
                raise UserStoreError("La contraseña actual no es correcta.")
            connection.execute(
                "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                (self._hash_clave(new_password), user_id),
            )

    def reset_password(
        self,
        user_id: int,
        new_password: str,
        updater_role: str | None = None,
        must_change: bool = True,
    ) -> None:
        """Restablece la clave de otro usuario; el afectado deberá cambiarla al ingresar."""
        self._validar_clave(new_password)
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT username, role FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row is None:
                raise UserStoreError("No se encontró el usuario.")
            if updater_role != "master" and row["role"] in ("master", "administrador"):
                raise UserStoreError(
                    "Solo el usuario master puede restablecer la clave de un administrador."
                )
            connection.execute(
                "UPDATE users SET password_hash = ?, must_change_password = ? WHERE id = ?",
                (self._hash_clave(new_password), 1 if must_change else 0, user_id),
            )
            connection.execute("DELETE FROM login_attempts WHERE username = ?", (row["username"],))

    def list_users(self, include_master: bool = True) -> list[User]:
        with self._connect() as connection:
            if include_master:
                rows = connection.execute(
                    "SELECT id, username, role, active, must_change_password FROM users ORDER BY username COLLATE NOCASE"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT id, username, role, active, must_change_password FROM users WHERE role != 'master' ORDER BY username COLLATE NOCASE"
                ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user(self, user_id: int) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, role, active, must_change_password FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._row_to_user(row) if row is not None else None

    def get_user_by_username(self, username: str) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, role, active, must_change_password FROM users WHERE username = ? COLLATE NOCASE",
                (username.strip(),),
            ).fetchone()
        return self._row_to_user(row) if row is not None else None

    def update_role(
        self, user_id: int, role: str, updater_role: str | None = None
    ) -> None:
        validated_role = self._validar_rol(role)
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
                "UPDATE users SET role = ? WHERE id = ?",
                (validated_role, user_id),
            )

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
            if (
                current["role"] == "administrador"
                and current["active"]
                and not active
            ):
                self._require_another_active_admin(connection, user_id)
            connection.execute(
                "UPDATE users SET active = ? WHERE id = ?",
                (int(active), user_id),
            )

    @staticmethod
    def _require_another_active_admin(
        connection: sqlite3.Connection, except_user_id: int
    ) -> None:
        another_admin = connection.execute(
            """
            SELECT 1 FROM users
            WHERE role = 'administrador' AND active = 1 AND id != ?
            LIMIT 1
            """,
            (except_user_id,),
        ).fetchone()
        if another_admin is None:
            raise UserStoreError(
                "No se puede quitar o desactivar al único administrador activo."
            )

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            role=UserStore._validar_rol(row["role"]),
            active=bool(row["active"]),
            must_change_password=(
                bool(row["must_change_password"])
                if "must_change_password" in row.keys()
                else False
            ),
        )
