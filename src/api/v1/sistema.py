"""Endpoints de estado, telemetría y diagnóstico operativo del sistema."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Request

from ..deps import (
    _sesiones_activas,
    get_optional_current_user,
    get_order_store,
    get_product_store,
    get_user_store,
    obtener_contexto_api_actual,
)
from ..schemas import EstadoSistemaResponse
from ...alertas_programadas import obtener_estado_planificador
from ...auth import UserStore
from ...core.environment import get_db_path
from ...inventory import StockManager
from ...server_app.network_utils import obtener_ip_local
from ...system_telemetry import medir_latencia_sqlite, obtener_metricas_logs, obtener_telemetria_sistema

router = APIRouter(prefix="/sistema", tags=["Sistema"])


@router.get("/ping", summary="Verificación de conectividad ultrarrápida (Heartbeat)")
async def ping():
    """Endpoint ligero sin autenticación para comprobar que el servidor responde."""
    return {"status": "pong", "timestamp": time.time()}


def _resolver_store_override(request: Request, provider, fallback: Any) -> Any:
    override = request.app.dependency_overrides.get(provider)
    if callable(override):
        try:
            return override()
        except Exception:
            return fallback
    return fallback


def _medir_latencias_bd(
    user_store: Any,
    product_store: Any,
    order_store: Any,
) -> Dict[str, Optional[float]]:
    ruta_users = getattr(user_store, "database_path", None) or get_db_path("usuarios.sqlite3")
    ruta_prod = getattr(product_store, "database_path", None) or get_db_path("productos.sqlite3")
    ruta_ord = getattr(order_store, "database_path", None) or get_db_path("pedidos.sqlite3")

    lat_users = medir_latencia_sqlite(ruta_users)
    lat_prod = medir_latencia_sqlite(ruta_prod)
    lat_ord = medir_latencia_sqlite(ruta_ord)
    muestras = [v for v in (lat_users, lat_prod, lat_ord) if v is not None]
    promedio = round(sum(muestras) / len(muestras), 2) if muestras else None
    return {
        "usuarios_ms": lat_users,
        "productos_ms": lat_prod,
        "pedidos_ms": lat_ord,
        "promedio_ms": promedio,
    }


def _recolectar_colas_y_logs(order_store: Any) -> Dict[str, Any]:
    try:
        pendientes_excel = len(StockManager.obtener_pendientes_sincronizacion_excel())
    except Exception:
        pendientes_excel = 0

    pendientes_cierre = 0
    if order_store is not None and hasattr(order_store, "contar_pedidos_pendientes_cierre_por_tipo"):
        try:
            conteo = order_store.contar_pedidos_pendientes_cierre_por_tipo()
            pendientes_cierre = int(conteo.get("total", 0))
        except Exception:
            pendientes_cierre = 0

    logs_info = obtener_metricas_logs()
    return {
        "excel_sync_pendientes": pendientes_excel,
        "pedidos_pendientes_cierre": pendientes_cierre,
        **logs_info,
    }


@router.get("/estado", response_model=EstadoSistemaResponse, summary="Estado general y métricas del servidor")
async def estado_servidor(
    request: Request,
    user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    user_store: UserStore = Depends(get_user_store),
):
    """Informa estado del servidor; la telemetría operativa exige autenticación."""
    if user is None:
        return EstadoSistemaResponse(
            ok=True,
            version="1.0.0",
            servidor_hora="",
            ip_local="",
            sesiones_activas=0,
            modo_conexion="",
        )

    contexto = obtener_contexto_api_actual()
    telemetria = obtener_telemetria_sistema()
    sesiones_ctx = contexto.sesiones_activas if contexto.sesiones_activas else _sesiones_activas
    product_store = _resolver_store_override(
        request, get_product_store, getattr(contexto, "_product_store", None)
    )
    order_store = _resolver_store_override(
        request, get_order_store, getattr(contexto, "_order_store", None)
    )
    return EstadoSistemaResponse(
        ok=True,
        version="1.0.0",
        servidor_hora=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ip_local=obtener_ip_local(),
        sesiones_activas=len(sesiones_ctx),
        modo_conexion=os.environ.get("STOCKAGENT_SCHEME", "http").upper(),
        sqlite_latencia_ms=_medir_latencias_bd(user_store, product_store, order_store),
        colas_y_logs=_recolectar_colas_y_logs(order_store),
        planificador_alertas=obtener_estado_planificador(),
        salud_sistema=telemetria.estado_salud,
    )
