"""Servidor web ASGI, FastAPI y runtime de red para StockAgent."""

import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
import socket
import sys
from typing import Callable
import webbrowser

import flet as ft

from .ssl_manager import asegurar_certificado_ssl
from .logger_config import configurar_logging
from .paths import application_root
from .alertas_programadas import iniciar_planificador

logger = logging.getLogger("stockagent.server")

PUERTO_WEB_DEFAULT = 8550


def obtener_directorio_assets() -> str:
    """Devuelve la ruta absoluta al directorio de assets estáticos (favicons, logos)."""
    if getattr(sys, "_MEIPASS", None):
        candidato = Path(sys._MEIPASS) / "assets"
        if candidato.is_dir():
            return str(candidato.resolve())
    candidato = application_root() / "assets"
    if candidato.is_dir():
        return str(candidato.resolve())
    candidato = Path(__file__).resolve().parent.parent / "assets"
    if candidato.is_dir():
        return str(candidato.resolve())
    return str((Path(__file__).resolve().parent / "img").resolve())


def obtener_ip_local() -> str:
    """Devuelve la dirección IP de la máquina en la red local (LAN)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except Exception:
        try:
            return str(socket.gethostbyname(socket.gethostname()))
        except Exception:
            return "127.0.0.1"


def obtener_ip_tailscale() -> str | None:
    """Busca una dirección IPv4 de Tailscale asignada a la máquina (rango 100.64.0.0/10)."""
    try:
        host = socket.gethostname()
        for item in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = item[4][0]
            if ip.startswith("100."):
                partes = [int(p) for p in ip.split(".") if p.isdigit()]
                if len(partes) == 4 and 64 <= partes[1] <= 127:
                    return ip
    except Exception:
        pass
    return None


def _puerto_local_activo(port: int) -> bool:
    """Verifica si el puerto local TCP ya se encuentra en escucha."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


class _RegistroConexionesMiddleware:
    """Middleware ASGI que avisa por consola cuando un dispositivo llega al servidor.

    Permite saber si el celular (o cualquier equipo) alcanzó el servidor aunque
    todavía no haya abierto la sesión de Flet. Muestra IP, tipo de petición y
    dispositivo; por IP no repite el aviso más de una vez cada 30 segundos.
    """

    _INTERVALO_AVISO_S = 30.0
    _ultimo_aviso: dict[str, float] = {}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        cliente_ws = None
        if scope.get("type") in ("http", "websocket"):
            try:
                import time

                cliente = (scope.get("client") or ("desconocido", 0))[0]
                try:
                    from .tray_icon import cliente_ws_abierto, registrar_actividad_cliente

                    registrar_actividad_cliente(cliente)
                    if scope["type"] == "websocket":
                        cliente_ws_abierto(cliente)
                        cliente_ws = cliente
                except Exception:
                    pass
                ahora = time.monotonic()
                es_ws = scope["type"] == "websocket"
                ultimo = self._ultimo_aviso.get(cliente, 0.0)
                if es_ws or ahora - ultimo >= self._INTERVALO_AVISO_S:
                    self._ultimo_aviso[cliente] = ahora
                    agente = ""
                    for nombre, valor in scope.get("headers") or []:
                        if nombre == b"user-agent":
                            agente = valor.decode("latin-1")[:70]
                            break
                    tipo = "WebSocket" if es_ws else scope.get("method", "HTTP")
                    ruta = scope.get("path", "/")
                    print(
                        f"[{datetime.now():%H:%M:%S}] [RED] {tipo} {ruta} desde {cliente}"
                        f"{' | ' + agente if agente else ''}",
                        flush=True,
                    )
                    try:
                        from .tray_icon import notificar_conexion_cliente

                        notificar_conexion_cliente(cliente, agente)
                    except Exception:
                        pass
            except Exception:
                pass
        es_http = scope.get("type") == "http"
        ruta_req = scope.get("path", "") if es_http else ""

        async def _send_filtrado(message):
            if es_http and message.get("type") == "http.response.start":
                if ruta_req in ("/", "/index.html", "/assets/FontManifest.json"):
                    raw_headers = list(message.get("headers") or [])
                    filtrados = [
                        (k, v)
                        for k, v in raw_headers
                        if k.lower() != b"cache-control"
                    ]
                    filtrados.append(
                        (b"cache-control", b"no-cache, no-store, must-revalidate")
                    )
                    message = {**message, "headers": filtrados}
            await send(message)

        try:
            await self.app(scope, receive, _send_filtrado if es_http else send)
        finally:
            if cliente_ws is not None:
                try:
                    from .tray_icon import cliente_ws_cerrado

                    cliente_ws_cerrado(cliente_ws)
                except Exception:
                    pass


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
    if ocultar_consola and sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

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

    if modo_web:
        forzar_reinicio = any(f in sys.argv for f in ("--force", "--forzar", "--reiniciar", "--restart"))
        if not hasattr(ft.run, "_mock_name") and _puerto_local_activo(port):
            if forzar_reinicio:
                try:
                    import subprocess
                    for line in subprocess.check_output("netstat -ano", shell=True, text=True).splitlines():
                        if f":{port}" in line and "LISTENING" in line:
                            pid_str = line.strip().split()[-1]
                            subprocess.run(f"taskkill /F /PID {pid_str}", shell=True, capture_output=True)
                    import time
                    time.sleep(0.6)
                except Exception:
                    pass

            if not forzar_reinicio or _puerto_local_activo(port):
                url_activa = f"{esquema}://localhost:{port}"
                if abrir_navegador:
                    print(f"[INFO] Servidor activo detectado en {url_activa}. Abriendo navegador...")
                    webbrowser.open(url_activa)
                else:
                    print(f"[INFO] Servidor activo detectado en {url_activa}.")
                return

        # Limpiar variables inyectadas por hooks de PyInstaller
        os.environ.pop("FLET_SERVER_IP", None)
        os.environ.pop("FLET_WEB_NO_CDN", None)
        os.environ.pop("FLET_WEB_RENDERER", None)

        flet_logger = logging.getLogger("flet")
        if flet_logger.getEffectiveLevel() in (logging.CRITICAL, logging.NOTSET):
            flet_logger.setLevel(logging.WARNING)

        # En Windows, abrir en navegador local usando localhost con HTTPS
        try:
            import flet.app as _flet_app
            import flet.utils as _flet_utils

            _orig_open = getattr(_flet_app, "_orig_open_in_browser", getattr(_flet_app, "open_in_browser", None))
            if _orig_open:
                setattr(_flet_app, "_orig_open_in_browser", _orig_open)

            _browser_opened = False

            def _open_local_browser(url: str) -> None:
                nonlocal _browser_opened
                if not abrir_navegador:
                    return
                if _browser_opened:
                    return
                _browser_opened = True
                url_local = url.replace("://0.0.0.0:", "://localhost:").replace("://127.0.0.1:", "://localhost:")
                if https and url_local.startswith("http://"):
                    url_local = "https://" + url_local[len("http://"):]
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
        except Exception:
            pass

        try:
            import flet_web
            import flet_web.fastapi
            import flet_web.fastapi.serve_fastapi_web_app as _sfa
            import uvicorn
            from starlette.responses import FileResponse, JSONResponse

            if https and cert_path_final and key_path_final:
                _orig_uv_init = getattr(uvicorn.Config, "_orig_init", uvicorn.Config.__init__)
                setattr(uvicorn.Config, "_orig_init", _orig_uv_init)

                def _https_uv_init(self_cfg, *u_args, **u_kwargs):
                    u_kwargs.setdefault("ssl_certfile", str(cert_path_final))
                    u_kwargs.setdefault("ssl_keyfile", str(key_path_final))
                    _orig_uv_init(self_cfg, *u_args, **u_kwargs)

                uvicorn.Config.__init__ = _https_uv_init

            _orig_serve = getattr(
                _sfa, "_orig_serve_fastapi_web_app", _sfa.serve_fastapi_web_app
            )
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
                            p_url = "https://" + p_url[len("http://"):]
                        p_url = p_url.replace("://0.0.0.0:", "://localhost:").replace("://127.0.0.1:", "://localhost:")
                        orig_on_startup(p_url)
                    kwargs["on_startup"] = _wrapped_on_startup

                assets_path = Path(obtener_directorio_assets())
                ico_path = assets_path / "favicon.ico"
                png_path = assets_path / "favicon.png"
                sw_path = assets_path / "sw.js"
                manifest_path = assets_path / "manifest.json"
                offline_path = assets_path / "offline.html"
                scanner_path = assets_path / "scanner.html"
                scanner_js = assets_path / "js" / "scanner.js"
                scanner_css = assets_path / "css" / "scanner.css"

                if not hasattr(flet_web.fastapi.FastAPI, "_orig_init"):
                    orig_init = flet_web.fastapi.FastAPI.__init__
                    setattr(flet_web.fastapi.FastAPI, "_orig_init", orig_init)

                    def custom_fastapi_init(self, *a, **kw):
                        orig_init(self, *a, **kw)
                        try:
                            self.add_middleware(_RegistroConexionesMiddleware)
                        except Exception as exc_mw:
                            logger.warning("No se pudo activar el aviso de conexiones: %s", exc_mw)

                        try:
                            from starlette.middleware.cors import CORSMiddleware
                            self.add_middleware(
                                CORSMiddleware,
                                allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|100\.\d+\.\d+\.\d+)(:\d+)?$",
                                allow_credentials=True,
                                allow_methods=["*"],
                                allow_headers=["*"],
                            )

                            @self.middleware("http")
                            async def _security_headers_middleware(request, call_next):
                                response = await call_next(request)
                                response.headers["X-Content-Type-Options"] = "nosniff"
                                response.headers["X-Frame-Options"] = "SAMEORIGIN"
                                return response
                        except Exception as exc_cors:
                            logger.warning("No se pudo activar CORS en la API: %s", exc_cors)

                        try:
                            from .api import api_v1_router
                            self.include_router(api_v1_router)
                            logger.info("Endpoints REST API (/api/v1) montados exitosamente.")
                        except Exception as exc_api:
                            logger.error("Error al montar router de API REST: %s", exc_api, exc_info=True)
                        if ico_path.exists():
                            @self.get("/favicon.ico")
                            async def _serve_favicon_ico():
                                return FileResponse(
                                    str(ico_path),
                                    media_type="image/x-icon",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )
                        if png_path.exists():
                            @self.get("/favicon.png")
                            async def _serve_favicon_png():
                                return FileResponse(
                                    str(png_path),
                                    media_type="image/png",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )
                        if sw_path.exists():
                            @self.get("/sw.js")
                            @self.get("/service-worker.js")
                            @self.get("/flutter_service_worker.js")
                            async def _serve_sw():
                                return FileResponse(
                                    str(sw_path),
                                    media_type="application/javascript",
                                    headers={
                                        "Service-Worker-Allowed": "/",
                                        "Cache-Control": "no-cache, no-store, must-revalidate",
                                    },
                                )
                        if manifest_path.exists():
                            @self.get("/manifest.json")
                            async def _serve_manifest():
                                return FileResponse(
                                    str(manifest_path),
                                    media_type="application/manifest+json",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )
                        if offline_path.exists():
                            @self.get("/offline.html")
                            async def _serve_offline():
                                return FileResponse(
                                    str(offline_path),
                                    media_type="text/html",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )
                        if scanner_path.exists():
                            @self.get("/scanner.html")
                            async def _serve_scanner():
                                return FileResponse(
                                    str(scanner_path),
                                    media_type="text/html",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )
                        if scanner_js.exists():
                            @self.get("/js/scanner.js")
                            async def _serve_scanner_js():
                                return FileResponse(
                                    str(scanner_js),
                                    media_type="application/javascript",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )
                        if scanner_css.exists():
                            @self.get("/css/scanner.css")
                            async def _serve_scanner_css():
                                return FileResponse(
                                    str(scanner_css),
                                    media_type="text/css",
                                    headers={"Cache-Control": "no-cache, must-revalidate"},
                                )

                        # Repositorio local de actualizaciones OTA para la app móvil
                        dist_movil_path = Path(application_root()) / "stockagent_mobile" / "dist_movil"
                        if not dist_movil_path.exists():
                            dist_movil_path = Path(application_root()) / "dist_movil"
                        apk_file_path = dist_movil_path / "StockAgent.apk"
                        version_json_path = dist_movil_path / "version.json"

                        @self.get("/actualizaciones/version.json")
                        @self.get("/api/version")
                        async def _serve_version_json():
                            info = {
                                "version_code": 1,
                                "version_name": "1.0.0",
                                "apk_url": "/actualizaciones/StockAgent.apk",
                                "release_notes": "Versión oficial de StockAgent para dispositivos móviles.",
                                "file_size": 0,
                                "updated_at": "",
                            }
                            if version_json_path.exists():
                                try:
                                    import json
                                    loaded = json.loads(version_json_path.read_text(encoding="utf-8"))
                                    if isinstance(loaded, dict):
                                        info.update(loaded)
                                except Exception as err_v:
                                    logger.warning("Error al leer version.json: %s", err_v)

                            if apk_file_path.exists():
                                st = apk_file_path.stat()
                                info["file_size"] = st.st_size
                                if not info.get("updated_at"):
                                    info["updated_at"] = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m/%Y %H:%M")

                            return JSONResponse(
                                content=info,
                                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
                            )

                        @self.get("/actualizaciones/StockAgent.apk")
                        @self.get("/dist_movil/StockAgent.apk")
                        async def _serve_apk_download():
                            if not apk_file_path.exists():
                                return JSONResponse(
                                    status_code=404,
                                    content={"error": "El instalador StockAgent.apk aún no ha sido compilado en la PC."},
                                )
                            return FileResponse(
                                str(apk_file_path),
                                media_type="application/vnd.android.package-archive",
                                filename="StockAgent.apk",
                                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
                            )

                        # Servir documentos y manuales PDF oficiales con visualización inline en navegador
                        doc_dir_path = Path(application_root()) / "Documentacion"

                        @self.get("/documentacion/{nombre_archivo}")
                        @self.get("/docs/{nombre_archivo}")
                        async def _serve_doc_pdf(nombre_archivo: str):
                            nombre_seguro = Path(nombre_archivo).name
                            archivo_pdf = doc_dir_path / nombre_seguro
                            if not archivo_pdf.exists() or not archivo_pdf.is_file():
                                return JSONResponse(
                                    status_code=404,
                                    content={"error": f"El documento '{nombre_seguro}' no se encuentra disponible."},
                                )
                            return FileResponse(
                                str(archivo_pdf),
                                media_type="application/pdf",
                                filename=nombre_seguro,
                                headers={
                                    "Content-Disposition": f"inline; filename={nombre_seguro}",
                                    "Cache-Control": "no-cache, no-store, must-revalidate",
                                },
                            )

                        # Servir informes generados para descarga directa en navegador
                        @self.get("/descargas/informes/{nombre_archivo}")
                        @self.get("/descargas/informe/{nombre_archivo}")
                        @self.get("/api/v1/informes/descargar/{nombre_archivo}")
                        async def _serve_informe_descarga(nombre_archivo: str):
                            nombre_seguro = Path(nombre_archivo).name
                            base_app = Path(application_root())
                            rutas_candidatas = [
                                base_app / "Descuentos" / "descuentos" / nombre_seguro,
                                base_app / "Descuentos" / nombre_seguro,
                                base_app / "Descuentos" / "descontados" / nombre_seguro,
                                base_app / "Descuentos" / "descontados" / "MercadoLibre" / nombre_seguro,
                                base_app / "Descuentos" / "descontados" / "Mayoristas" / nombre_seguro,
                                base_app / "Descuentos" / "descontados" / "Canjes" / nombre_seguro,
                                base_app / "Descuentos" / "descontados" / "Fabrica" / nombre_seguro,
                                base_app / "Descuentos" / "descontados" / "MercadoFull" / nombre_seguro,
                                base_app / "Descuentos" / "descontados" / "StockFisico" / nombre_seguro,
                                base_app / "Descuentos" / "Rotulos" / nombre_seguro,
                                base_app / "Fabrica" / "Pedidos_Sugeridos" / nombre_seguro,
                                base_app / "StockFisico" / "Comparativas" / nombre_seguro,
                            ]
                            archivo_encontrado: Path | None = None
                            for cand in rutas_candidatas:
                                if cand.exists() and cand.is_file():
                                    archivo_encontrado = cand
                                    break
                            if not archivo_encontrado:
                                base_desc = base_app / "Descuentos"
                                if base_desc.exists():
                                    for arch in base_desc.rglob(nombre_seguro):
                                        if arch.is_file():
                                            archivo_encontrado = arch
                                            break
                            if not archivo_encontrado or not archivo_encontrado.is_file():
                                return JSONResponse(
                                    status_code=404,
                                    content={"error": f"El informe '{nombre_seguro}' no se encuentra disponible."},
                                )
                            media = "application/octet-stream"
                            sufijo = archivo_encontrado.suffix.lower()
                            if sufijo == ".pdf":
                                media = "application/pdf"
                            elif sufijo in (".xlsx", ".xlsm"):
                                media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            elif sufijo == ".xls":
                                media = "application/vnd.ms-excel"
                            elif sufijo == ".csv":
                                media = "text/csv"

                            disposition = "inline" if sufijo == ".pdf" else "attachment"
                            return FileResponse(
                                str(archivo_encontrado),
                                media_type=media,
                                filename=nombre_seguro,
                                headers={
                                    "Content-Disposition": f'{disposition}; filename="{nombre_seguro}"',
                                    "Cache-Control": "no-cache, no-store, must-revalidate",
                                },
                            )

                    flet_web.fastapi.FastAPI.__init__ = custom_fastapi_init

                handle = await _orig_serve(*args, **kwargs)
                for _ in range(100):
                    if getattr(handle.server, "started", False) or handle.serve_task.done():
                        break
                    await asyncio.sleep(0.05)

                if abrir_navegador and not _browser_opened:
                    _open_local_browser(f"{esquema}://localhost:{port}")
                return handle

            _sfa.serve_fastapi_web_app = _serve_local_url

            import flet_web.fastapi.flet_app as _ffa

            if hasattr(_ffa, "FletApp"):
                if not hasattr(_ffa.FletApp, "_orig_send_loop"):
                    _orig_send_loop = getattr(_ffa.FletApp, "_FletApp__send_loop", None)
                    if _orig_send_loop:
                        setattr(_ffa.FletApp, "_orig_send_loop", _orig_send_loop)

                        async def _clean_send_loop(self):
                            try:
                                await _orig_send_loop(self)
                            except Exception as e:
                                c_name = e.__class__.__name__
                                if any(k in c_name for k in ("Disconnect", "InvalidState", "ConnectionClosed", "ClientDisconnected")):
                                    pass
                                else:
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
                            c_name = e.__class__.__name__
                            if any(k in c_name for k in ("Disconnect", "InvalidState", "ConnectionClosed", "ClientDisconnected")):
                                pass
                            else:
                                raise
                        finally:
                            print(f"[{datetime.now():%H:%M:%S}] [CONEXION] Cliente desconectado: {_cliente}", flush=True)
                            logger.info("Cliente desconectado: %s", _cliente)

                    _ffa.FletApp.handle = _clean_handle
        except Exception:
            pass

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
        assets_dir = obtener_directorio_assets()
        os.environ["FLET_ASSETS_DIR"] = assets_dir

        tray_service = None
        if con_tray:
            try:
                from .tray_icon import iniciar_icono_bandeja

                tray_service = iniciar_icono_bandeja(
                    port=port,
                    host=host,
                    https=https,
                )
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
    else:
        assets_dir = obtener_directorio_assets()
        ft.run(
            entrypoint_main,
            view=ft.AppView.FLET_APP,
            name="Control de Inventario Depósito Pasteur",
            assets_dir=assets_dir,
            no_cdn=False,
            web_renderer=ft.WebRenderer.AUTO,
        )
