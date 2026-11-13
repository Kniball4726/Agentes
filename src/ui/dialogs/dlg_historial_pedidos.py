"""Módulo fachada para diálogos de historial de pedidos e impresión de comprobantes."""

from ...paths import application_root  # noqa: F401 - patch target en tests
from .historial_archivos import (
    abrir_comprobante_pedido,
    abrir_descuento_pedido,
    buscar_archivo_comprobante,
    buscar_archivo_descuento,
)
from .historial_detalle import mostrar_detalle_pedido_modal, mostrar_imprimir_descuentos
from .historial_vista import mostrar_historial_pedidos

__all__ = [
    "application_root",
    "buscar_archivo_comprobante",
    "buscar_archivo_descuento",
    "abrir_comprobante_pedido",
    "abrir_descuento_pedido",
    "mostrar_detalle_pedido_modal",
    "mostrar_historial_pedidos",
    "mostrar_imprimir_descuentos",
]
