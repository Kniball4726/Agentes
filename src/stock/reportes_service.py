"""Fachada unificada de reportes operativos en PDF y Excel (.xlsx)."""

from .report_styles import _ReporteNumberedCanvas, _autoajustar_columnas_excel
from .reports_ops import (
    generar_reporte_cierres_historicos,
    generar_reporte_pedidos_despacho,
)
from .reports_stock import (
    generar_reporte_catalogo_stock,
    generar_reporte_stock_critico,
)

__all__ = [
    "_ReporteNumberedCanvas",
    "_autoajustar_columnas_excel",
    "generar_reporte_stock_critico",
    "generar_reporte_catalogo_stock",
    "generar_reporte_pedidos_despacho",
    "generar_reporte_cierres_historicos",
]
