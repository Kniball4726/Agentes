"""Utilidades compartidas de QR, formateo de cliente y grilla A4 para rótulos."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, SimpleDocTemplate, Table, TableStyle

ETIQUETAS_POR_HOJA = 6
FILAS_POR_HOJA = 3
COLUMNAS_POR_HOJA = 2


def _crear_qr_drawing(contenido: str, tamano_cm: float = 1.7) -> Drawing:
    """Genera un componente visual ReportLab con el código QR vectorizado."""
    qr_widget = QrCodeWidget(contenido)
    bounds = qr_widget.getBounds()
    ancho_orig = bounds[2] - bounds[0]
    alto_orig = bounds[3] - bounds[1]
    tam_puntos = tamano_cm * cm
    sx = tam_puntos / max(ancho_orig, 1)
    sy = tam_puntos / max(alto_orig, 1)
    d = Drawing(tam_puntos, tam_puntos, transform=[sx, 0, 0, sy, 0, 0])
    d.add(qr_widget)
    return d


def _es_pedido_agregado(pedido: Any) -> bool:
    """Determina si un pedido corresponde a un agregado."""
    val = getattr(pedido, "agregado", False)
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "si", "sí", "t", "agregado")
    return False


def _formatear_cliente_etiqueta(pedido: Any) -> str:
    """Formatea el nombre del cliente añadiendo `'Agregado'` y `'Nro ...'` si corresponde."""
    cliente_base = (getattr(pedido, "cliente", "") or "").strip()
    if _es_pedido_agregado(pedido):
        if not re.search(r"\bagregado\b", cliente_base, re.IGNORECASE):
            cliente_base = f"{cliente_base} Agregado"

    num_ped = str(getattr(pedido, "numero_pedido", "") or "").strip()
    if num_ped:
        if not re.search(r"\b(nro|n°|nº|numero)\b", num_ped, re.IGNORECASE):
            sufijo_pedido = f"Nro {num_ped}"
        else:
            sufijo_pedido = num_ped
        return f"{cliente_base} {sufijo_pedido}"
    return cliente_base


def compilar_grilla_a4_pdf(tarjetas: list[Table], ruta_pdf: Path) -> Path:
    """Maqueta una lista de tarjetas en páginas A4 en grilla 2x3 (6 rótulos por hoja)."""
    story: list = []
    for i in range(0, len(tarjetas), ETIQUETAS_POR_HOJA):
        chunk = tarjetas[i : i + ETIQUETAS_POR_HOJA]
        while len(chunk) < ETIQUETAS_POR_HOJA:
            chunk.append("")  # type: ignore[arg-type]

        grid_data = [
            [chunk[0], chunk[1]],
            [chunk[2], chunk[3]],
            [chunk[4], chunk[5]],
        ]
        grid_table = Table(
            grid_data,
            colWidths=[9.8 * cm, 9.8 * cm],
            rowHeights=[9.3 * cm, 9.3 * cm, 9.3 * cm],
        )
        grid_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(grid_table)
        if i + ETIQUETAS_POR_HOJA < len(tarjetas):
            story.append(PageBreak())

    doc = SimpleDocTemplate(
        str(ruta_pdf),
        pagesize=A4,
        leftMargin=0.6 * cm,
        rightMargin=0.6 * cm,
        topMargin=0.6 * cm,
        bottomMargin=0.6 * cm,
    )
    doc.build(story)
    return ruta_pdf
