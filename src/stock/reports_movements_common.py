"""Utilidades compartidas de formato PDF/Excel para reportes de movimientos y canales."""

from __future__ import annotations

from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table, TableStyle

from ..core.sanitize_utils import escapar_texto_reportlab, sanitizar_celda_excel, sanitizar_fila_excel
from .report_styles import (
    _BORDER_THIN,
    _FILL_HEADER,
    _FONT_BOLD,
    _FONT_HEADER,
    estilizar_fila_excel,
)


def _fmt_num(valor: int) -> str:
    return str(valor) if valor > 0 else "—"


def _construir_bloque_kpis_pdf(tarjetas: list[tuple[str, str]], st: dict[str, ParagraphStyle]) -> Table:
    """Construye una fila horizontal compacta de tarjetas KPI en PDF."""
    fila_titulos = [
        Paragraph(
            f"<b>{escapar_texto_reportlab(lbl)}</b>",
            ParagraphStyle("KpiT", parent=st["sub"], fontSize=7.5, alignment=1, textColor=colors.HexColor("#475569")),
        )
        for lbl, _ in tarjetas
    ]
    fila_valores = [
        Paragraph(
            f"<b>{escapar_texto_reportlab(val)}</b>",
            ParagraphStyle("KpiV", parent=st["td_center"], fontSize=11, leading=13, textColor=colors.HexColor("#0f172a")),
        )
        for _, val in tarjetas
    ]
    ancho_total = 18.6 * cm
    ancho_celda = ancho_total / max(1, len(tarjetas))
    tabla = Table([fila_titulos, fila_valores], colWidths=[ancho_celda] * len(tarjetas))
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return tabla


def _construir_titulo_seccion_pdf(texto: str, st: dict[str, ParagraphStyle]) -> Paragraph:
    estilo = ParagraphStyle(
        "SecMov",
        parent=st["titulo"],
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=6,
        spaceAfter=4,
    )
    return Paragraph(escapar_texto_reportlab(texto), estilo)


def _construir_firmas_pdf(st: dict[str, ParagraphStyle]) -> Table:
    tabla = Table(
        [
            ["_______________________________", "_______________________________"],
            [
                Paragraph("Firma Operador / Armador", st["td_center"]),
                Paragraph("Control / Supervisión Administración", st["td_center"]),
            ],
        ],
        colWidths=[9.3 * cm, 9.3 * cm],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, 0), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tabla


def _escribir_seccion_excel(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    titulo_seccion: str,
    headers: list[str],
    filas: list[list[Any]],
    fila_totales: list[Any] | None = None,
) -> None:
    """Agrega un bloque titulado con encabezados, filas cebreadas y totales opcionales."""
    if ws.max_row > 1:
        ws.append([])
    ws.append([sanitizar_celda_excel(titulo_seccion)])
    fila_sec = ws.max_row
    ws.cell(fila_sec, 1).font = Font(name="Calibri", size=11, bold=True, color="1E293B")
    ws.cell(fila_sec, 1).fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    ws.append(sanitizar_fila_excel(headers))
    fila_hdr = ws.max_row
    for c_idx in range(1, len(headers) + 1):
        celda = ws.cell(fila_hdr, c_idx)
        celda.fill = _FILL_HEADER
        celda.font = _FONT_HEADER
        celda.alignment = Alignment(horizontal="center", vertical="center")

    for idx_r, row_vals in enumerate(filas):
        ws.append(sanitizar_fila_excel(row_vals))
        estilizar_fila_excel(ws, ws.max_row, len(headers), idx_r % 2 == 1)

    if fila_totales:
        ws.append(sanitizar_fila_excel(fila_totales))
        r_tot = ws.max_row
        fill_tot = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
        for c_idx in range(1, len(headers) + 1):
            celda = ws.cell(r_tot, c_idx)
            celda.font = _FONT_BOLD
            celda.border = _BORDER_THIN
            celda.fill = fill_tot


def _estilo_estado_cell(estado: str, st: dict[str, ParagraphStyle]) -> Paragraph:
    if estado == "AGOTADO":
        return Paragraph("AGOTADO", st["agotado"])
    if estado in ("QUIEBRE_INMINENTE", "CRITICO"):
        return Paragraph("QUIEBRE", st["critico"])
    if estado == "SOBRESTOCK":
        return Paragraph("SOBRESTOCK", st["td_center"])
    return Paragraph("OK", st["td_center"])


def _ordenar_items_por_catalogo(
    items: list[dict[str, Any]],
    mapa_orden_catalogo: dict[str, int] | None,
) -> list[dict[str, Any]]:
    if not mapa_orden_catalogo:
        return sorted(items, key=lambda x: str(x.get("codigo") or x.get("code") or ""))
    return sorted(
        items,
        key=lambda x: (
            mapa_orden_catalogo.get(str(x.get("codigo") or x.get("code") or ""), 999999),
            str(x.get("codigo") or x.get("code") or ""),
        ),
    )
