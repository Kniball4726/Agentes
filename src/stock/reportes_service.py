"""Fachada unificada de reportes operativos en PDF y Excel (.xlsx)."""

from .report_styles import _ReporteNumberedCanvas, _autoajustar_columnas_excel
from .reports_inventory import (
    generar_reporte_auditoria_inventario_fisico,
    generar_reporte_planilla_conteo_fisico,
)
from .reports_kardex import (
    generar_reporte_kardex_producto,
    generar_reporte_rotacion_consumo,
)
from .reports_movements import (
    generar_reporte_descuento_operario_canales,
    generar_reporte_movimientos_estandar,
)
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
    "generar_reporte_descuento_operario_canales",
    "generar_reporte_movimientos_estandar",
    "generar_reporte_planilla_conteo_fisico",
    "generar_reporte_auditoria_inventario_fisico",
    "generar_reporte_kardex_producto",
    "generar_reporte_rotacion_consumo",
]
