"""Fachada compuesta para lectura y escritura del catálogo de productos."""

from __future__ import annotations

from .catalog_read_repo import CatalogReadRepository
from .catalog_write_repo import CatalogWriteRepository
from .protocols import CatalogCacheHostProtocol


class CatalogRepository:
    """Agrupa las operaciones de lectura cacheada y escritura transaccional del catálogo."""

    def __init__(self, host: CatalogCacheHostProtocol) -> None:
        self.read = CatalogReadRepository(host)
        self.write = CatalogWriteRepository(host)


__all__ = ["CatalogReadRepository", "CatalogWriteRepository", "CatalogRepository"]
