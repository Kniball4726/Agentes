"""Subpaquete modular para la gestión de inventario, stock y sincronización Excel."""

from .excel_exporter import exportar_catalogo_a_excel
from .manager import StockManager

__all__ = ["StockManager", "exportar_catalogo_a_excel"]
