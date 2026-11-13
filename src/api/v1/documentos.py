"""Endpoints para visualización, previsualización y descarga de documentos de StockAgent."""

from __future__ import annotations

import logging
import mimetypes
import urllib.parse
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..deps import require_document_access
from ...paths import application_root

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documentos", tags=["Documentos"])

# Extensiones autorizadas para consulta y visualización inline
EXTENSIONES_PERMITIDAS = {
    ".pdf",
    ".xlsx",
    ".xls",
    ".docx",
    ".doc",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".txt",
    ".csv",
}

# Carpetas y archivos estrictamente protegidos / prohibidos
PARTES_PROHIBIDAS = {
    ".git",
    ".env",
    ".venv",
    "__pycache__",
    ".vscode",
    "usuarios.sqlite3",
    "usuarios.db",
    "secretos.py",
    "certs",
    "backups",
    "logs",
    ".clave_secretos",
}


def resolver_ruta_documento(ruta_param: str) -> Path:
    """Resuelve y valida la ruta de un documento contra Path Traversal y carpetas no autorizadas."""
    if not ruta_param or not ruta_param.strip():
        raise HTTPException(status_code=400, detail="Debe especificar la ruta o nombre del documento.")

    app_root = Path(application_root()).resolve()

    # Limpiar prefijos y normalizar separadores
    ruta_limpia = ruta_param.strip().replace("\\", "/").lstrip("/")
    if PARTES_PROHIBIDAS.intersection({p.lower() for p in Path(ruta_limpia).parts}):
        logger.warning("Intento de acceso a ruta confidencial: %s", ruta_param)
        raise HTTPException(status_code=403, detail="Acceso denegado a recurso restringido.")

    candidato = (app_root / ruta_limpia).resolve()

    # Si no existe directamente, intentar ubicarlo en las carpetas estándar de documentos
    if not candidato.exists() or not candidato.is_file():
        nombre_base = Path(ruta_limpia).name
        carpetas_busqueda = [
            app_root / "data" / "pedidos_archivos",
            app_root / "data" / "informes",
            app_root / "data",
            app_root / "Descuentos",
            app_root / "Documentacion",
        ]
        for carpeta in carpetas_busqueda:
            if not carpeta.exists():
                continue
            posible = (carpeta / nombre_base).resolve()
            if posible.exists() and posible.is_file():
                candidato = posible
                break

    # 1. Seguridad: Verificar que esté estrictamente dentro de app_root (Anti-Path Traversal)
    try:
        if not candidato.is_relative_to(app_root):
            logger.warning("Intento de acceso fuera del directorio raíz: %s", ruta_param)
            raise HTTPException(status_code=403, detail="Acceso denegado: ruta fuera de los límites permitidos.")
    except (ValueError, AttributeError):
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    # 2. Validar partes prohibidas antes de verificar existencia (evita enumeración)
    partes_lower = {p.lower() for p in candidato.parts}
    if PARTES_PROHIBIDAS.intersection(partes_lower):
        logger.warning("Intento de acceso a recurso confidencial: %s", candidato)
        raise HTTPException(status_code=403, detail="Acceso denegado a recurso restringido.")

    # 3. Existencia del archivo
    if not candidato.exists() or not candidato.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"El documento '{Path(ruta_param).name}' no fue encontrado en el servidor.",
        )

    # 4. Validar extensión
    ext = candidato.suffix.lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(
            status_code=403,
            detail=f"El tipo de archivo '{ext}' no está permitido para visualización.",
        )

    return candidato


@router.get("/ver", summary="Visualizar documento inline (sin descarga forzada)")
@router.get("/visor", summary="Visualizar documento inline")
async def ver_documento(
    p: str = Query(..., description="Ruta relativa o nombre del documento"),
    descargar: bool = Query(False, description="Forzar descarga en vez de visualización inline"),
    _user: Dict[str, Any] = Depends(require_document_access),
):
    """Sirve un documento con cabecera Content-Disposition: inline por defecto.

    Permite visualizar el archivo directamente en una pestaña del navegador con herramientas
    nativas de impresión (Ctrl+P / botón Imprimir) y descarga manual bajo demanda.
    """
    archivo = resolver_ruta_documento(p)
    ext = archivo.suffix.lower()

    # Mapeo de Media Types
    media_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".txt": "text/plain; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
    }
    media_type = media_types.get(ext) or mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"

    safe_filename = archivo.name
    quoted_filename = urllib.parse.quote(safe_filename)

    disposition_type = "attachment" if descargar else "inline"
    headers = {
        "Content-Disposition": f'{disposition_type}; filename="{safe_filename}"; filename*=UTF-8\'\'{quoted_filename}',
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    return FileResponse(
        path=str(archivo),
        media_type=media_type,
        filename=safe_filename,
        headers=headers,
    )


@router.get("/ver/{nombre_archivo:path}", summary="Visualizar documento por nombre directo o subruta")
async def ver_documento_path(
    nombre_archivo: str,
    descargar: bool = Query(False),
    _user: Dict[str, Any] = Depends(require_document_access),
):
    """Alias para visualización directa mediante ruta en path."""
    return await ver_documento(p=nombre_archivo, descargar=descargar, _user=_user)
