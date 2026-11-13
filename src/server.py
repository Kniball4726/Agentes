"""Fachada pública del servidor web ASGI, FastAPI y runtime de red de StockAgent."""

from __future__ import annotations

from .server_app import (
    PUERTO_WEB_DEFAULT,
    _RegistroConexionesMiddleware,
    _puerto_local_activo,
    configurar_middlewares_http,
    iniciar_servidor_web,
    obtener_directorio_assets,
    obtener_ip_local,
    obtener_ip_tailscale,
    registrar_rutas_documentos_e_informes,
    registrar_rutas_ota,
    registrar_rutas_pwa,
)

__all__ = [
    "PUERTO_WEB_DEFAULT",
    "obtener_directorio_assets",
    "obtener_ip_local",
    "obtener_ip_tailscale",
    "_puerto_local_activo",
    "_RegistroConexionesMiddleware",
    "configurar_middlewares_http",
    "registrar_rutas_pwa",
    "registrar_rutas_ota",
    "registrar_rutas_documentos_e_informes",
    "iniciar_servidor_web",
]
