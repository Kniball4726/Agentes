"""Submódulo de vistas y renderizadores especializados del Dashboard."""

from __future__ import annotations

from .auditoria_view import renderizar_auditoria_master
from .pedidos_turno_view import renderizar_pedidos_preparados_turno
from .fechas_view import _obtener_resumen_fechas_operador, renderizar_pedidos_armados_por_fecha
from .informes_view import renderizar_informes_generados

__all__ = [
    "renderizar_auditoria_master",
    "renderizar_pedidos_preparados_turno",
    "_obtener_resumen_fechas_operador",
    "renderizar_pedidos_armados_por_fecha",
    "renderizar_informes_generados",
]
