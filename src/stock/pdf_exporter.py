"""Exportación de informes tabulares openpyxl a PDF profesional mediante ReportLab."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence
from xml.sax.saxutils import escape

import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_ALINEACIONES_PDF: dict[str, Literal[0, 1, 2]] = {
    "left": 0,
    "center": 1,
    "right": 2,
}


def _color_excel(color) -> colors.Color | None:
    if color is None or color.type != "rgb" or not color.rgb:
        return None
    codigo = str(color.rgb)[-6:]
    try:
        return colors.HexColor(f"#{codigo}")
    except ValueError:
        return None


def _formatear_valor(celda) -> str:
    val = celda.value
    if val is None:
        return ""
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    return escape(str(val)).replace("\n", "<br/>")


def _construir_tabla_seccion(
    hoja,
    fila_inicio: int,
    fila_fin: int,
    columnas: Sequence[int],
    anchos: list[float],
    prefijo_estilo: str,
    repeat_rows: int = 2,
) -> Table | None:
    """Renderiza un rango continuo de filas de Excel como una `Table` de ReportLab."""
    contenido: list[list[Paragraph]] = []
    estilos: list[tuple] = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    max_col_idx = len(columnas) - 1
    mapeo_filas: dict[int, int] = {}

    for num_f in range(fila_inicio, fila_fin):
        celdas_fila = [hoja.cell(num_f, c) for c in columnas]
        textos_fila = [_formatear_valor(c) for c in celdas_fila]
        if all(not t for t in textos_fila):
            continue

        idx_tabla = len(contenido)
        mapeo_filas[num_f] = idx_tabla
        fila_elems: list[Paragraph] = []

        for col_idx, c in enumerate(celdas_fila):
            align_code = _ALINEACIONES_PDF.get(c.alignment.horizontal or "left", 0)
            font_name = "Helvetica-Bold" if c.font and c.font.bold else "Helvetica"
            font_size = c.font.size if c.font and c.font.size else 9
            color_texto = (_color_excel(c.font.color) if c.font else None) or colors.black

            st_par = ParagraphStyle(
                name=f"{prefijo_estilo}_{num_f}_{col_idx}",
                fontName=font_name,
                fontSize=font_size,
                leading=font_size + 3,
                textColor=color_texto,
                alignment=align_code,
            )
            fila_elems.append(Paragraph(_formatear_valor(c), st_par))

            bg = _color_excel(c.fill.fgColor) if c.fill and c.fill.fill_type == "solid" else None
            if bg:
                estilos.append(("BACKGROUND", (col_idx, idx_tabla), (col_idx, idx_tabla), bg))

            if c.border:
                for side_name, side_obj in (
                    ("TOP", c.border.top),
                    ("BOTTOM", c.border.bottom),
                    ("LEFT", c.border.left),
                    ("RIGHT", c.border.right),
                ):
                    if side_obj and side_obj.style:
                        b_col = _color_excel(side_obj.color) or colors.HexColor("#D6DEE8")
                        b_w = 1.0 if side_obj.style in ("medium", "thick") else 0.5
                        cmd = f"{side_name}GRID" if side_name in ("TOP", "BOTTOM") else side_name
                        estilos.append((cmd, (col_idx, idx_tabla), (col_idx, idx_tabla), b_w, b_col))

        contenido.append(fila_elems)

    for r_m in hoja.merged_cells.ranges:
        if r_m.min_row >= fila_inicio and r_m.max_row < fila_fin:
            r_target_min = mapeo_filas.get(r_m.min_row)
            r_target_max = mapeo_filas.get(r_m.max_row)
            if r_target_min is not None and r_target_max is not None:
                estilos.append(("SPAN", (r_m.min_col - 1, r_target_min), (min(r_m.max_col - 1, max_col_idx), r_target_max)))

    if not contenido:
        return None
    tabla = Table(
        contenido,
        colWidths=anchos,
        repeatRows=min(repeat_rows, len(contenido)),
        hAlign="LEFT",
        splitByRow=1,
    )
    tabla.setStyle(TableStyle(estilos))
    return tabla


def guardar_informe_pdf(libro: openpyxl.Workbook, ruta: Path) -> None:
    """Convierte el contenido visual del informe openpyxl a un documento PDF profesional."""
    hoja = libro.active
    if hoja is None:
        raise ValueError("El informe no contiene una hoja activa para exportar.")

    ancho_util = A4[0] - 4 * cm
    fila_inicio_pedidos = None
    fila_inicio_no_descontados = None

    for num_f in range(1, hoja.max_row + 1):
        val_a = str(hoja.cell(num_f, 1).value or "").strip().upper()
        if "PEDIDOS CON PRODUCTOS DESCONTADOS" in val_a and fila_inicio_pedidos is None:
            fila_inicio_pedidos = num_f
        elif "PRODUCTOS NO DESCONTADOS" in val_a and fila_inicio_no_descontados is None:
            fila_inicio_no_descontados = num_f

    tiene_secciones = (fila_inicio_pedidos is not None) or (fila_inicio_no_descontados is not None)

    def pie_pagina(canvas, documento) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5B6573"))
        canvas.setStrokeColor(colors.HexColor("#D6DEE8"))
        canvas.setLineWidth(0.4)
        canvas.line(2 * cm, 1.8 * cm + 6, A4[0] - 2 * cm, 1.8 * cm + 6)
        canvas.drawString(2 * cm, 1.8 * cm - 6, "StockAgent · Informe de Control de Stock")
        canvas.drawRightString(A4[0] - 2 * cm, 1.8 * cm - 6, f"Página {documento.page}")
        canvas.restoreState()

    elementos = []
    if tiene_secciones:
        fin_catalogo = (
            fila_inicio_pedidos
            if fila_inicio_pedidos is not None
            else (fila_inicio_no_descontados if fila_inicio_no_descontados is not None else hoja.max_row + 1)
        )
        anchos_cat = [2.4 * cm, ancho_util - 6.0 * cm, 3.6 * cm]
        t_cat = _construir_tabla_seccion(hoja, 1, fin_catalogo, (1, 2, 3), anchos_cat, "cat")
        if t_cat is not None:
            elementos.append(t_cat)

        if fila_inicio_pedidos is not None:
            elementos.append(Spacer(1, 14))
            fin_ped = fila_inicio_no_descontados if fila_inicio_no_descontados is not None else hoja.max_row + 1
            anchos_ped = [3.2 * cm, 8.0 * cm, max(2.0 * cm, ancho_util - 11.2 * cm)]
            t_ped = _construir_tabla_seccion(hoja, fila_inicio_pedidos, fin_ped, (1, 2, 3), anchos_ped, "ped")
            if t_ped is not None:
                elementos.append(t_ped)

        if fila_inicio_no_descontados is not None:
            elementos.append(Spacer(1, 14))
            anchos_nd = [2.0 * cm, 3.8 * cm, 6.4 * cm, max(2.0 * cm, ancho_util - 12.2 * cm)]
            t_nd = _construir_tabla_seccion(hoja, fila_inicio_no_descontados, hoja.max_row + 1, (1, 2, 3, 4), anchos_nd, "nd")
            if t_nd is not None:
                elementos.append(t_nd)
    else:
        total_columnas = max(1, min(hoja.max_column, 6))
        anchos = [ancho_util / total_columnas] * total_columnas
        t_gen = _construir_tabla_seccion(
            hoja,
            1,
            hoja.max_row + 1,
            tuple(range(1, total_columnas + 1)),
            anchos,
            "p",
            repeat_rows=3,
        )
        if t_gen is not None:
            elementos.append(t_gen)

    documento = SimpleDocTemplate(
        str(ruta),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=ruta.stem,
    )
    documento.build(elementos, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
