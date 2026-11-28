"""Inicialización y migraciones automáticas del esquema SQLite de autenticación."""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
import sqlite3

from ..core.sqlite_migrations import MigrationStep, aplicar_migraciones_sqlite
from .models import DEFAULT_MASTER_PASSWORD, _master_default_credentials, _master_env_password
from .password import hash_clave, verificar_clave

logger = logging.getLogger(__name__)

AUTH_SCHEMA_VERSION = 3
ARCHIVO_CLAVE_INICIAL = "PRIMER_INICIO_MASTER.txt"


def _publicar_clave_inicial(connection: sqlite3.Connection, usuario: str, clave: str) -> None:
    """Deja la clave aleatoria inicial en un archivo local junto a la base (solo si no hay clave en .env)."""
    try:
        fila = connection.execute("PRAGMA database_list").fetchone()
        ruta_db = fila[2] if fila else ""
    except sqlite3.Error:
        ruta_db = ""
    if not ruta_db:
        logger.warning("Usuario master '%s' creado con clave aleatoria en base en memoria.", usuario)
        return
    destino = Path(ruta_db).parent / ARCHIVO_CLAVE_INICIAL
    try:
        destino.write_text(
            "StockAgent - credenciales iniciales del usuario Master\n"
            f"Usuario: {usuario}\n"
            f"Clave temporal: {clave}\n\n"
            "Se exigirá cambiarla en el primer inicio de sesión. "
            "Elimine este archivo una vez que haya ingresado.\n",
            encoding="utf-8",
        )
        try:
            os.chmod(destino, 0o600)
        except OSError:
            pass
        logger.warning("Usuario master '%s' creado. Clave temporal guardada en: %s", usuario, destino)
    except OSError as exc:
        logger.error("No se pudo guardar la clave inicial del master (%s). Defina STOCKAGENT_MASTER_PASSWORD.", exc)


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
    def_user, _ = _master_default_credentials()
    master_row = connection.execute(query, (def_user,)).fetchone()
    if master_row is None:
        # Sin clave explícita en el entorno NO se usa una clave conocida: se genera una aleatoria.
        clave_env = _master_env_password()
        clave_inicial = clave_env or secrets.token_urlsafe(12)
        pwd_hash = hash_clave(clave_inicial)
        connection.execute(
            """
            INSERT INTO users (username, password_hash, role, active, must_change_password, nombre, email)
            VALUES (?, ?, 'master', 1, 1, 'Auditoría', '')
            """,
            (def_user, pwd_hash),
        )
        if not clave_env:
            _publicar_clave_inicial(connection, def_user, clave_inicial)
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


def _crear_tablas_base(connection: sqlite3.Connection) -> None:
    """Crea tablas base de autenticación cuando aún no existen."""
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


def _aplicar_migracion_roles_y_columnas(connection: sqlite3.Connection) -> None:
    migrar_esquema(connection)
    migrar_columnas(connection)


_AUTH_MIGRATION_STEPS: tuple[MigrationStep, ...] = (
    MigrationStep(1, "Tablas base de usuarios, intentos y sesiones API", _crear_tablas_base),
    MigrationStep(2, "Migración de CHECK roles y columnas incrementales", _aplicar_migracion_roles_y_columnas),
    MigrationStep(3, "Índices únicos y trigger updated_at de usuarios", asegurar_indices_y_triggers),
)


def inicializar_esquema(
    connection: sqlite3.Connection,
    database_path: Path | str | None = None,
) -> None:
    """Crea tablas, ejecuta migraciones versionadas y garantiza la cuenta Master inicial."""
    aplicar_migraciones_sqlite(connection, database_path, _AUTH_MIGRATION_STEPS, domain="auth")
    asegurar_usuario_master(connection)
