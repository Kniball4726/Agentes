"""Submódulo de catálogo y búsqueda de comandos rápidos."""

from __future__ import annotations

from .command_registry import (
    TipoComando,
    obtener_catalogo_completo_comandos,
    obtener_comandos_rol,
    obtener_comandos_sistema,
)
from .command_search import (
    buscar_clientes_palette,
    buscar_comandos,
    buscar_pedidos_palette,
    buscar_productos_palette,
)

__all__ = [
    "TipoComando",
    "obtener_catalogo_completo_comandos",
    "obtener_comandos_rol",
    "obtener_comandos_sistema",
    "buscar_comandos",
    "buscar_productos_palette",
    "buscar_clientes_palette",
    "buscar_pedidos_palette",
]
