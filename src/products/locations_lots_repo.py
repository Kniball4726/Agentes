"""Fachada compuesta de multi-ubicación de depósito y trazabilidad de lotes FEFO.

Mantiene compatibilidad de importación y delega declarativamente en los repositorios
especializados ``WarehouseLocationsRepository`` y ``FefoLotsRepository``.
"""

from __future__ import annotations

import sqlite3
from typing import Callable

from ..core.delegation import DelegadoAtributo
from .locations_repo import (
    VALID_ZONE_TYPES,
    WarehouseLocationsRepository,
    descontar_ubicaciones_en_tx,
    map_location_row,
    normalizar_ubicacion,
    normalizar_zona,
    sincronizar_ubicacion_principal_en_tx,
)
from .lots_fefo_repo import (
    VALID_LOT_STATES,
    FefoLotsRepository,
    consumir_lotes_fefo_en_tx,
    map_lot_row,
    normalizar_fecha_vencimiento,
    planificar_lotes_fefo_en_tx,
    trasladar_lotes_en_tx,
)

__all__ = [
    "FefoLotsRepository",
    "LocationsLotsRepository",
    "VALID_LOT_STATES",
    "VALID_ZONE_TYPES",
    "WarehouseLocationsRepository",
    "consumir_lotes_fefo_en_tx",
    "descontar_ubicaciones_en_tx",
    "map_location_row",
    "map_lot_row",
    "normalizar_fecha_vencimiento",
    "normalizar_ubicacion",
    "normalizar_zona",
    "planificar_lotes_fefo_en_tx",
    "sincronizar_ubicacion_principal_en_tx",
    "trasladar_lotes_en_tx",
]


class LocationsLotsRepository:
    """Fachada unificada de multi-ubicación logística por zona y lotes con caducidad FEFO."""

    def __init__(
        self,
        connect_fn: Callable[[], sqlite3.Connection],
        invalidate_cache_cb: Callable[[], None] | None = None,
    ) -> None:
        self._connect = connect_fn
        self._invalidar_cache = invalidate_cache_cb
        self.locations = WarehouseLocationsRepository(
            connect_fn,
            invalidate_cache_cb,
            transfer_lots_tx=trasladar_lotes_en_tx,
        )
        self.lots = FefoLotsRepository(connect_fn, invalidate_cache_cb)

    def _notificar_cambio_catalogo(self) -> None:
        if self._invalidar_cache is not None:
            self._invalidar_cache()

    _map_location_row = staticmethod(map_location_row)
    _map_lot_row = staticmethod(map_lot_row)
    _trasladar_lotes_en_tx = staticmethod(trasladar_lotes_en_tx)

    # --- Multi-ubicación logística (WarehouseLocationsRepository) ---
    asignar_ubicacion_producto = DelegadoAtributo("locations", WarehouseLocationsRepository)
    listar_ubicaciones_producto = DelegadoAtributo("locations", WarehouseLocationsRepository)
    listar_ubicaciones_mapa = DelegadoAtributo("locations", WarehouseLocationsRepository)
    transferir_entre_ubicaciones = DelegadoAtributo("locations", WarehouseLocationsRepository)

    # --- Lotes y caducidad FEFO (FefoLotsRepository) ---
    registrar_lote = DelegadoAtributo("lots", FefoLotsRepository)
    listar_lotes_fefo = DelegadoAtributo("lots", FefoLotsRepository)
    consumir_lotes_fefo = DelegadoAtributo("lots", FefoLotsRepository)
    listar_lotes_proximos_vencer = DelegadoAtributo("lots", FefoLotsRepository)
