"""Estilos, canvas numerado y constructores base PDF/Excel para reportes de servicio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FILL_HEADER = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
_FILL_ZEBRA = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
_FILL_WHITE = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
_FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
_FONT_BODY = Font(name="Calibri", size=10)
_FONT_BOLD = Font(name="Calibri", size=10, bold=True)
_BORDER_THIN = Border(
    left=Side(style="thin", color="E2E8F0"),
    right=Side(style="thin", color="E2E8F0"),
    top=Side(style="thin", color="E2E8F0"),
    bottom=Side(style="thin", color="E2E8F0"),
)


class _ReporteNumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para numeración precisa 'Página X de Y'."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []
        self.titulo_reporte: str = "StockAgent · Reporte"
        self.fecha_emision: str = ""

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_page_states)
        for estado in self._saved_page_states:
            self.__dict__.update(estado)
            self.dibujar_pie(total)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def dibujar_pie(self, total_paginas: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(1.2 * cm, 1.2 * cm, A4[0] - 1.2 * cm, 1.2 * cm)
        self.drawString(1.2 * cm, 0.8 * cm, f"{self.titulo_reporte} · Emitido: {self.fecha_emision}")
        self.drawRightString(A4[0] - 1.2 * cm, 0.8 * cm, f"Página {self._pageNumber} de {total_paginas}")
        self.restoreState()


def _autoajustar_columnas_excel(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
    """Ajusta automáticamente el ancho de cada columna según su contenido."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)


def crear_hoja_reporte_excel(
    titulo_hoja: str,
    titulo_reporte: str,
    subtitulo: str,
    headers: list[str],
) -> tuple[openpyxl.Workbook, Any]:
    """Inicializa un libro openpyxl con cabecera estilizada corporativa."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = titulo_hoja
    ws.append([titulo_reporte])
    ws.cell(1, 1).font = Font(name="Calibri", size=14, bold=True, color="1E293B")
    ws.append([subtitulo])
    ws.append([])
    ws.append(headers)
    for c_idx in range(1, len(headers) + 1):
        cell = ws.cell(4, c_idx)
        cell.fill = _FILL_HEADER
        cell.font = _FONT_HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center")
    return wb, ws


def estilizar_fila_excel(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    row_idx: int,
    num_cols: int,
    es_zebra: bool = False,
) -> None:
    """Aplica fuente, borde y relleno cebreado uniforme a una fila Excel."""
    fill_row = _FILL_ZEBRA if es_zebra else _FILL_WHITE
    for c_idx in range(1, num_cols + 1):
        celda = ws.cell(row_idx, c_idx)
        celda.font = _FONT_BODY
        celda.border = _BORDER_THIN
        celda.fill = fill_row


def crear_estilos_pdf() -> dict[str, ParagraphStyle]:
    """Devuelve estilos tipográficos compartidos para reportes PDF de servicio."""
    estilos = getSampleStyleSheet()
    td = ParagraphStyle("TD", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#1e293b"))
    td_center = ParagraphStyle("TDC", parent=td, alignment=1)
    return {
        "titulo": ParagraphStyle("Titulo", parent=estilos["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold"),
        "sub": ParagraphStyle("Sub", parent=estilos["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#64748b")),
        "th": ParagraphStyle("TH", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.white, fontName="Helvetica-Bold", alignment=1),
        "td": td,
        "td_center": td_center,
        "td_right": ParagraphStyle("TDR", parent=td, alignment=2),
        "agotado": ParagraphStyle("Agotado", parent=td_center, textColor=colors.HexColor("#dc2626"), fontName="Helvetica-Bold"),
        "critico": ParagraphStyle("Critico", parent=td_center, textColor=colors.HexColor("#d97706"), fontName="Helvetica-Bold"),
    }


def construir_tabla_zebra(filas_pdf: list[list[Any]], col_widths: list[float]) -> Table:
    """Construye una `Table` con encabezado oscuro y filas cebreadas."""
    tabla = Table(filas_pdf, colWidths=col_widths, repeatRows=1)
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for r_idx in range(1, len(filas_pdf)):
        if r_idx % 2 == 0:
            t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#f8fafc")))
    tabla.setStyle(TableStyle(t_style))
    return tabla


def compilar_pdf_reporte(
    ruta_salida: Path,
    titulo_doc: str,
    subtitulo_html: str,
    titulo_canvas: str,
    fecha_legible: str,
    cuerpo_extra: list[Any],
    st: dict[str, ParagraphStyle],
) -> Path:
    """Compila el documento PDF completo aplicando márgenes y pie de página numerado."""
    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )
    elementos: list[Any] = [
        Paragraph(titulo_doc, st["titulo"]),
        Paragraph(subtitulo_html, st["sub"]),
        Spacer(1, 0.4 * cm),
        *cuerpo_extra,
    ]

    def _make_canvas(*args, **kwargs):
        c = _ReporteNumberedCanvas(*args, **kwargs)
        c.titulo_reporte = titulo_canvas
        c.fecha_emision = fecha_legible
        return c

    doc.build(elementos, canvasmaker=_make_canvas)
    return ruta_salida
