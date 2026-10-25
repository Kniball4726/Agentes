"""SQLite persistence and authentication for local application users."""

import hashlib
import hmac
import os
import sqlite3
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


class UserStoreError(Exception):
    """Raised when a user store operation cannot be completed safely."""


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: UserRole
    active: bool


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
            self._asegurar_usuario_master(connection)

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
                INSERT INTO users (username, password_hash, role, active)
                VALUES (?, ?, 'master', 1)
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
        username = username.strip()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, username, password_hash, role, active
                FROM users WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if row is None:
            self._verificar_clave(password, self._hash_clave("invalid-user-password"))
            return None
        password_valid = self._verificar_clave(password, row["password_hash"])
        if not password_valid or not row["active"]:
            return None
        return self._row_to_user(row)

    def list_users(self, include_master: bool = True) -> list[User]:
        with self._connect() as connection:
            if include_master:
                rows = connection.execute(
                    "SELECT id, username, role, active FROM users ORDER BY username COLLATE NOCASE"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT id, username, role, active FROM users WHERE role != 'master' ORDER BY username COLLATE NOCASE"
                ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user(self, user_id: int) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, role, active FROM users WHERE id = ?",
                (user_id,),
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
        )
