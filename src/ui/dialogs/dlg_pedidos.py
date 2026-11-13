"""Módulo fachada para diálogos modales de creación, edición, anulación y desarmado de pedidos."""

from __future__ import annotations

import sys

from ...stock_manager import StockManager as _DefaultStockManager
from .pedidos_crear import mostrar_dialogo_crear_pedido
from .pedidos_gestion import (
    _restituir_stock_pedido,
    mostrar_dialogo_confirmar_anulacion_pedido,
    mostrar_dialogo_confirmar_desarmar_pedido,
    mostrar_dialogo_editar_pedido,
)


def _get_stock_manager_cls():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


__all__ = [
    "_get_stock_manager_cls",
    "_restituir_stock_pedido",
    "mostrar_dialogo_crear_pedido",
    "mostrar_dialogo_confirmar_anulacion_pedido",
    "mostrar_dialogo_editar_pedido",
    "mostrar_dialogo_confirmar_desarmar_pedido",
]
