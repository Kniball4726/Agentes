"""Rutas web protegidas para manuales oficiales PDF e informes generados."""

from __future__ import annotations

import logging
from pathlib import Path
from fastapi import Depends
from starlette.responses import FileResponse, JSONResponse

from ..paths import application_root

logger = logging.getLogger("stockagent.server")

EXTENSIONES_INFORME = {
    ".pdf",
    ".xlsx",
    ".xlsm",
    ".xls",
    ".docx",
    ".doc",
    ".csv",
    ".txt",
}

_MEDIA_TYPES_INFORME = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
}


def _buscar_informe_seguro(base_app: Path, nombre_seguro: str) -> Path | None:
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
    for cand in rutas_candidatas:
        res_cand = cand.resolve()
        if res_cand.is_relative_to(base_app) and res_cand.exists() and res_cand.is_file():
            return res_cand

    base_desc = (base_app / "Descuentos").resolve()
    if base_desc.exists():
        for arch in base_desc.rglob("*"):
            if arch.is_file() and arch.name == nombre_seguro:
                res_arch = arch.resolve()
                if res_arch.is_relative_to(base_desc):
                    return res_arch
    return None


def registrar_rutas_documentos_e_informes(app) -> None:
    """Registra rutas autenticadas para manuales, visor universal e informes."""
    from ..api.deps import require_document_access

    doc_dir_path = (Path(application_root()) / "Documentacion").resolve()

    @app.get("/documentacion/{nombre_archivo}")
    @app.get("/docs/{nombre_archivo}")
    async def _serve_doc_pdf(
        nombre_archivo: str,
        _user=Depends(require_document_access),
    ):
        nombre_seguro = Path(nombre_archivo).name
        if not nombre_seguro or not nombre_seguro.lower().endswith(".pdf"):
            return JSONResponse(
                status_code=403,
                content={"error": "Solo se permite visualizar manuales oficiales en formato PDF."},
            )
        archivo_pdf = (doc_dir_path / nombre_seguro).resolve()
        if not archivo_pdf.is_relative_to(doc_dir_path) or not archivo_pdf.is_file():
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

    try:
        from ..api.v1.documentos import ver_documento, ver_documento_path

        app.add_api_route("/documentos/ver", ver_documento, methods=["GET"])
        app.add_api_route("/documentos/visor", ver_documento, methods=["GET"])
        app.add_api_route("/documentos/ver/{nombre_archivo:path}", ver_documento_path, methods=["GET"])
    except Exception as exc_doc:
        logger.warning("No se pudieron montar rutas directas para documentos: %s", exc_doc)

    @app.get("/descargas/informes/{nombre_archivo}")
    @app.get("/descargas/informe/{nombre_archivo}")
    @app.get("/api/v1/informes/descargar/{nombre_archivo}")
    async def _serve_informe_descarga(
        nombre_archivo: str,
        _user=Depends(require_document_access),
    ):
        nombre_seguro = Path(nombre_archivo).name
        if not nombre_seguro or any(ch in nombre_seguro for ch in ("*", "?", "[", "]")):
            return JSONResponse(status_code=400, content={"error": "Nombre de informe inválido."})
        sufijo_req = Path(nombre_seguro).suffix.lower()
        if sufijo_req not in EXTENSIONES_INFORME:
            return JSONResponse(
                status_code=403,
                content={"error": f"El tipo de archivo '{sufijo_req}' no está habilitado para descarga."},
            )
        base_app = Path(application_root()).resolve()
        archivo_encontrado = _buscar_informe_seguro(base_app, nombre_seguro)
        if not archivo_encontrado or not archivo_encontrado.is_file():
            return JSONResponse(
                status_code=404,
                content={"error": f"El informe '{nombre_seguro}' no se encuentra disponible."},
            )
        sufijo = archivo_encontrado.suffix.lower()
        if sufijo not in EXTENSIONES_INFORME:
            return JSONResponse(
                status_code=403,
                content={"error": f"El tipo de archivo '{sufijo}' no está habilitado para descarga."},
            )
        media = _MEDIA_TYPES_INFORME.get(sufijo, "application/octet-stream")
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
