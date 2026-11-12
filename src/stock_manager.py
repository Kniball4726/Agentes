"""Módulo de compatibilidad para StockManager.

Redirige a la implementación modular en src.inventory y src.stock.models.
"""

import openpyxl

from .inventory import StockManager
from .remito_parser import normalizar_codigo
from .stock.models import AlertaStock, RegistroDescuento, ReporteStock

__all__ = [
    "StockManager",
    "AlertaStock",
    "RegistroDescuento",
    "ReporteStock",
    "normalizar_codigo",
    "openpyxl",
]
