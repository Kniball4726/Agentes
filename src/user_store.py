"""SQLite persistence and authentication for local application users."""

import hashlib
import hmac
import os
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Literal


UserRole = Literal["administrador", "operador", "consulta"]
USER_ROLES: tuple[UserRole, ...] = ("administrador", "operador", "consulta")
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
            yield connection

    def _initialize(self) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (
                        role IN ('administrador', 'operador', 'consulta')
                    ),
                    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
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
        if role == "administrador" or role == "operador" or role == "consulta":
            return role
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
                if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
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

    def create_user(self, username: str, password: str, role: str) -> User:
        username = self._normalizar_usuario(username)
        self._validar_clave(password)
        validated_role = self._validar_rol(role)
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

    def list_users(self) -> list[User]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, username, role, active FROM users ORDER BY username COLLATE NOCASE"
            ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def get_user(self, user_id: int) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, username, role, active FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return self._row_to_user(row) if row is not None else None

    def update_role(self, user_id: int, role: str) -> None:
        validated_role = self._validar_rol(role)
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT role, active FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if current is None:
                raise UserStoreError("No se encontró el usuario.")
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

    def set_active(self, user_id: int, active: bool) -> None:
        with self._connect() as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT role, active FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if current is None:
                raise UserStoreError("No se encontró el usuario.")
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
