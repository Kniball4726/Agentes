"""Gestión de ciclo de vida y notificaciones de red para el servicio System Tray."""

from __future__ import annotations

from typing import Callable, Optional

from ..logger_config import configurar_logging
from .tray_controller import TrayIconServidor

logger = configurar_logging()

_INSTANCIA_ACTIVA: Optional[TrayIconServidor] = None


def iniciar_icono_bandeja(
    port: int = 8550,
    host: str = "0.0.0.0",
    https: bool = True,
    on_exit: Optional[Callable[[], None]] = None,
    on_restart: Optional[Callable[[], None]] = None,
) -> Optional[TrayIconServidor]:
    """Crea e inicia el servicio de System Tray para el servidor StockAgent."""
    global _INSTANCIA_ACTIVA
    try:
        tray = TrayIconServidor(
            port=port,
            host=host,
            https=https,
            on_exit=on_exit,
            on_restart=on_restart,
        )
        if tray.iniciar():
            _INSTANCIA_ACTIVA = tray
            return tray
    except Exception as exc:
        logger.warning("No se pudo iniciar el servicio de icono de bandeja: %s", exc)
    return None


def registrar_actividad_cliente(ip: str) -> None:
    """Registra actividad HTTP de un dispositivo remoto."""
    tray = _INSTANCIA_ACTIVA
    if tray is not None:
        tray.registrar_actividad_cliente(ip)


def cliente_ws_abierto(ip: str) -> None:
    """Registra una sesión WebSocket abierta."""
    tray = _INSTANCIA_ACTIVA
    if tray is not None:
        tray.cliente_ws_abierto(ip)


def cliente_ws_cerrado(ip: str) -> None:
    """Registra el cierre de una sesión WebSocket."""
    tray = _INSTANCIA_ACTIVA
    if tray is not None:
        tray.cliente_ws_cerrado(ip)


def notificar_conexion_cliente(ip: str, agente: str = "") -> bool:
    """Notifica en la bandeja la conexión de un cliente."""
    tray = _INSTANCIA_ACTIVA
    if tray is None:
        return False
    try:
        return tray.notificar_conexion_cliente(ip, agente)
    except Exception as exc:
        logger.debug("No se pudo notificar conexión de cliente: %s", exc)
        return False


__all__ = [
    "_INSTANCIA_ACTIVA",
    "iniciar_icono_bandeja",
    "registrar_actividad_cliente",
    "cliente_ws_abierto",
    "cliente_ws_cerrado",
    "notificar_conexion_cliente",
]
