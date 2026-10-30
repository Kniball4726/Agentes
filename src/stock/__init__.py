"""Módulo de gestión y dominio de stock, inventario y reportes."""

from .models import AlertaStock, RegistroDescuento, ReporteStock
from .reports import (
    copiar_estilo_fila,
    guardar_informe_pdf,
    guardar_informe_xls,
)
from .replenishment import generar_pedido_sugerido_fabrica_excel
from .physical_inventory import (
    comparar_stock_fisico_dict,
    generar_documento_comparativo_excel,
)

__all__ = [
    "RegistroDescuento",
    "ReporteStock",
    "copiar_estilo_fila",
    "guardar_informe_pdf",
    "guardar_informe_xls",
    "generar_pedido_sugerido_fabrica_excel",
    "comparar_stock_fisico_dict",
    "generar_documento_comparativo_excel",
]
