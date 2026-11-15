"""Fachada compatible para diálogos analíticos: dashboard, auditoría, estadísticas y notificaciones."""

from __future__ import annotations

import sys

from ...inventory import StockManager as _DefaultStockManager
from .analytics_auditoria_notif import (
    mostrar_notificaciones_admin,
    mostrar_registro_auditoria,
)
from .analytics_metricas import (
    mostrar_dashboard_metricas,
    mostrar_estadisticas,
)


def _get_stock_manager():
    """Devuelve la clase StockManager vigente (respetando mocks sobre src.flet_gui)."""
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


__all__ = [
    "_get_stock_manager",
    "mostrar_dashboard_metricas",
    "mostrar_estadisticas",
    "mostrar_notificaciones_admin",
    "mostrar_registro_auditoria",
]
