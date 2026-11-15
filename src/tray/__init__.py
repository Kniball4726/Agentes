"""Subpaquete modular para el icono en bandeja del sistema (System Tray)."""

from .net_and_images import (
    COLORES_BADGE,
    ESTADO_CLIENTE,
    ESTADO_DETENIDO,
    ESTADO_ERROR,
    ESTADO_INICIANDO,
    ESTADO_ONLINE,
    TEXTOS_ESTADO,
    _buscar_icono_base,
    _copiar_al_portapapeles,
    _obtener_ip_local,
    _obtener_ip_tailscale,
    describir_dispositivo,
    generar_imagen_estado,
)
from .service import (
    _INSTANCIA_ACTIVA,
    cliente_ws_abierto,
    cliente_ws_cerrado,
    iniciar_icono_bandeja,
    notificar_conexion_cliente,
    registrar_actividad_cliente,
)
from .tray_controller import TrayIconServidor

__all__ = [
    "ESTADO_INICIANDO",
    "ESTADO_ONLINE",
    "ESTADO_CLIENTE",
    "ESTADO_ERROR",
    "ESTADO_DETENIDO",
    "TEXTOS_ESTADO",
    "COLORES_BADGE",
    "_obtener_ip_local",
    "_obtener_ip_tailscale",
    "_copiar_al_portapapeles",
    "_buscar_icono_base",
    "describir_dispositivo",
    "generar_imagen_estado",
    "TrayIconServidor",
    "_INSTANCIA_ACTIVA",
    "iniciar_icono_bandeja",
    "registrar_actividad_cliente",
    "cliente_ws_abierto",
    "cliente_ws_cerrado",
    "notificar_conexion_cliente",
]
