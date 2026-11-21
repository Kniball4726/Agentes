"""Rutas estáticas de PWA, favicons, escáner web y distribución OTA móvil."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
from starlette.responses import FileResponse, JSONResponse

from ..paths import application_root

logger = logging.getLogger("stockagent.server")
_APK_HASH_CACHE: dict[str, tuple[float, int, str]] = {}


def _calcular_sha256_apk(apk_path: Path) -> str:
    """Calcula y cachea el hash SHA-256 de un archivo APK según su mtime y tamaño."""
    st = apk_path.stat()
    key = str(apk_path.resolve())
    cached = _APK_HASH_CACHE.get(key)
    if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
        return cached[2]
    h = hashlib.sha256()
    with apk_path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    digest = h.hexdigest().lower()
    _APK_HASH_CACHE[key] = (st.st_mtime, st.st_size, digest)
    return digest


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


def _obtener_web_dir_flet() -> Path | None:
    """Devuelve el directorio web empaquetado por flet_web si está disponible."""
    try:
        from flet_web import get_package_web_dir

        web_dir = Path(get_package_web_dir())
        if web_dir.is_dir():
            return web_dir
    except Exception as exc:
        logger.debug("No se pudo resolver web_dir de flet_web: %s", exc)
    return None


def _resolver_ruta_fuente_roboto(assets_path: Path, web_dir: Path | None = None) -> Path | None:
    """Localiza el archivo local roboto.woff2 (UTF-8 con soporte de tildes y eñes)."""
    candidatos = [
        assets_path / "fonts" / "roboto.woff2",
        assets_path / "assets" / "fonts" / "roboto.woff2",
    ]
    if web_dir is not None:
        candidatos.append(web_dir / "assets" / "fonts" / "roboto.woff2")
    for candidato in candidatos:
        if candidato.is_file():
            return candidato
    return None


def _construir_font_manifest_con_roboto(assets_path: Path) -> list[dict] | None:
    """Construye FontManifest.json incluyendo la fuente local Roboto con soporte de tildes."""
    web_dir = _obtener_web_dir_flet()
    candidatos = [
        assets_path / "FontManifest.json",
        assets_path / "assets" / "FontManifest.json",
    ]
    if web_dir is not None:
        candidatos.append(web_dir / "assets" / "FontManifest.json")

    manifest: list[dict] | None = None
    for candidato in candidatos:
        if candidato.is_file():
            try:
                loaded = json.loads(candidato.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    manifest = loaded
                    break
            except Exception as exc:
                logger.warning("No se pudo leer FontManifest.json en %s: %s", candidato, exc)

    if manifest is None:
        return None

    roboto_path = _resolver_ruta_fuente_roboto(assets_path, web_dir)
    if roboto_path is not None and not any(
        isinstance(item, dict) and item.get("family") == "Roboto" for item in manifest
    ):
        entrada_roboto = {"family": "Roboto", "fonts": [{"asset": "fonts/roboto.woff2"}]}
        insert_idx = (
            1
            if manifest
            and isinstance(manifest[0], dict)
            and manifest[0].get("family") == "MaterialIcons"
            else 0
        )
        manifest.insert(insert_idx, entrada_roboto)

    return manifest


def registrar_rutas_pwa(app, assets_path: Path) -> None:
    """Registra rutas estáticas de PWA (Service Worker, manifest, fuentes, offline y escáner)."""
    no_cache = {"Cache-Control": "no-cache, must-revalidate"}
    recursos: list[tuple[tuple[str, ...], Path, str, dict[str, str]]] = [
        (("/favicon.ico",), assets_path / "favicon.ico", "image/x-icon", no_cache),
        (("/favicon.png",), assets_path / "favicon.png", "image/png", no_cache),
        (
            ("/sw.js", "/service-worker.js", "/flutter_service_worker.js"),
            assets_path / "sw.js",
            "application/javascript; charset=utf-8",
            {
                "Service-Worker-Allowed": "/",
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        ),
        (
            ("/manifest.json",),
            assets_path / "manifest.json",
            "application/manifest+json; charset=utf-8",
            no_cache,
        ),
        (("/offline.html",), assets_path / "offline.html", "text/html; charset=utf-8", no_cache),
        (("/scanner.html",), assets_path / "scanner.html", "text/html; charset=utf-8", no_cache),
        (
            ("/js/scanner.js",),
            assets_path / "js" / "scanner.js",
            "application/javascript; charset=utf-8",
            no_cache,
        ),
        (
            ("/css/scanner.css",),
            assets_path / "css" / "scanner.css",
            "text/css; charset=utf-8",
            no_cache,
        ),
    ]
    for rutas, archivo, media_type, headers in recursos:
        _registrar_recurso_estatico(app, rutas, archivo, media_type, headers)

    web_dir = _obtener_web_dir_flet()
    roboto_path = _resolver_ruta_fuente_roboto(assets_path, web_dir)
    if roboto_path is not None:
        _registrar_recurso_estatico(
            app,
            ("/assets/fonts/roboto.woff2",),
            roboto_path,
            "font/woff2",
            {"Cache-Control": "public, max-age=86400"},
        )

    font_manifest = _construir_font_manifest_con_roboto(assets_path)
    if font_manifest is not None:
        async def _serve_font_manifest():
            return JSONResponse(
                content=font_manifest,
                media_type="application/json; charset=utf-8",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )

        app.add_api_route("/assets/FontManifest.json", _serve_font_manifest, methods=["GET"])


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
            info["sha256"] = _calcular_sha256_apk(apk_file_path)
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
