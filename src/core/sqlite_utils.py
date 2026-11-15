"""Utilidades centralizadas para apertura y cierre determinista de conexiones SQLite."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator


def open_sqlite_connection(
    database_path: Path | str,
    *,
    timeout: float = 10.0,
    row_factory: bool = True,
    foreign_keys: bool = True,
    wal: bool = True,
    synchronous_normal: bool = False,
    temp_store_memory: bool = False,
    busy_timeout_ms: int | None = 10000,
) -> sqlite3.Connection:
    """Abre una conexión SQLite configurada con PRAGMAs seguros.

    Si ocurre un error durante la inicialización de la sesión, cierra la
    conexión de inmediato antes de propagar la excepción.
    """
    connection = sqlite3.connect(database_path, timeout=timeout)
    try:
        if row_factory:
            connection.row_factory = sqlite3.Row
        if foreign_keys:
            connection.execute("PRAGMA foreign_keys = ON")
        if wal:
            connection.execute("PRAGMA journal_mode = WAL")
        if synchronous_normal:
            connection.execute("PRAGMA synchronous = NORMAL")
        if temp_store_memory:
            connection.execute("PRAGMA temp_store = MEMORY")
        if busy_timeout_ms is not None:
            connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    except Exception:
        connection.close()
        raise
    return connection


@contextmanager
def sqlite_connection(
    database_path: Path | str,
    *,
    timeout: float = 10.0,
    row_factory: bool = True,
    foreign_keys: bool = True,
    wal: bool = True,
    synchronous_normal: bool = False,
    temp_store_memory: bool = False,
    busy_timeout_ms: int | None = 10000,
) -> Iterator[sqlite3.Connection]:
    """Context manager que abre y cierra determinísticamente una conexión SQLite."""
    with closing(
        open_sqlite_connection(
            database_path,
            timeout=timeout,
            row_factory=row_factory,
            foreign_keys=foreign_keys,
            wal=wal,
            synchronous_normal=synchronous_normal,
            temp_store_memory=temp_store_memory,
            busy_timeout_ms=busy_timeout_ms,
        )
    ) as connection:
        yield connection
