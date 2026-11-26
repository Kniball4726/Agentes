"""Fachada de compatibilidad para gestión de edición y baja de pedidos.

Módulos internos por responsabilidad:
- `pedidos_edicion`: bloqueo de concurrencia y edición de datos de pedidos.
- `pedidos_baja`: anulación, desarmado lógico, eliminación física y restitución de stock.
"""

from __future__ import annotations

from .dlg_ajuste_bultos import mostrar_dialogo_ajuste_bultos_express
from .pedidos_baja import (
    _resolver_sm_cls,
    _restituir_stock_pedido,
    construir_botones_baja_pedido,
    mostrar_dialogo_confirmar_anulacion_pedido,
    mostrar_dialogo_confirmar_desarmar_pedido,
    mostrar_dialogo_confirmar_eliminacion_pedido,
)
from .pedidos_edicion import _mostrar_dialogo_bloqueo_pedido, mostrar_dialogo_editar_pedido

__all__ = [
    "_mostrar_dialogo_bloqueo_pedido",
    "_resolver_sm_cls",
    "_restituir_stock_pedido",
    "construir_botones_baja_pedido",
    "mostrar_dialogo_ajuste_bultos_express",
    "mostrar_dialogo_confirmar_anulacion_pedido",
    "mostrar_dialogo_confirmar_desarmar_pedido",
    "mostrar_dialogo_confirmar_eliminacion_pedido",
    "mostrar_dialogo_editar_pedido",
]
