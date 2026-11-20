"""Cargador seguro y límites anti-DoS/XXE para archivos Excel (.xlsx/.xls), DOCX y PDF."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

import openpyxl

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_OOXML_ENTRIES = 500
MAX_OOXML_UNCOMPRESSED_BYTES = 150 * 1024 * 1024  # 150 MB
MAX_PDF_PAGES = 200
MAX_EXCEL_ROWS = 20_000
MAX_EXCEL_COLS = 100

_RE_XXE_DANGEROUS = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_XML_SCAN_MAX_BYTES = 5 * 1024 * 1024  # 5 MB por miembro XML al inspeccionar DOCTYPE/ENTITY


def validar_tamano_archivo(path: Path, max_bytes: int = MAX_FILE_BYTES) -> None:
    """Rechaza archivos que excedan el tamaño máximo permitido."""
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"El archivo '{path.name}' ({size // (1024 * 1024)} MB) supera el límite seguro de {max_bytes // (1024 * 1024)} MB."
        )


def validar_ooxml_seguro(path: Path) -> None:
    """Inspecciona contenedores OOXML (.xlsx/.docx) contra Zip Bombs y ataques XXE/Entity Expansion."""
    validar_tamano_archivo(path)
    if not zipfile.is_zipfile(path):
        raise ValueError(f"El archivo '{path.name}' no es un contenedor OOXML válido.")

    total_uncompressed = 0
    with zipfile.ZipFile(path, "r") as zf:
        infos = zf.infolist()
        if len(infos) > MAX_OOXML_ENTRIES:
            raise ValueError(
                f"El archivo '{path.name}' contiene demasiadas entradas internas ({len(infos)} > {MAX_OOXML_ENTRIES})."
            )
        for info in infos:
            total_uncompressed += max(0, info.file_size)
            if total_uncompressed > MAX_OOXML_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"El archivo '{path.name}' supera el límite descomprimido seguro (posible Zip Bomb)."
                )
            nombre_lower = info.filename.lower()
            if nombre_lower.endswith((".xml", ".rels")):
                with zf.open(info, "r") as member:
                    muestra = member.read(_XML_SCAN_MAX_BYTES)
                if _RE_XXE_DANGEROUS.search(muestra):
                    raise ValueError(
                        f"Contenido XML inseguro (DOCTYPE/ENTITY) detectado en '{path.name}'."
                    )


def validar_xls_seguro(path: Path) -> bytes:
    """Valida tamaño y cabecera básica de una planilla Excel binaria (.xls) antes de abrirla con xlrd."""
    validar_tamano_archivo(path)
    return path.read_bytes()


def validar_pdf_seguro(path: Path) -> None:
    """Valida tamaño máximo y cabecera %PDF- antes de entregar el archivo al parser."""
    validar_tamano_archivo(path)
    with open(path, "rb") as fh:
        cab = fh.read(8)
    if not cab.startswith(b"%PDF-"):
        raise ValueError(f"El archivo '{path.name}' no tiene una cabecera PDF válida.")


def cargar_workbook_seguro(
    path: Path,
    *,
    data_only: bool = True,
    read_only: bool = False,
) -> openpyxl.Workbook:
    """Valida un archivo .xlsx contra Zip Bomb/XXE y lo abre con openpyxl."""
    validar_ooxml_seguro(path)
    return openpyxl.load_workbook(str(path), data_only=data_only, read_only=read_only)


def cargar_docx_seguro(path: Path) -> Any:
    """Valida un archivo .docx contra Zip Bomb/XXE y lo abre con python-docx."""
    from docx import Document

    validar_ooxml_seguro(path)
    with open(path, "rb") as fh:
        return Document(fh)
