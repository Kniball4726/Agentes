"""Fachada repositorio mixin para catálogo de productos, combinando lectura y escritura."""

from __future__ import annotations

from .catalog_read_repo import CatalogReadMixin
from .catalog_write_repo import CatalogWriteMixin


class CatalogRepositoryMixin(CatalogReadMixin, CatalogWriteMixin):
    """Mixin compuesto para consultas, altas, ediciones y búsqueda del catálogo."""


__all__ = ["CatalogReadMixin", "CatalogWriteMixin", "CatalogRepositoryMixin"]
