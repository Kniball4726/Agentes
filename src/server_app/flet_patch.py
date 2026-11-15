"""Orquestación de arranque HTTPS/FastAPI, integración Flet Web y bandeja del sistema."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Callable
import webbrowser

import flet as ft

from ..alertas_programadas import iniciar_planificador
from ..logger_config import configurar_logging
from ..ssl_manager import asegurar_certificado_ssl
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


def _parchear_navegador_local(abrir_navegador: bool, https: bool) -> Callable[[str], None]:
    _browser_opened = False

    def _noop_open(_url: str) -> None:
        return None

    try:
        import flet.app as _flet_app
        import flet.utils as _flet_utils

        _orig_open = getattr(
            _flet_app, "_orig_open_in_browser", getattr(_flet_app, "open_in_browser", None)
        )
        if _orig_open:
            setattr(_flet_app, "_orig_open_in_browser", _orig_open)

        def _open_local_browser(url: str) -> None:
            nonlocal _browser_opened
            if not abrir_navegador or _browser_opened:
                return
            _browser_opened = True
            url_local = url.replace("://0.0.0.0:", "://localhost:").replace(
                "://127.0.0.1:", "://localhost:"
            )
            if https and url_local.startswith("http://"):
                url_local = "https://" + url_local[len("http://") :]
            if _orig_open:
                _orig_open(url_local)
            else:
                webbrowser.open(url_local)

        _flet_app.open_in_browser = _open_local_browser
        _flet_utils.open_in_browser = _open_local_browser
        if hasattr(ft, "open_in_browser"):
            ft.open_in_browser = _open_local_browser
        if hasattr(ft.run_async, "__globals__"):
            ft.run_async.__globals__["open_in_browser"] = _open_local_browser
        return _open_local_browser
    except Exception:
        return _noop_open


def _parchear_websocket_logging() -> None:
    import flet_web.fastapi.flet_app as _ffa

    if not hasattr(_ffa, "FletApp"):
        return

    if not hasattr(_ffa.FletApp, "_orig_send_loop"):
        _orig_send_loop = getattr(_ffa.FletApp, "_FletApp__send_loop", None)
        if _orig_send_loop:
            setattr(_ffa.FletApp, "_orig_send_loop", _orig_send_loop)

            async def _clean_send_loop(self):
                try:
                    await _orig_send_loop(self)
                except Exception as e:
                    if not any(
                        k in e.__class__.__name__
                        for k in ("Disconnect", "InvalidState", "ConnectionClosed", "ClientDisconnected")
                    ):
                        raise

            setattr(_ffa.FletApp, "_FletApp__send_loop", _clean_send_loop)

    if not hasattr(_ffa.FletApp, "_orig_handle"):
        _orig_handle = _ffa.FletApp.handle
        setattr(_ffa.FletApp, "_orig_handle", _orig_handle)

        async def _clean_handle(self, websocket):
            _cliente = getattr(getattr(websocket, "client", None), "host", None) or "desconocido"
            print(f"[{datetime.now():%H:%M:%S}] [CONEXION] Cliente conectado: {_cliente}", flush=True)
            logger.info("Cliente conectado: %s", _cliente)
            try:
                await _orig_handle(self, websocket)
            except Exception as e:
                if not any(
                    k in e.__class__.__name__
                    for k in ("Disconnect", "InvalidState", "ConnectionClosed", "ClientDisconnected")
                ):
                    raise
            finally:
                print(
                    f"[{datetime.now():%H:%M:%S}] [CONEXION] Cliente desconectado: {_cliente}",
                    flush=True,
                )
                logger.info("Cliente desconectado: %s", _cliente)

        _ffa.FletApp.handle = _clean_handle


def _configurar_adaptadores_web(
    https: bool,
    port: int,
    esquema: str,
    abrir_navegador: bool,
    cert_path_final: Path | None,
    key_path_final: Path | None,
    open_browser_cb: Callable[[str], None],
) -> None:
    try:
        import flet_web.fastapi
        import flet_web.fastapi.serve_fastapi_web_app as _sfa
        import uvicorn

        if https and cert_path_final and key_path_final:
            _orig_uv_init = getattr(uvicorn.Config, "_orig_init", uvicorn.Config.__init__)
            setattr(uvicorn.Config, "_orig_init", _orig_uv_init)

            def _https_uv_init(self_cfg, *u_args, **u_kwargs):
                u_kwargs.setdefault("ssl_certfile", str(cert_path_final))
                u_kwargs.setdefault("ssl_keyfile", str(key_path_final))
                _orig_uv_init(self_cfg, *u_args, **u_kwargs)

            uvicorn.Config.__init__ = _https_uv_init

        _orig_serve = getattr(_sfa, "_orig_serve_fastapi_web_app", _sfa.serve_fastapi_web_app)
        setattr(_sfa, "_orig_serve_fastapi_web_app", _orig_serve)

        async def _serve_local_url(*args, **kwargs):
            if kwargs.get("url_host") in ("0.0.0.0", "*", "", None, "127.0.0.1"):
                kwargs["url_host"] = "localhost"
            elif len(args) >= 4 and args[3] in ("0.0.0.0", "*", "", None, "127.0.0.1"):
                args = (*args[:3], "localhost", *args[4:])

            orig_on_startup = kwargs.get("on_startup")
            if orig_on_startup:
                def _wrapped_on_startup(p_url: str):
                    if https and p_url.startswith("http://"):
                        p_url = "https://" + p_url[len("http://") :]
                    p_url = p_url.replace("://0.0.0.0:", "://localhost:").replace(
                        "://127.0.0.1:", "://localhost:"
                    )
                    orig_on_startup(p_url)

                kwargs["on_startup"] = _wrapped_on_startup

            assets_path = Path(obtener_directorio_assets())
            if not hasattr(flet_web.fastapi.FastAPI, "_orig_init"):
                orig_init = flet_web.fastapi.FastAPI.__init__
                setattr(flet_web.fastapi.FastAPI, "_orig_init", orig_init)

                def custom_fastapi_init(self, *a, **kw):
                    habilitar_docs_api = os.environ.get(
                        "STOCKAGENT_ENABLE_API_DOCS", "0"
                    ).strip().lower() in ("1", "true", "si", "yes")
                    if not habilitar_docs_api:
                        kw.setdefault("docs_url", None)
                        kw.setdefault("redoc_url", None)
                        kw.setdefault("openapi_url", None)
                    orig_init(self, *a, **kw)
                    configurar_middlewares_http(self)
                    try:
                        from ..api import api_v1_router

                        self.include_router(api_v1_router)
                        logger.info("Endpoints REST API (/api/v1) montados exitosamente.")
                    except Exception as exc_api:
                        logger.error("Error al montar router de API REST: %s", exc_api, exc_info=True)
                    registrar_rutas_pwa(self, assets_path)
                    registrar_rutas_ota(self)
                    registrar_rutas_documentos_e_informes(self)

                flet_web.fastapi.FastAPI.__init__ = custom_fastapi_init

            handle = await _orig_serve(*args, **kwargs)
            for _ in range(100):
                if getattr(handle.server, "started", False) or handle.serve_task.done():
                    break
                await asyncio.sleep(0.05)

            if abrir_navegador:
                open_browser_cb(f"{esquema}://localhost:{port}")
            return handle

        _sfa.serve_fastapi_web_app = _serve_local_url
        _parchear_websocket_logging()
    except Exception:
        pass


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


def iniciar_servidor_web(
    entrypoint_main: Callable[[ft.Page], None],
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
    """Inicia el servidor web ASGI / FastAPI o la aplicación en modo ventana."""
    if ocultar_consola:
        ocultar_consola_windows()
    asegurar_flujos_estandar()
    configurar_logging()
    try:
        iniciar_planificador()
    except Exception:
        pass

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
            logger.info("Certificado SSL preparado para HTTPS: %s", cert_path_final)
        except Exception as exc_ssl:
            logger.warning("No se pudo preparar certificado SSL, continuando en HTTP: %s", exc_ssl)
            https = False
            esquema = "http"
            os.environ["STOCKAGENT_SCHEME"] = "http"

    if not modo_web:
        assets_dir = obtener_directorio_assets()
        ft.run(
            entrypoint_main,
            view=ft.AppView.FLET_APP,
            name="Control de Inventario Depósito Pasteur",
            assets_dir=assets_dir,
            no_cdn=False,
            web_renderer=ft.WebRenderer.AUTO,
        )
        return

    if resolver_instancia_unica(port, esquema, abrir_navegador, ft):
        return

    for var_env in ("FLET_SERVER_IP", "FLET_WEB_NO_CDN", "FLET_WEB_RENDERER"):
        os.environ.pop(var_env, None)

    flet_logger = logging.getLogger("flet")
    if flet_logger.getEffectiveLevel() in (logging.CRITICAL, logging.NOTSET):
        flet_logger.setLevel(logging.WARNING)

    open_cb = _parchear_navegador_local(abrir_navegador, https)
    _configurar_adaptadores_web(
        https, port, esquema, abrir_navegador, cert_path_final, key_path_final, open_cb
    )
    _imprimir_banner_red(esquema, port, https, cert_path_final)

    assets_dir = obtener_directorio_assets()
    os.environ["FLET_ASSETS_DIR"] = assets_dir

    tray_service = None
    if con_tray:
        try:
            from ..tray import iniciar_icono_bandeja

            tray_service = iniciar_icono_bandeja(port=port, host=host, https=https)
        except Exception as exc_tray:
            logger.warning("No se pudo iniciar icono en bandeja del sistema: %s", exc_tray)

    try:
        ft.run(
            entrypoint_main,
            view=ft.AppView.WEB_BROWSER,
            host=host,
            port=port,
            name="",
            assets_dir=assets_dir,
            no_cdn=False,
            web_renderer=ft.WebRenderer.AUTO,
        )
    finally:
        if tray_service:
            tray_service.detener()
