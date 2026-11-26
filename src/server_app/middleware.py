"""Middlewares ASGI/HTTP de trazabilidad estructurada, CORS LAN y cabeceras de seguridad."""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Optional
import uuid

from ..api.stores import establecer_contexto_api, restaurar_contexto_api

if TYPE_CHECKING:
    from ..api.stores import ApiStoreContext

logger = logging.getLogger("stockagent.server")

_PATRON_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

_CORS_ORIGIN_REGEX_LAN_TAILSCALE = (
    r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3})(:\d+)?$"
)
_CSP_API_ESTRICTA = "default-src 'self'; frame-ancestors 'self'; object-src 'self'; base-uri 'self'"
_CSP_APP_WEB_LOCAL = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' blob:; "
    "worker-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "frame-ancestors 'self'; "
    "base-uri 'self'"
)
_CSP_APP_WEB_CDN = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' blob: https://www.gstatic.com https://cdn.jsdelivr.net; "
    "worker-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "connect-src 'self' ws: wss: https://www.gstatic.com https://fonts.gstatic.com https://cdn.jsdelivr.net; "
    "frame-ancestors 'self'; "
    "base-uri 'self'"
)
# Por defecto la política web es estrictamente local (sin CDNs externos en LAN).
_CSP_APP_WEB = _CSP_APP_WEB_LOCAL


def construir_csp_app_web(no_cdn: bool = True) -> str:
    """Construye la cabecera CSP web en modo estricto local (`no_cdn=True`) o con CDN."""
    return _CSP_APP_WEB_LOCAL if no_cdn else _CSP_APP_WEB_CDN


def _extraer_header(scope, nombre_objetivo: bytes) -> str:
    for nombre, valor in scope.get("headers") or []:
        if nombre.lower() == nombre_objetivo:
            return valor.decode("latin-1")
    return ""


def _resolver_request_id(scope) -> str:
    raw = _extraer_header(scope, b"x-request-id").strip()
    if raw and _PATRON_REQUEST_ID.match(raw):
        return raw
    return uuid.uuid4().hex[:12]


class _RegistroConexionesMiddleware:
    """Middleware ASGI de trazabilidad estructurada (request_id, latencia y status HTTP)."""

    _INTERVALO_AVISO_S = 30.0
    _ultimo_aviso: dict[str, float] = {}

    def __init__(self, app):
        self.app = app

    def _registrar_actividad_y_tray(self, scope) -> tuple[str, str, str | None]:
        cliente = "desconocido"
        agente = ""
        cliente_ws: str | None = None
        try:
            cliente = str((scope.get("client") or ("desconocido", 0))[0])
            agente = _extraer_header(scope, b"user-agent")[:70]
            try:
                from ..tray import cliente_ws_abierto, notificar_conexion_cliente, registrar_actividad_cliente

                registrar_actividad_cliente(cliente)
                es_ws = scope.get("type") == "websocket"
                if es_ws:
                    cliente_ws_abierto(cliente)
                    cliente_ws = cliente
                ahora = time.monotonic()
                ultimo = self._ultimo_aviso.get(cliente, 0.0)
                if es_ws or ahora - ultimo >= self._INTERVALO_AVISO_S:
                    self._ultimo_aviso[cliente] = ahora
                    notificar_conexion_cliente(cliente, agente)
            except Exception:
                pass
        except Exception:
            pass
        return cliente, agente, cliente_ws

    async def __call__(self, scope, receive, send):
        tipo_scope = scope.get("type")
        if tipo_scope not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        inicio = time.perf_counter()
        request_id = _resolver_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        cliente, agente, cliente_ws = self._registrar_actividad_y_tray(scope)

        es_http = tipo_scope == "http"
        ruta_req = scope.get("path", "/")
        metodo = scope.get("method", "WS" if not es_http else "GET")
        status_code: int | str = "ws" if not es_http else 500

        async def _send_observado(message):
            nonlocal status_code
            if es_http and message.get("type") == "http.response.start":
                status_code = int(message.get("status", 200))
                raw_headers = [
                    (k, v)
                    for k, v in (message.get("headers") or [])
                    if k.lower() != b"x-request-id"
                ]
                raw_headers.append((b"x-request-id", request_id.encode("ascii")))
                if ruta_req in ("/", "/index.html", "/assets/FontManifest.json"):
                    raw_headers = [
                        (k, v)
                        for k, v in raw_headers
                        if k.lower() != b"cache-control"
                    ]
                    raw_headers.append(
                        (b"cache-control", b"no-cache, no-store, must-revalidate")
                    )
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, _send_observado if es_http else send)
        finally:
            duracion_ms = round((time.perf_counter() - inicio) * 1000.0, 2)
            if es_http:
                log_fn = logger.debug if ruta_req == "/api/v1/sistema/ping" else logger.info
                log_fn(
                    "HTTP request_id=%s method=%s path=%s status=%s duration_ms=%.2f client=%s ua=%s",
                    request_id,
                    metodo,
                    ruta_req,
                    status_code,
                    duracion_ms,
                    cliente,
                    agente or "-",
                )
            else:
                logger.info(
                    "WebSocket request_id=%s path=%s duration_ms=%.2f client=%s ua=%s",
                    request_id,
                    ruta_req,
                    duracion_ms,
                    cliente,
                    agente or "-",
                )
            if cliente_ws is not None:
                try:
                    from ..tray import cliente_ws_cerrado

                    cliente_ws_cerrado(cliente_ws)
                except Exception:
                    pass


class _ApiContextMiddleware:
    """Aísla cada petición dentro del `ApiStoreContext` de la instancia de servidor."""

    def __init__(self, app, store_context: ApiStoreContext):
        self.app = app
        self.store_context = store_context

    async def __call__(self, scope, receive, send):
        token = establecer_contexto_api(self.store_context)
        try:
            await self.app(scope, receive, send)
        finally:
            restaurar_contexto_api(token)


def configurar_middlewares_http(
    app,
    *,
    no_cdn: bool = True,
    store_context: Optional[ApiStoreContext] = None,
) -> None:
    """Registra trazabilidad estructurada, CORS LAN/Tailscale, CSP y contexto por instancia."""
    csp_app_web = construir_csp_app_web(no_cdn=no_cdn)
    try:
        app.add_middleware(_RegistroConexionesMiddleware)
    except Exception as exc_mw:
        logger.warning("No se pudo activar el middleware de trazabilidad: %s", exc_mw)

    try:
        from starlette.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=_CORS_ORIGIN_REGEX_LAN_TAILSCALE,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Requested-With", "X-Request-ID", "Accept"],
        )

        @app.middleware("http")
        async def _security_headers_middleware(request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
            if request.url.scheme == "https":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            ruta = request.url.path or "/"
            if ruta.startswith(("/api/", "/documentos/", "/documentacion/", "/descargas/")):
                response.headers.setdefault("Content-Security-Policy", _CSP_API_ESTRICTA)
            else:
                response.headers.setdefault("Content-Security-Policy", csp_app_web)
            return response
    except Exception as exc_cors:
        logger.warning("No se pudo activar CORS en la API: %s", exc_cors)

    if store_context is not None:
        try:
            app.add_middleware(_ApiContextMiddleware, store_context=store_context)
        except Exception as exc_ctx:
            logger.warning("No se pudo registrar el contexto API por servidor: %s", exc_ctx)
