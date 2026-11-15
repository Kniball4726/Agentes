"""Contratos estructurales (Protocols) para composición de repositorios de productos."""

from __future__ import annotations

import sqlite3
import threading
from typing import Protocol, runtime_checkable


@runtime_checkable
class CatalogCacheHostProtocol(Protocol):
    """Contrato mínimo para lectura cacheada de catálogo y conexión SQLite."""

    _cache_sku: dict[str, sqlite3.Row]
    _cache_barcode: dict[str, sqlite3.Row]
    _cache_lock: threading.Lock
    _cache_data_version: int | None
    _cache_ts: float

    def _connect(self) -> sqlite3.Connection: ...
    def _es_cache_valido(self, connection: sqlite3.Connection | None = None) -> bool: ...


@runtime_checkable
class CatalogWriteHostProtocol(Protocol):
    """Contrato mínimo para escrituras transaccionales del catálogo con invalidación."""

    def _connect(self) -> sqlite3.Connection: ...
    def invalidar_cache(self) -> None: ...
