"""Componentes modulares del servidor web ASGI / FastAPI y runtime Flet."""

from .flet_patch import iniciar_servidor_web
from .middleware import _RegistroConexionesMiddleware, configurar_middlewares_http
from .network_utils import (
    PUERTO_WEB_DEFAULT,
    _puerto_local_activo,
    obtener_directorio_assets,
    obtener_ip_local,
    obtener_ip_tailscale,
)
from .protected_docs_routes import registrar_rutas_documentos_e_informes
from .static_routes import registrar_rutas_ota, registrar_rutas_pwa

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
