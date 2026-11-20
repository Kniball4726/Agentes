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
from ...core.security_utils import ruta_en_directorios_permitidos
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


def _directorios_documentos_permitidos(app_root: Path) -> list[Path]:
    """Lista blanca estricta de directorios habilitados para visualización/descarga."""
    return [
        (app_root / "data" / "pedidos_archivos").resolve(),
        (app_root / "data" / "informes").resolve(),
        (app_root / "data_qa" / "pedidos_archivos").resolve(),
        (app_root / "data_qa" / "informes").resolve(),
        (app_root / "Descuentos").resolve(),
        (app_root / "Descuentos_QA").resolve(),
        (app_root / "Documentacion").resolve(),
        (app_root / "Fabrica").resolve(),
        (app_root / "StockFisico").resolve(),
    ]


def resolver_ruta_documento(ruta_param: str) -> Path:
    """Resuelve y valida un documento usando lista blanca de carpetas y protección anti-traversal."""
    if not ruta_param or not ruta_param.strip():
        raise HTTPException(status_code=400, detail="Debe especificar la ruta o nombre del documento.")

    app_root = Path(application_root()).resolve()
    carpetas_permitidas = _directorios_documentos_permitidos(app_root)

    # Limpiar prefijos y normalizar separadores
    ruta_limpia = ruta_param.strip().replace("\\", "/").lstrip("/")
    partes_req = Path(ruta_limpia).parts
    if ".." in partes_req or PARTES_PROHIBIDAS.intersection({p.lower() for p in partes_req}):
        logger.warning("Intento de acceso a ruta confidencial o traversal: %s", ruta_param)
        raise HTTPException(status_code=403, detail="Acceso denegado a recurso restringido.")

    tiene_subruta = "/" in ruta_limpia
    candidato: Path | None = None

    if tiene_subruta:
        cand = (app_root / ruta_limpia).resolve()
        if not cand.is_relative_to(app_root):
            logger.warning("Intento de acceso fuera del directorio raíz: %s", ruta_param)
            raise HTTPException(status_code=403, detail="Acceso denegado: ruta fuera de los límites permitidos.")
        if PARTES_PROHIBIDAS.intersection({p.lower() for p in cand.parts}):
            logger.warning("Intento de acceso a recurso confidencial: %s", cand)
            raise HTTPException(status_code=403, detail="Acceso denegado a recurso restringido.")
        if not ruta_en_directorios_permitidos(cand, carpetas_permitidas):
            logger.warning("Intento de acceso fuera de carpetas de documentos autorizadas: %s", cand)
            raise HTTPException(status_code=403, detail="Acceso denegado: carpeta no autorizada para documentos.")
        candidato = cand
    else:
        ext_req = Path(ruta_limpia).suffix.lower()
        if ext_req not in EXTENSIONES_PERMITIDAS:
            raise HTTPException(
                status_code=403,
                detail=f"El tipo de archivo '{ext_req}' no está permitido para visualización.",
            )
        nombre_base = Path(ruta_limpia).name
        for carpeta in carpetas_permitidas:
            if not carpeta.exists():
                continue
            posible = (carpeta / nombre_base).resolve()
            if posible.is_relative_to(carpeta) and posible.exists() and posible.is_file():
                candidato = posible
                break
        if candidato is None:
            posible_raiz = (app_root / nombre_base).resolve()
            if posible_raiz.is_relative_to(app_root) and posible_raiz.exists() and posible_raiz.is_file():
                logger.warning("Intento de acceso a archivo en raíz no autorizado: %s", posible_raiz)
                raise HTTPException(status_code=403, detail="Acceso denegado: archivo fuera de carpetas autorizadas.")
            raise HTTPException(
                status_code=404,
                detail=f"El documento '{nombre_base}' no fue encontrado en el servidor.",
            )

    # Validación final sobre el candidato resuelto
    partes_lower = {p.lower() for p in candidato.parts}
    if PARTES_PROHIBIDAS.intersection(partes_lower) or not ruta_en_directorios_permitidos(candidato, carpetas_permitidas):
        logger.warning("Intento de acceso a recurso confidencial: %s", candidato)
        raise HTTPException(status_code=403, detail="Acceso denegado a recurso restringido.")

    if not candidato.exists() or not candidato.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"El documento '{Path(ruta_param).name}' no fue encontrado en el servidor.",
        )

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
