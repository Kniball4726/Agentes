"""Orquestación explícita de servidor HTTPS/FastAPI/Uvicorn, Flet Web ASGI y bandeja del sistema."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import sys
from typing import Any, Callable
import webbrowser

import flet as ft
import flet_web.fastapi as flet_web_fastapi
import uvicorn

from ..alertas_programadas import iniciar_planificador
from ..api.stores import ApiStoreContext, crear_contexto_api
from ..auto_updater import iniciar_watcher_auto_update
from ..logger_config import configurar_logging
from ..ssl_manager import asegurar_ca_confiable_windows, asegurar_certificado_ssl
from .middleware import configurar_middlewares_http
from .network_utils import (
    PUERTO_WEB_DEFAULT,
    asegurar_flujos_estandar,
    obtener_directorio_assets,
    obtener_ip_local,
    obtener_ip_tailscale,
    ocultar_consola_windows,
    resolver_instancia_unica,
)
from .protected_docs_routes import registrar_rutas_documentos_e_informes
from .static_routes import registrar_rutas_ota, registrar_rutas_pwa

logger = logging.getLogger("stockagent.server")


def _resolver_no_cdn_web(no_cdn: bool | None) -> bool:
    """Resuelve modo offline web (`no_cdn=True` por defecto en LAN para evitar CDNs externos)."""
    if no_cdn is not None:
        return bool(no_cdn)
    raw = os.environ.get("STOCKAGENT_WEB_NO_CDN", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def crear_aplicacion_asgi(
    entrypoint_main: Callable[[ft.Page], Any],
    *,
    assets_dir: str | Path | None = None,
    no_cdn: bool | None = None,
    web_renderer: ft.WebRenderer = ft.WebRenderer.AUTO,
    habilitar_docs_api: bool | None = None,
    store_context: ApiStoreContext | None = None,
) -> flet_web_fastapi.FastAPI:
    """Construye la aplicación ASGI explícita sin monkey-patching sobre FastAPI o Uvicorn.

    Registra middlewares HTTP/CORS/CSP, API REST `/api/v1`, rutas PWA, OTA,
    documentos protegidos y monta la subaplicación web de Flet en `/`.
    Por defecto sirve recursos CanvasKit y fuentes localmente (`no_cdn=True`) para operar
    sin acceso a Internet en la red local del depósito.
    """
    assets_path = Path(assets_dir or obtener_directorio_assets()).resolve()
    os.environ["FLET_ASSETS_DIR"] = str(assets_path)
    no_cdn_activo = _resolver_no_cdn_web(no_cdn)
    ctx_api = store_context or crear_contexto_api(name="asgi")

    if habilitar_docs_api is None:
        habilitar_docs_api = os.environ.get(
            "STOCKAGENT_ENABLE_API_DOCS", "0"
        ).strip().lower() in ("1", "true", "si", "yes")

    fastapi_kwargs: dict[str, Any] = {}
    if not habilitar_docs_api:
        fastapi_kwargs.update({"docs_url": None, "redoc_url": None, "openapi_url": None})

    app = flet_web_fastapi.FastAPI(**fastapi_kwargs)
    app.state.api_store_context = ctx_api
    configurar_middlewares_http(app, no_cdn=no_cdn_activo, store_context=ctx_api)

    try:
        from ..api import api_v1_router

        app.include_router(api_v1_router)
        logger.info("Endpoints REST API (/api/v1) montados exitosamente.")
    except Exception as exc_api:
        logger.error("Error al montar router de API REST: %s", exc_api, exc_info=True)

    registrar_rutas_pwa(app, assets_path)
    registrar_rutas_ota(app)
    registrar_rutas_documentos_e_informes(app)

    sub_app_flet = flet_web_fastapi.app(
        entrypoint_main,
        assets_dir=str(assets_path),
        web_renderer=web_renderer,
        no_cdn=no_cdn_activo,
    )
    app.mount("/", sub_app_flet)
    return app


def _imprimir_banner_red(esquema: str, port: int, https: bool, cert_path_final: Path | None) -> None:
    ip_local = obtener_ip_local()
    ip_tailscale = obtener_ip_tailscale()
    print("=" * 70, flush=True)
    print(f"  STOCK AGENT - SERVIDOR WEB MULTI-EQUIPO ({esquema.upper()})", flush=True)
    print("=" * 70, flush=True)
    print(f"  -> Acceso Local (esta PC):        {esquema}://localhost:{port}", flush=True)
    print(f"  -> Acceso Red LAN (misma red):    {esquema}://{ip_local}:{port}", flush=True)
    if ip_tailscale:
        print(f"  -> Acceso Remoto (Tailscale VPN): {esquema}://{ip_tailscale}:{port}", flush=True)
    else:
        print(f"  -> Acceso Remoto Seguro (VPN):    {esquema}://<IP_TAILSCALE>:{port} (via Tailscale)", flush=True)
    if https and cert_path_final:
        print(f"  -> Certificado SSL activo:        {cert_path_final}", flush=True)
    print("  Mantén esta consola abierta mientras el servidor esté en uso.", flush=True)
    print("=" * 70, flush=True)


async def _servir_uvicorn_con_apertura(
    server: uvicorn.Server,
    *,
    abrir_navegador: bool,
    url_local: str,
) -> None:
    """Inicia Uvicorn de forma asíncrona y abre el navegador cuando el socket queda listo."""
    serve_task = asyncio.create_task(server.serve())
    if abrir_navegador:
        for _ in range(100):
            if getattr(server, "started", False) or serve_task.done():
                break
            await asyncio.sleep(0.05)
        if getattr(server, "started", False) and not serve_task.done():
            webbrowser.open(url_local)
    await serve_task


def iniciar_servidor_web(
    entrypoint_main: Callable[[ft.Page], Any],
    modo_web: bool = True,
    host: str = "0.0.0.0",
    port: int = PUERTO_WEB_DEFAULT,
    https: bool = True,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
    ocultar_consola: bool = False,
    abrir_navegador: bool = True,
    con_tray: bool = True,
    **kwargs,
) -> None:
    """Inicia el servidor web ASGI / FastAPI explícito o la aplicación en modo ventana."""
    if ocultar_consola:
        ocultar_consola_windows()
    asegurar_flujos_estandar()
    configurar_logging()
    try:
        iniciar_planificador()
    except Exception as exc:
        logger.warning("No se pudo iniciar el planificador de alertas programadas: %s", exc)

    esquema = "https" if https else "http"
    os.environ["STOCKAGENT_PORT"] = str(port)
    os.environ["STOCKAGENT_SCHEME"] = esquema

    cert_path_final: Path | None = None
    key_path_final: Path | None = None
    if modo_web and https:
        try:
            cert_path_final, key_path_final = asegurar_certificado_ssl(
                Path(ssl_certfile) if ssl_certfile else None,
                Path(ssl_keyfile) if ssl_keyfile else None,
            )
            asegurar_ca_confiable_windows(cert_path_final.parent / "stockagent_ca.crt")
            logger.info("Certificado SSL preparado para HTTPS: %s", cert_path_final)
        except Exception as exc_ssl:
            logger.warning("No se pudo preparar certificado SSL, continuando en HTTP: %s", exc_ssl)
            https = False
            esquema = "http"
            os.environ["STOCKAGENT_SCHEME"] = "http"

    assets_dir = obtener_directorio_assets()
    web_renderer = kwargs.get("web_renderer", ft.WebRenderer.AUTO)

    if not modo_web:
        no_cdn_desktop = bool(kwargs.get("no_cdn", False))
        ft.run(
            entrypoint_main,
            view=ft.AppView.FLET_APP,
            name="Control de Inventario Depósito Pasteur",
            assets_dir=assets_dir,
            no_cdn=no_cdn_desktop,
            web_renderer=web_renderer,
        )
        return

    if resolver_instancia_unica(port, esquema, abrir_navegador, ft):
        return

    for var_env in ("FLET_SERVER_IP", "FLET_WEB_NO_CDN", "FLET_WEB_RENDERER"):
        os.environ.pop(var_env, None)

    flet_logger = logging.getLogger("flet")
    if flet_logger.getEffectiveLevel() in (logging.CRITICAL, logging.NOTSET):
        flet_logger.setLevel(logging.WARNING)

    no_cdn_web = bool(kwargs["no_cdn"]) if "no_cdn" in kwargs else None
    app = crear_aplicacion_asgi(
        entrypoint_main,
        assets_dir=assets_dir,
        no_cdn=no_cdn_web,
        web_renderer=web_renderer,
        store_context=kwargs.get("store_context"),
    )
    _imprimir_banner_red(esquema, port, https, cert_path_final)

    config_kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "log_level": "warning",
        "ws": "websockets-sansio",
        "timeout_graceful_shutdown": 5,
    }
    if https and cert_path_final and key_path_final:
        config_kwargs["ssl_certfile"] = str(cert_path_final)
        config_kwargs["ssl_keyfile"] = str(key_path_final)

    config = uvicorn.Config(app, **config_kwargs)
    server = uvicorn.Server(config)

    def _solicitar_reinicio_servidor() -> None:
        server.should_exit = True

    tray_service = None
    if con_tray:
        try:
            from ..tray import iniciar_icono_bandeja

            tray_service = iniciar_icono_bandeja(
                port=port,
                host=host,
                https=https,
                on_restart=_solicitar_reinicio_servidor,
            )
        except Exception as exc_tray:
            logger.warning("No se pudo iniciar icono en bandeja del sistema: %s", exc_tray)

    watcher_auto_update = None
    if not hasattr(uvicorn.Server, "_mock_name"):
        try:
            watcher_auto_update = iniciar_watcher_auto_update(
                port=port,
                argv=sys.argv[1:],
                on_restart_requested=_solicitar_reinicio_servidor,
            )
        except Exception as exc_upd:
            logger.warning("No se pudo iniciar vigilante de auto-actualización: %s", exc_upd)

    url_local = f"{esquema}://localhost:{port}"
    try:
        asyncio.run(
            _servir_uvicorn_con_apertura(
                server,
                abrir_navegador=abrir_navegador,
                url_local=url_local,
            )
        )
    finally:
        if watcher_auto_update:
            watcher_auto_update.detener()
        if tray_service:
            tray_service.detener()
