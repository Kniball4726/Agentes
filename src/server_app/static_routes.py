"""Rutas estáticas de PWA, favicons, escáner web y distribución OTA móvil."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from starlette.responses import FileResponse, JSONResponse

from ..paths import application_root

logger = logging.getLogger("stockagent.server")


def _registrar_recurso_estatico(
    app,
    rutas: tuple[str, ...],
    archivo: Path,
    media_type: str,
    headers: dict[str, str],
) -> None:
    if not archivo.exists():
        return

    async def _endpoint():
        return FileResponse(str(archivo), media_type=media_type, headers=headers)

    for ruta in rutas:
        app.add_api_route(ruta, _endpoint, methods=["GET"])


def registrar_rutas_pwa(app, assets_path: Path) -> None:
    """Registra rutas estáticas de PWA (Service Worker, manifest, offline y escáner)."""
    no_cache = {"Cache-Control": "no-cache, must-revalidate"}
    recursos: list[tuple[tuple[str, ...], Path, str, dict[str, str]]] = [
        (("/favicon.ico",), assets_path / "favicon.ico", "image/x-icon", no_cache),
        (("/favicon.png",), assets_path / "favicon.png", "image/png", no_cache),
        (
            ("/sw.js", "/service-worker.js", "/flutter_service_worker.js"),
            assets_path / "sw.js",
            "application/javascript",
            {
                "Service-Worker-Allowed": "/",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        ),
        (
            ("/manifest.json",),
            assets_path / "manifest.json",
            "application/manifest+json",
            no_cache,
        ),
        (("/offline.html",), assets_path / "offline.html", "text/html", no_cache),
        (("/scanner.html",), assets_path / "scanner.html", "text/html", no_cache),
        (
            ("/js/scanner.js",),
            assets_path / "js" / "scanner.js",
            "application/javascript",
            no_cache,
        ),
        (
            ("/css/scanner.css",),
            assets_path / "css" / "scanner.css",
            "text/css",
            no_cache,
        ),
    ]
    for rutas, archivo, media_type, headers in recursos:
        _registrar_recurso_estatico(app, rutas, archivo, media_type, headers)


def registrar_rutas_ota(app) -> None:
    """Registra el repositorio local de actualizaciones OTA para Android (.apk)."""
    dist_movil_path = Path(application_root()) / "stockagent_mobile" / "dist_movil"
    if not dist_movil_path.exists():
        dist_movil_path = Path(application_root()) / "dist_movil"
    apk_file_path = dist_movil_path / "StockAgent.apk"
    version_json_path = dist_movil_path / "version.json"

    @app.get("/actualizaciones/version.json")
    @app.get("/api/version")
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
                loaded = json.loads(version_json_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    info.update(loaded)
            except Exception as err_v:
                logger.warning("Error al leer version.json: %s", err_v)

        if apk_file_path.exists():
            st = apk_file_path.stat()
            info["file_size"] = st.st_size
            if not info.get("updated_at"):
                info["updated_at"] = datetime.fromtimestamp(st.st_mtime).strftime(
                    "%d/%m/%Y %H:%M"
                )

        return JSONResponse(
            content=info,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    @app.get("/actualizaciones/StockAgent.apk")
    @app.get("/dist_movil/StockAgent.apk")
    async def _serve_apk_download():
        if not apk_file_path.exists():
            return JSONResponse(
                status_code=404,
                content={
                    "error": "El instalador StockAgent.apk aún no ha sido compilado en la PC."
                },
            )
        return FileResponse(
            str(apk_file_path),
            media_type="application/vnd.android.package-archive",
            filename="StockAgent.apk",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
