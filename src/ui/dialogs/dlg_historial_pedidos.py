"""Módulo fachada para diálogos de historial de pedidos e impresión de comprobantes."""

from ...paths import application_root  # noqa: F401 - patch target en tests
from .historial_archivos import (
    abrir_comprobante_pedido as _abrir_comprobante_base,
    abrir_descuento_pedido as _abrir_descuento_base,
    buscar_archivo_comprobante as _buscar_comprobante_base,
    buscar_archivo_descuento as _buscar_descuento_base,
)
from .historial_detalle import mostrar_detalle_pedido_modal, mostrar_imprimir_descuentos
from .historial_vista import mostrar_historial_pedidos


def buscar_archivo_comprobante(pedido, interfaz=None):
    """Busca la ruta del comprobante usando la raíz inyectada o `application_root`."""
    return _buscar_comprobante_base(pedido, interfaz=interfaz, app_root_fn=lambda: application_root())


def buscar_archivo_descuento(pedido, interfaz=None):
    """Busca la ruta del informe de descuento usando la raíz inyectada o `application_root`."""
    return _buscar_descuento_base(pedido, interfaz=interfaz, app_root_fn=lambda: application_root())


def abrir_comprobante_pedido(interfaz, ped):
    """Abre el comprobante del pedido respetando `application_root` e inyección."""
    return _abrir_comprobante_base(interfaz, ped, app_root_fn=lambda: application_root())


def abrir_descuento_pedido(interfaz, ped):
    """Abre el informe de descuento del pedido respetando `application_root` e inyección."""
    return _abrir_descuento_base(interfaz, ped, app_root_fn=lambda: application_root())

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
