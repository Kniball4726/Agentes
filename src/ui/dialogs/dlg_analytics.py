"""Fachada compatible para diálogos analíticos: dashboard, auditoría, estadísticas y notificaciones."""

from __future__ import annotations

from ._shared import resolve_stock_manager
from .analytics_auditoria_notif import (
    mostrar_notificaciones_admin,
    mostrar_registro_auditoria,
)
from .analytics_metricas import (
    mostrar_dashboard_metricas,
    mostrar_estadisticas,
)


def _get_stock_manager(interfaz=None):
    """Devuelve la clase StockManager vigente mediante inyección en `interfaz`."""
    return resolve_stock_manager(interfaz)


__all__ = [
    "_get_stock_manager",
    "mostrar_dashboard_metricas",
    "mostrar_estadisticas",
    "mostrar_notificaciones_admin",
    "mostrar_registro_auditoria",
]
