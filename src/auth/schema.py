"""Inicialización y migraciones automáticas del esquema SQLite de autenticación."""

from __future__ import annotations

import sqlite3

from .models import DEFAULT_MASTER_PASSWORD, _master_default_credentials
from .password import hash_clave, verificar_clave


def migrar_esquema(connection: sqlite3.Connection) -> None:
    """Migra la restricción CHECK histórica de roles si faltan 'master', 'picker' o 'despachador'."""
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
    ).fetchone()
    if row and row[0] and (
        "'master'" not in row[0]
        or "'picker'" not in row[0]
        or "'despachador'" not in row[0]
    ):
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            CREATE TABLE users_migracion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (
                    role IN ('master', 'administrador', 'operador', 'consulta', 'picker', 'despachador')
                ),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1)),
                nombre TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        old_cols = {r["name"] for r in connection.execute("PRAGMA table_info(users)")}
        cols_to_copy = [
            c
            for c in [
                "id",
                "username",
                "password_hash",
                "role",
                "active",
                "must_change_password",
                "nombre",
                "email",
                "created_at",
                "updated_at",
            ]
            if c in old_cols
        ]
        cols_str = ", ".join(cols_to_copy)
        connection.execute(
            f"INSERT INTO users_migracion ({cols_str}) SELECT {cols_str} FROM users"
        )
        connection.execute("DROP TABLE users")
        connection.execute("ALTER TABLE users_migracion RENAME TO users")
        connection.execute("PRAGMA foreign_keys = ON")


def migrar_columnas(connection: sqlite3.Connection) -> None:
    """Agrega columnas incrementales faltantes en tablas heredadas."""
    columnas = {r["name"] for r in connection.execute("PRAGMA table_info(users)")}

    if "must_change_password" not in columnas:
        connection.execute(
            "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
        )
        def_user, def_pass = _master_default_credentials()
        master = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ? COLLATE NOCASE",
            (def_user,),
        ).fetchone()
        if master is not None and (
            verificar_clave(def_pass, master["password_hash"])
            or verificar_clave(DEFAULT_MASTER_PASSWORD, master["password_hash"])
        ):
            connection.execute(
                "UPDATE users SET must_change_password = 1 WHERE id = ?", (master["id"],)
            )

    if "nombre" not in columnas:
        connection.execute(
            "ALTER TABLE users ADD COLUMN nombre TEXT NOT NULL DEFAULT ''"
        )

    if "email" not in columnas:
        connection.execute(
            "ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''"
        )

    if "updated_at" not in columnas:
        connection.execute(
            "ALTER TABLE users ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"
        )
        connection.execute(
            "UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at = ''"
        )


def asegurar_indices_y_triggers(connection: sqlite3.Connection) -> None:
    """Crea índices únicos de búsqueda y trigger de auditoría updated_at."""
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_nocase ON users(username COLLATE NOCASE)"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email COLLATE NOCASE) WHERE email != '' AND email IS NOT NULL"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_users_active ON users(active)")
    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
        AFTER UPDATE OF username, password_hash, role, active, must_change_password, nombre, email ON users
        FOR EACH ROW
        BEGIN
            UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END
        """
    )


def asegurar_usuario_master(connection: sqlite3.Connection) -> None:
    """Garantiza la existencia y consistencia del usuario Master del sistema."""
    columnas = {r["name"] for r in connection.execute("PRAGMA table_info(users)")}
    tiene_nombre = "nombre" in columnas
    query = (
        "SELECT id, role, active, nombre FROM users WHERE username = ? COLLATE NOCASE"
        if tiene_nombre
        else "SELECT id, role, active FROM users WHERE username = ? COLLATE NOCASE"
    )
    auditoria_row = connection.execute(
        "SELECT id FROM users WHERE username = 'Auditoria' COLLATE NOCASE"
    ).fetchone()
    desarrollo_row = connection.execute(
        "SELECT id FROM users WHERE username = 'Desarrollo' COLLATE NOCASE AND role = 'master'"
    ).fetchone()
    if auditoria_row and desarrollo_row:
        connection.execute("DELETE FROM users WHERE id = ?", (desarrollo_row["id"],))
    elif desarrollo_row:
        connection.execute(
            "UPDATE users SET username = 'Auditoria', nombre = 'Auditoría' WHERE id = ?",
            (desarrollo_row["id"],),
        )
    def_user, def_pass = _master_default_credentials()
    master_row = connection.execute(query, (def_user,)).fetchone()
    if master_row is None:
        pwd_hash = hash_clave(def_pass)
        connection.execute(
            """
            INSERT INTO users (username, password_hash, role, active, must_change_password, nombre, email)
            VALUES (?, ?, 'master', 1, 1, 'Auditoría', '')
            """,
            (def_user, pwd_hash),
        )
    else:
        if master_row["role"] != "master" or not master_row["active"]:
            connection.execute(
                "UPDATE users SET role = 'master', active = 1 WHERE id = ?",
                (master_row["id"],),
            )
        if tiene_nombre and not master_row["nombre"]:
            connection.execute(
                "UPDATE users SET nombre = 'Auditoría' WHERE id = ?",
                (master_row["id"],),
            )


def inicializar_esquema(connection: sqlite3.Connection) -> None:
    """Crea tablas, índices, migraciones y cuenta Master inicial en SQLite."""
    migrar_esquema(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (
                role IN ('master', 'administrador', 'operador', 'consulta', 'picker', 'despachador')
            ),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1)),
            nombre TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS api_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at REAL NOT NULL,
            last_active REAL NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_sessions_last_active ON api_sessions(last_active)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            key_hash TEXT PRIMARY KEY,
            client_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'operador',
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            created_at TEXT NOT NULL,
            last_used TEXT NOT NULL DEFAULT ''
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(active)"
    )
    migrar_columnas(connection)
    asegurar_indices_y_triggers(connection)
    asegurar_usuario_master(connection)
