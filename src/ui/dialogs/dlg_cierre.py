"""Módulo fachada para el Cierre de Jornada y auditoría de turnos.

Re-exporta las funciones especializadas desde src.ui.dialogs.cierre:
- hoja_ruta: resolver_archivos_cierre, gestionar_hoja_ruta_cierre, _get_stock_manager_cls
- dlg_cierre_operario: mostrar_dialogo_cierre_jornada
- dlg_cierres_admin: mostrar_detalle_pedidos_cierre, mostrar_dialogo_cierres_operarios
"""

from .cierre.hoja_ruta import (
    resolver_archivos_cierre,
    gestionar_hoja_ruta_cierre,
    _get_stock_manager_cls,
)
from .cierre.dlg_cierre_operario import mostrar_dialogo_cierre_jornada
from .cierre.dlg_cierres_admin import (
    mostrar_detalle_pedidos_cierre,
    mostrar_dialogo_cierres_operarios,
)

__all__ = [
    "_get_stock_manager_cls",
    "resolver_archivos_cierre",
    "gestionar_hoja_ruta_cierre",
    "mostrar_dialogo_cierre_jornada",
    "mostrar_detalle_pedidos_cierre",
    "mostrar_dialogo_cierres_operarios",
]
