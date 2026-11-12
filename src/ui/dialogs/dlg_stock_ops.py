"""Módulo fachada para operaciones y diálogos de stock.

Re-exporta los diálogos especializados para mantener retrocompatibilidad total:
- dlg_pedido_fabrica: generar_pedido_fabrica
- dlg_ingreso_fabrica: mostrar_ingreso_fabrica
- dlg_mercado_full: mostrar_descuento_mercado_full
- dlg_mercadolibre_descuento: mostrar_descuento_mercado_libre
- dlg_stock_fisico: mostrar_stock_fisico_operario, mostrar_comparativa_stock_fisico_admin
"""

from .dlg_pedido_fabrica import generar_pedido_fabrica, _get_stock_manager, safe_focus
from .dlg_ingreso_fabrica import mostrar_ingreso_fabrica
from .dlg_mercado_full import mostrar_descuento_mercado_full
from .dlg_mercadolibre_descuento import mostrar_descuento_mercado_libre
from .dlg_stock_fisico import (
    mostrar_stock_fisico_operario,
    mostrar_comparativa_stock_fisico_admin,
)

__all__ = [
    "generar_pedido_fabrica",
    "mostrar_ingreso_fabrica",
    "mostrar_descuento_mercado_full",
    "mostrar_descuento_mercado_libre",
    "mostrar_stock_fisico_operario",
    "mostrar_comparativa_stock_fisico_admin",
    "safe_focus",
    "_get_stock_manager",
]
