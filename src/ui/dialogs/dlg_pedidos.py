"""Módulo fachada para diálogos modales de creación, edición, anulación y desarmado de pedidos."""

from __future__ import annotations

from ._shared import resolve_stock_manager
from .pedidos_crear import mostrar_dialogo_crear_pedido
from .pedidos_gestion import (
    _restituir_stock_pedido,
    mostrar_dialogo_confirmar_anulacion_pedido,
    mostrar_dialogo_confirmar_desarmar_pedido,
    mostrar_dialogo_confirmar_eliminacion_pedido,
    mostrar_dialogo_editar_pedido,
    mostrar_dialogo_ajuste_bultos_express,
)


def _get_stock_manager_cls(interfaz=None):
    """Devuelve la clase StockManager vigente mediante inyección en `interfaz`."""
    return resolve_stock_manager(interfaz)


__all__ = [
    "_get_stock_manager_cls",
    "_restituir_stock_pedido",
    "mostrar_dialogo_crear_pedido",
    "mostrar_dialogo_confirmar_anulacion_pedido",
    "mostrar_dialogo_editar_pedido",
    "mostrar_dialogo_ajuste_bultos_express",
    "mostrar_dialogo_confirmar_desarmar_pedido",
    "mostrar_dialogo_confirmar_eliminacion_pedido",
]
