"""Motor de búsqueda rápida universal para la Paleta de Comandos."""

from __future__ import annotations

from typing import Any
from .command_registry import TipoComando


def buscar_comandos(query: str, comandos: list[TipoComando]) -> list[TipoComando]:
    """Filtra comandos coincidentes por título o descripción."""
    q = (query or "").strip().lower()
    if not q:
        return []
    return [
        (t, d, ic, col, cb)
        for t, d, ic, col, cb in comandos
        if q in t.lower() or q in d.lower()
    ]


def buscar_productos_palette(query: str, product_store: Any, limite: int = 5) -> list[Any]:
    """Busca productos en stock coincidentes con la consulta."""
    q = (query or "").strip().lower()
    if not q or product_store is None:
        return []
    try:
        if hasattr(product_store, "buscar_productos"):
            return product_store.buscar_productos(q)[:limite]
    except Exception:
        pass
    return []


def buscar_clientes_palette(query: str, order_store: Any, limite: int = 4) -> list[Any]:
    """Busca clientes activos coincidentes con la consulta."""
    q = (query or "").strip().lower()
    if not q or order_store is None:
        return []
    try:
        if hasattr(order_store, "buscar_clientes"):
            return order_store.buscar_clientes(q)[:limite]
    except Exception:
        pass
    return []


def buscar_pedidos_palette(query: str, order_store: Any, limite: int = 5) -> list[Any]:
    """Busca pedidos y remitos coincidentes con la consulta."""
    q = (query or "").strip().lower()
    if not q or order_store is None:
        return []
    try:
        if hasattr(order_store, "listar_pedidos"):
            peds_todos = order_store.listar_pedidos(limit=150)
            return [
                p for p in peds_todos
                if q in (getattr(p, "cliente", "") or "").lower()
                or q in (getattr(p, "nota_pedido", "") or "").lower()
                or q in str(getattr(p, "numero_pedido", "") or "").lower()
                or q in str(getattr(p, "numero_guia", "") or "").lower()
            ][:limite]
    except Exception:
        pass
    return []
