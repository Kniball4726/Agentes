"""Motor centralizado de migraciones versionadas para bases SQLite (`PRAGMA user_version`)."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
import sqlite3
from typing import Callable, Sequence

logger = logging.getLogger("stockagent.sqlite_migrations")


@dataclass(frozen=True)
class MigrationStep:
    """Representa una etapa versionada e idempotente de migración de esquema SQLite."""

    version: int
    description: str
    migrate_fn: Callable[[sqlite3.Connection], None]


def get_user_version(connection: sqlite3.Connection) -> int:
    """Retorna el número de versión actual almacenado en `PRAGMA user_version`."""
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def set_user_version(connection: sqlite3.Connection, version: int) -> None:
    """Actualiza el número de versión de esquema mediante `PRAGMA user_version`."""
    connection.execute(f"PRAGMA user_version = {int(version)}")


def _tiene_tablas_usuario(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
          AND name != 'schema_migrations'
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def _obtener_version_dominio(connection: sqlite3.Connection, domain: str | None) -> int:
    if domain:
        existe = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations' LIMIT 1"
        ).fetchone()
        if existe is not None:
            row = connection.execute(
                "SELECT version FROM schema_migrations WHERE domain = ?",
                (domain,),
            ).fetchone()
            if row is not None:
                return int(row[0])
            hay_otros = connection.execute("SELECT 1 FROM schema_migrations LIMIT 1").fetchone()
            if hay_otros is not None:
                return 0
    return get_user_version(connection)


def _registrar_version_dominio(
    connection: sqlite3.Connection,
    domain: str | None,
    version: int,
) -> None:
    if domain:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                domain TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO schema_migrations (domain, version, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(domain) DO UPDATE SET
                version = excluded.version,
                updated_at = CURRENT_TIMESTAMP
            """,
            (domain, int(version)),
        )
    set_user_version(connection, max(get_user_version(connection), int(version)))


def _es_archivo_bd_existente(database_path: Path | str | None) -> Path | None:
    if database_path is None:
        return None
    raw = str(database_path).strip()
    if not raw or raw == ":memory:" or raw.startswith("file::memory:"):
        return None
    ruta = Path(database_path)
    try:
        if ruta.exists() and ruta.is_file() and ruta.stat().st_size > 0:
            return ruta
    except OSError:
        return None
    return None


def _respaldar_antes_de_migrar(
    connection: sqlite3.Connection,
    database_path: Path,
    version_actual: int,
    version_objetivo: int,
) -> Path | None:
    """Genera un backup consistente en caliente mediante `sqlite3.Connection.backup`."""
    carpeta_backups = database_path.parent / "backups_migraciones"
    carpeta_backups.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destino = carpeta_backups / (
        f"{database_path.stem}_v{version_actual}_a_v{version_objetivo}_{ts}.sqlite3"
    )
    with closing(sqlite3.connect(destino, timeout=10.0)) as backup_conn:
        connection.backup(backup_conn)
    logger.info(
        "Backup pre-migración generado para %s (v%s -> v%s): %s",
        database_path.name,
        version_actual,
        version_objetivo,
        destino,
    )
    return destino


def _asegurar_fuera_de_transaccion(connection: sqlite3.Connection) -> None:
    """Cierra transacciones implícitas pendientes antes de cambiar PRAGMAs como foreign_keys."""
    if connection.in_transaction:
        connection.commit()


def aplicar_migraciones_sqlite(
    connection: sqlite3.Connection,
    database_path: Path | str | None,
    steps: Sequence[MigrationStep],
    *,
    domain: str | None = None,
    crear_backup_si_existe: bool = True,
) -> int:
    """Aplica secuencialmente migraciones pendientes y actualiza `PRAGMA user_version`.

    Cuando `domain` está especificado, también registra el progreso por dominio en la tabla
    `schema_migrations`, permitiendo que múltiples módulos (`auth`, `products`, `orders`)
    coexistan sin colisión incluso si comparten el mismo archivo SQLite.

    Si la base ya tenía tablas creadas (por ejemplo una base heredada con `user_version == 0`
    o de una versión menor a la objetivo), genera un backup atómico en
    `backups_migraciones/` antes de ejecutar los pasos pendientes.
    """
    if not steps:
        return _obtener_version_dominio(connection, domain)

    ordenados = sorted(steps, key=lambda s: s.version)
    versiones = [s.version for s in ordenados]
    if any(v <= 0 for v in versiones) or len(set(versiones)) != len(versiones):
        raise ValueError("Las versiones de migración deben ser enteros positivos únicos.")

    version_objetivo = ordenados[-1].version
    version_actual = _obtener_version_dominio(connection, domain)
    if version_actual >= version_objetivo:
        return version_actual

    pendientes = [step for step in ordenados if step.version > version_actual]
    archivo_existente = _es_archivo_bd_existente(database_path) if crear_backup_si_existe else None
    if archivo_existente is not None and _tiene_tablas_usuario(connection):
        _asegurar_fuera_de_transaccion(connection)
        _respaldar_antes_de_migrar(connection, archivo_existente, version_actual, version_objetivo)

    for step in pendientes:
        _asegurar_fuera_de_transaccion(connection)
        step.migrate_fn(connection)
        _asegurar_fuera_de_transaccion(connection)
        _registrar_version_dominio(connection, domain, step.version)
        _asegurar_fuera_de_transaccion(connection)
        logger.debug(
            "Migración SQLite v%s aplicada (%s/%s): %s",
            step.version,
            domain or "default",
            archivo_existente.name if archivo_existente else "db",
            step.description,
        )

    return version_objetivo
