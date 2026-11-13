"""Endpoints de estado, telemetría y diagnóstico del sistema."""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends

from ..deps import _sesiones_activas, get_optional_current_user
from ..schemas import EstadoSistemaResponse
from ...server_app.network_utils import obtener_ip_local

router = APIRouter(prefix="/sistema", tags=["Sistema"])


@router.get("/ping", summary="Verificación de conectividad ultrarrápida (Heartbeat)")
async def ping():
    """Endpoint ligero sin autenticación para comprobar que el servidor responde."""
    return {"status": "pong", "timestamp": time.time()}


@router.get("/estado", response_model=EstadoSistemaResponse, summary="Estado general del servidor")
async def estado_servidor(
    user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    """Informa estado del servidor; la telemetría de red y sesiones exige autenticación."""
    if user is None:
        return EstadoSistemaResponse(
            ok=True,
            version="1.0.0",
            servidor_hora="",
            ip_local="",
            sesiones_activas=0,
            modo_conexion="",
        )
    return EstadoSistemaResponse(
        ok=True,
        version="1.0.0",
        servidor_hora=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ip_local=obtener_ip_local(),
        sesiones_activas=len(_sesiones_activas),
        modo_conexion=os.environ.get("STOCKAGENT_SCHEME", "http").upper(),
    )
