"""Middlewares ASGI/HTTP de trazabilidad, CORS LAN y cabeceras de seguridad."""

from __future__ import annotations

from datetime import datetime
import logging
import time

logger = logging.getLogger("stockagent.server")


class _RegistroConexionesMiddleware:
    """Middleware ASGI que avisa por consola cuando un dispositivo llega al servidor."""

    _INTERVALO_AVISO_S = 30.0
    _ultimo_aviso: dict[str, float] = {}

    def __init__(self, app):
        self.app = app

    def _registrar_y_notificar(self, scope) -> str | None:
        cliente_ws: str | None = None
        try:
            cliente = (scope.get("client") or ("desconocido", 0))[0]
            try:
                from ..tray import cliente_ws_abierto, registrar_actividad_cliente

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
                    from ..tray import notificar_conexion_cliente

                    notificar_conexion_cliente(cliente, agente)
                except Exception:
                    pass
        except Exception:
            pass
        return cliente_ws

    async def __call__(self, scope, receive, send):
        cliente_ws = (
            self._registrar_y_notificar(scope)
            if scope.get("type") in ("http", "websocket")
            else None
        )
        es_http = scope.get("type") == "http"
        ruta_req = scope.get("path", "") if es_http else ""

        async def _send_filtrado(message):
            if (
                es_http
                and message.get("type") == "http.response.start"
                and ruta_req in ("/", "/index.html", "/assets/FontManifest.json")
            ):
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
                    from ..tray import cliente_ws_cerrado

                    cliente_ws_cerrado(cliente_ws)
                except Exception:
                    pass


_CORS_ORIGIN_REGEX_LAN_TAILSCALE = (
    r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3})(:\d+)?$"
)
_CSP_API_ESTRICTA = "default-src 'self'; frame-ancestors 'self'; object-src 'self'; base-uri 'self'"
_CSP_APP_WEB = (
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


def configurar_middlewares_http(app) -> None:
    """Registra trazabilidad de red, política CORS LAN/Tailscale y cabeceras HTTP seguras."""
    try:
        app.add_middleware(_RegistroConexionesMiddleware)
    except Exception as exc_mw:
        logger.warning("No se pudo activar el aviso de conexiones: %s", exc_mw)

    try:
        from starlette.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=_CORS_ORIGIN_REGEX_LAN_TAILSCALE,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Requested-With", "Accept"],
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
                response.headers.setdefault("Content-Security-Policy", _CSP_APP_WEB)
            return response
    except Exception as exc_cors:
        logger.warning("No se pudo activar CORS en la API: %s", exc_cors)
