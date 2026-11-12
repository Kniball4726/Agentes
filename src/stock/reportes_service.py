"""Servicio centralizado para la generación de reportes operativos, de inventario y despacho en PDF y Excel."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Sequence

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
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

        texto_izq = f"{self.titulo_reporte} · Emitido: {self.fecha_emision}"
        self.drawString(1.2 * cm, 0.8 * cm, texto_izq)

        texto_der = f"Página {self._pageNumber} de {total_paginas}"
        self.drawRightString(A4[0] - 1.2 * cm, 0.8 * cm, texto_der)
        self.restoreState()


# --- Estilos Globales Excel ---
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


def _autoajustar_columnas_excel(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)


# =========================================================================
# 1. REPORTE DE STOCK CRÍTICO Y REPOSICIÓN
# =========================================================================

def generar_reporte_stock_critico(
    product_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Sistema",
) -> Path:
    """Genera informe de productos agotados o por debajo del stock mínimo."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = datetime.now()
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    fecha_legible = dt.strftime("%d/%m/%Y %H:%M")

    # Extraer análisis de reposición
    try:
        items = product_store.get_replenishment_analysis(solo_criticos=True)
    except Exception:
        # Fallback a list_products filtrando stock <= 0
        items = []
        try:
            prods = product_store.list_products()
            for p in prods:
                stk = int(p["stock"]) if hasattr(p, "keys") else int(getattr(p, "stock", 0))
                min_stk = int(p["min_stock"]) if "min_stock" in p.keys() else 10
                if stk <= min_stk:
                    items.append({
                        "code": p["code"],
                        "name": p["name"],
                        "stock": stk,
                        "min_stock": min_stk,
                        "target_stock": min_stk * 2,
                        "suggested_order": max((min_stk * 2) - stk, 0),
                        "status": "CRITICAL" if stk > 0 else "OUT_OF_STOCK",
                        "ubicacion": p["ubicacion"] if "ubicacion" in p.keys() else "",
                    })
        except Exception:
            items = []

    if formato.lower() == "excel" or formato.lower() == "xlsx":
        ruta_salida = carpeta_destino / f"Reporte_Stock_Critico_{stamp}.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Stock Crítico"

        # Encabezado informativo
        ws.append(["STOCKAGENT · REPORTE DE STOCK CRÍTICO Y REPOSICIÓN"])
        ws.cell(1, 1).font = Font(name="Calibri", size=14, bold=True, color="1E293B")
        ws.append([f"Fecha de emisión: {fecha_legible} | Generado por: {usuario} | Total productos en alerta: {len(items)}"])
        ws.append([])

        # Cabeceras
        headers = ["Código", "Descripción del Producto", "Ubicación", "Stock Actual", "Stock Mínimo", "Sugerido Reponer", "Estado"]
        ws.append(headers)
        row_h = 4
        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(row_h, c_idx)
            cell.fill = _FILL_HEADER
            cell.font = _FONT_HEADER
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Filas
        for idx, it in enumerate(items, start=5):
            stk = int(it.get("stock", 0))
            estado = "AGOTADO" if stk <= 0 else "CRÍTICO"
            fill_actual = _FILL_ZEBRA if idx % 2 == 0 else _FILL_WHITE

            fila = [
                it.get("code", ""),
                it.get("name", ""),
                it.get("ubicacion", "") or "-",
                stk,
                int(it.get("min_stock", 0)),
                int(it.get("suggested_order", 0)),
                estado,
            ]
            ws.append(fila)
            for c_idx in range(1, len(fila) + 1):
                c = ws.cell(idx, c_idx)
                c.fill = fill_actual
                c.font = _FONT_BODY
                c.border = _BORDER_THIN
                if c_idx in (4, 5, 6):
                    c.alignment = Alignment(horizontal="right")
                elif c_idx == 7:
                    c.alignment = Alignment(horizontal="center")
                    c.font = Font(name="Calibri", size=10, bold=True, color="DC2626" if estado == "AGOTADO" else "D97706")

        _autoajustar_columnas_excel(ws)
        wb.save(str(ruta_salida))
        return ruta_salida

    # Formato PDF (ReportLab)
    ruta_salida = carpeta_destino / f"Reporte_Stock_Critico_{stamp}.pdf"
    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("Titulo", parent=estilos["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold")
    estilo_sub = ParagraphStyle("Sub", parent=estilos["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#64748b"))
    estilo_th = ParagraphStyle("TH", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.white, fontName="Helvetica-Bold", alignment=1)
    estilo_td = ParagraphStyle("TD", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#1e293b"))
    estilo_td_center = ParagraphStyle("TDC", parent=estilo_td, alignment=1)
    estilo_td_right = ParagraphStyle("TDR", parent=estilo_td, alignment=2)
    estilo_agotado = ParagraphStyle("Agotado", parent=estilo_td_center, textColor=colors.HexColor("#dc2626"), fontName="Helvetica-Bold")
    estilo_critico = ParagraphStyle("Critico", parent=estilo_td_center, textColor=colors.HexColor("#d97706"), fontName="Helvetica-Bold")

    elementos: list[Any] = []

    # Cabecera
    elementos.append(Paragraph("StockAgent · Reporte de Stock Crítico y Reposición", estilo_titulo))
    elementos.append(Paragraph(f"Emitido el {fecha_legible} · Generado por: <b>{escape(usuario)}</b>", estilo_sub))
    elementos.append(Spacer(1, 0.4 * cm))

    # Resumen en pastillas
    agotados_cnt = sum(1 for it in items if int(it.get("stock", 0)) <= 0)
    criticos_cnt = len(items) - agotados_cnt
    resumen_data = [
        [
            Paragraph(f"<b>Total en Alerta:</b> {len(items)}", estilo_td_center),
            Paragraph(f"<b>Agotados (Stock 0):</b> {agotados_cnt}", estilo_agotado),
            Paragraph(f"<b>Bajo Mínimo:</b> {criticos_cnt}", estilo_critico),
        ]
    ]
    t_resumen = Table(resumen_data, colWidths=[6 * cm, 6 * cm, 6 * cm])
    t_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(t_resumen)
    elementos.append(Spacer(1, 0.5 * cm))

    # Tabla de productos
    col_widths = [2.2 * cm, 6.8 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 1.8 * cm]
    headers_pdf = [
        Paragraph("Código", estilo_th),
        Paragraph("Descripción", estilo_th),
        Paragraph("Ubicación", estilo_th),
        Paragraph("Actual", estilo_th),
        Paragraph("Mínimo", estilo_th),
        Paragraph("Sugerido", estilo_th),
        Paragraph("Estado", estilo_th),
    ]
    filas_pdf = [headers_pdf]

    if not items:
        filas_pdf.append([
            Paragraph("No hay productos en quiebre ni bajo stock crítico.", estilo_td_center),
            "", "", "", "", "", ""
        ])
    else:
        for it in items:
            stk = int(it.get("stock", 0))
            is_agotado = stk <= 0
            filas_pdf.append([
                Paragraph(escape(str(it.get("code", ""))), estilo_td_center),
                Paragraph(escape(str(it.get("name", ""))), estilo_td),
                Paragraph(escape(str(it.get("ubicacion", "") or "-")), estilo_td_center),
                Paragraph(str(stk), estilo_td_right),
                Paragraph(str(it.get("min_stock", 0)), estilo_td_right),
                Paragraph(str(it.get("suggested_order", 0)), estilo_td_right),
                Paragraph("AGOTADO" if is_agotado else "CRÍTICO", estilo_agotado if is_agotado else estilo_critico),
            ])

    t_prod = Table(filas_pdf, colWidths=col_widths, repeatRows=1)
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
    t_prod.setStyle(TableStyle(t_style))
    elementos.append(t_prod)

    def _make_canvas(*args, **kwargs):
        c = _ReporteNumberedCanvas(*args, **kwargs)
        c.titulo_reporte = "StockAgent · Reporte de Stock Crítico"
        c.fecha_emision = fecha_legible
        return c

    doc.build(elementos, canvasmaker=_make_canvas)
    return ruta_salida


# =========================================================================
# 2. REPORTE DE CATÁLOGO COMPLETO E INVENTARIO
# =========================================================================

def generar_reporte_catalogo_stock(
    product_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Sistema",
) -> Path:
    """Genera inventario general con existencias, código de barras y ubicaciones."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = datetime.now()
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    fecha_legible = dt.strftime("%d/%m/%Y %H:%M")

    try:
        prods = product_store.list_products()
    except Exception:
        prods = []

    if formato.lower() in ("excel", "xlsx"):
        ruta_salida = carpeta_destino / f"Reporte_Catalogo_Inventario_{stamp}.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Catálogo Stock"

        ws.append(["STOCKAGENT · INVENTARIO Y CATÁLOGO DE PRODUCTOS"])
        ws.cell(1, 1).font = Font(name="Calibri", size=14, bold=True, color="1E293B")
        ws.append([f"Fecha de emisión: {fecha_legible} | Generado por: {usuario} | Total referencias: {len(prods)}"])
        ws.append([])

        headers = ["Código", "Descripción", "Código de Barras", "Ubicación", "Stock Actual", "Estado"]
        ws.append(headers)
        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(4, c_idx)
            cell.fill = _FILL_HEADER
            cell.font = _FONT_HEADER
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for idx, p in enumerate(prods, start=5):
            fill_actual = _FILL_ZEBRA if idx % 2 == 0 else _FILL_WHITE
            cod = p["code"] if hasattr(p, "keys") else getattr(p, "code", "")
            nom = p["name"] if hasattr(p, "keys") else getattr(p, "name", "")
            keys_p = set(p.keys()) if hasattr(p, "keys") else set()
            bar = (p["cod_barras"] if "cod_barras" in keys_p and p["cod_barras"] else "") or (
                p["barcode"] if "barcode" in keys_p else ""
            )
            ubi = p["ubicacion"] if "ubicacion" in p.keys() else ""
            stk = int(p["stock"]) if hasattr(p, "keys") else int(getattr(p, "stock", 0))
            act = bool(p["active"]) if "active" in p.keys() else True

            ws.append([cod, nom, bar or "-", ubi or "-", stk, "Activo" if act else "Inactivo"])
            for c_idx in range(1, 7):
                c = ws.cell(idx, c_idx)
                c.fill = fill_actual
                c.font = _FONT_BODY
                c.border = _BORDER_THIN
                if c_idx == 5:
                    c.alignment = Alignment(horizontal="right")
                    c.font = _FONT_BOLD
                elif c_idx in (1, 3, 4, 6):
                    c.alignment = Alignment(horizontal="center")

        _autoajustar_columnas_excel(ws)
        wb.save(str(ruta_salida))
        return ruta_salida

    # PDF
    ruta_salida = carpeta_destino / f"Reporte_Catalogo_Inventario_{stamp}.pdf"
    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("Titulo", parent=estilos["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold")
    estilo_sub = ParagraphStyle("Sub", parent=estilos["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#64748b"))
    estilo_th = ParagraphStyle("TH", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.white, fontName="Helvetica-Bold", alignment=1)
    estilo_td = ParagraphStyle("TD", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#1e293b"))
    estilo_td_center = ParagraphStyle("TDC", parent=estilo_td, alignment=1)
    estilo_td_right = ParagraphStyle("TDR", parent=estilo_td, alignment=2)

    elementos: list[Any] = []
    elementos.append(Paragraph("StockAgent · Catálogo Completo de Inventario", estilo_titulo))
    elementos.append(Paragraph(f"Emitido el {fecha_legible} · Total referencias: <b>{len(prods)}</b> · Operador: <b>{escape(usuario)}</b>", estilo_sub))
    elementos.append(Spacer(1, 0.4 * cm))

    col_widths = [2.2 * cm, 8.0 * cm, 3.2 * cm, 2.4 * cm, 2.6 * cm]
    headers_pdf = [
        Paragraph("Código", estilo_th),
        Paragraph("Descripción", estilo_th),
        Paragraph("Cód. Barras", estilo_th),
        Paragraph("Ubicación", estilo_th),
        Paragraph("Stock", estilo_th),
    ]
    filas_pdf = [headers_pdf]

    for p in prods:
        cod = p["code"] if hasattr(p, "keys") else getattr(p, "code", "")
        nom = p["name"] if hasattr(p, "keys") else getattr(p, "name", "")
        keys_p = set(p.keys()) if hasattr(p, "keys") else set()
        bar = (p["cod_barras"] if "cod_barras" in keys_p and p["cod_barras"] else "") or (
            p["barcode"] if "barcode" in keys_p else ""
        )
        ubi = p["ubicacion"] if "ubicacion" in p.keys() else ""
        stk = int(p["stock"]) if hasattr(p, "keys") else int(getattr(p, "stock", 0))

        filas_pdf.append([
            Paragraph(escape(str(cod)), estilo_td_center),
            Paragraph(escape(str(nom)), estilo_td),
            Paragraph(escape(str(bar or "-")), estilo_td_center),
            Paragraph(escape(str(ubi or "-")), estilo_td_center),
            Paragraph(str(stk), estilo_td_right),
        ])

    t_prod = Table(filas_pdf, colWidths=col_widths, repeatRows=1)
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
    t_prod.setStyle(TableStyle(t_style))
    elementos.append(t_prod)

    def _make_canvas(*args, **kwargs):
        c = _ReporteNumberedCanvas(*args, **kwargs)
        c.titulo_reporte = "StockAgent · Catálogo e Inventario"
        c.fecha_emision = fecha_legible
        return c

    doc.build(elementos, canvasmaker=_make_canvas)
    return ruta_salida


# =========================================================================
# 3. REPORTE DE DESPACHO Y PEDIDOS POR LOGÍSTICA / CLIENTE
# =========================================================================

def generar_reporte_pedidos_despacho(
    order_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Sistema",
    filtro_transporte: str | None = None,
    limite: int = 500,
) -> Path:
    """Genera informe consolidado de despachos y pedidos procesados."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = datetime.now()
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    fecha_legible = dt.strftime("%d/%m/%Y %H:%M")

    try:
        pedidos = order_store.listar_pedidos(limit=limite)
    except Exception:
        pedidos = []

    if filtro_transporte and filtro_transporte.strip():
        filtro_norm = filtro_transporte.strip().lower()
        pedidos = [p for p in pedidos if (getattr(p, "logistica", "") or "").strip().lower() == filtro_norm]

    total_pedidos = len(pedidos)
    total_bultos = sum(int(getattr(p, "bultos", 0) or 0) for p in pedidos)

    if formato.lower() in ("excel", "xlsx"):
        ruta_salida = carpeta_destino / f"Reporte_Despacho_Pedidos_{stamp}.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Despacho Pedidos"

        ws.append(["STOCKAGENT · REPORTE CONSOLIDADO DE DESPACHO Y PEDIDOS"])
        ws.cell(1, 1).font = Font(name="Calibri", size=14, bold=True, color="1E293B")
        ws.append([f"Fecha de emisión: {fecha_legible} | Generado por: {usuario} | Total pedidos: {total_pedidos} | Total bultos: {total_bultos}"])
        ws.append([])

        headers = ["Nota de Pedido", "Cliente", "Transporte / Logística", "Bultos", "Armador", "Estado", "Fecha"]
        ws.append(headers)
        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(4, c_idx)
            cell.fill = _FILL_HEADER
            cell.font = _FONT_HEADER
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for idx, p in enumerate(pedidos, start=5):
            fill_actual = _FILL_ZEBRA if idx % 2 == 0 else _FILL_WHITE
            f_str = str(getattr(p, "created_at", "") or getattr(p, "fecha", ""))[:16]
            ws.append([
                getattr(p, "nota_pedido", ""),
                getattr(p, "cliente", "") or "-",
                getattr(p, "logistica", "") or "-",
                int(getattr(p, "bultos", 0) or 0),
                getattr(p, "armador", "") or "-",
                getattr(p, "estado_despacho", "") or "-",
                f_str,
            ])
            for c_idx in range(1, 8):
                c = ws.cell(idx, c_idx)
                c.fill = fill_actual
                c.font = _FONT_BODY
                c.border = _BORDER_THIN
                if c_idx == 4:
                    c.alignment = Alignment(horizontal="right")
                    c.font = _FONT_BOLD
                elif c_idx in (1, 3, 5, 6, 7):
                    c.alignment = Alignment(horizontal="center")

        _autoajustar_columnas_excel(ws)
        wb.save(str(ruta_salida))
        return ruta_salida

    # PDF
    ruta_salida = carpeta_destino / f"Reporte_Despacho_Pedidos_{stamp}.pdf"
    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("Titulo", parent=estilos["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold")
    estilo_sub = ParagraphStyle("Sub", parent=estilos["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#64748b"))
    estilo_th = ParagraphStyle("TH", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.white, fontName="Helvetica-Bold", alignment=1)
    estilo_td = ParagraphStyle("TD", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#1e293b"))
    estilo_td_center = ParagraphStyle("TDC", parent=estilo_td, alignment=1)
    estilo_td_right = ParagraphStyle("TDR", parent=estilo_td, alignment=2)

    elementos: list[Any] = []
    elementos.append(Paragraph("StockAgent · Reporte Consolidado de Despacho", estilo_titulo))
    elementos.append(Paragraph(f"Emitido el {fecha_legible} · Total Pedidos: <b>{total_pedidos}</b> · Total Bultos: <b>{total_bultos}</b>", estilo_sub))
    elementos.append(Spacer(1, 0.4 * cm))

    col_widths = [2.6 * cm, 5.4 * cm, 3.2 * cm, 1.6 * cm, 2.6 * cm, 3.0 * cm]
    headers_pdf = [
        Paragraph("Remito / NP", estilo_th),
        Paragraph("Cliente", estilo_th),
        Paragraph("Transporte", estilo_th),
        Paragraph("Bultos", estilo_th),
        Paragraph("Armador", estilo_th),
        Paragraph("Fecha", estilo_th),
    ]
    filas_pdf = [headers_pdf]

    for p in pedidos:
        f_str = str(getattr(p, "created_at", "") or getattr(p, "fecha", ""))[:16]
        filas_pdf.append([
            Paragraph(escape(str(getattr(p, "nota_pedido", ""))), estilo_td_center),
            Paragraph(escape(str(getattr(p, "cliente", "") or "-")), estilo_td),
            Paragraph(escape(str(getattr(p, "logistica", "") or "-")), estilo_td_center),
            Paragraph(str(getattr(p, "bultos", 0) or 0), estilo_td_right),
            Paragraph(escape(str(getattr(p, "armador", "") or "-")), estilo_td_center),
            Paragraph(f_str, estilo_td_center),
        ])

    t_ped = Table(filas_pdf, colWidths=col_widths, repeatRows=1)
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
    t_ped.setStyle(TableStyle(t_style))
    elementos.append(t_ped)

    def _make_canvas(*args, **kwargs):
        c = _ReporteNumberedCanvas(*args, **kwargs)
        c.titulo_reporte = "StockAgent · Reporte de Despacho"
        c.fecha_emision = fecha_legible
        return c

    doc.build(elementos, canvasmaker=_make_canvas)
    return ruta_salida


# =========================================================================
# 4. REPORTE DE AUDITORÍA Y CIERRES DE JORNADA
# =========================================================================

def generar_reporte_cierres_historicos(
    order_store: Any,
    carpeta_destino: Path,
    formato: str = "pdf",
    usuario: str = "Sistema",
    limite: int = 100,
) -> Path:
    """Genera informe consolidado de todos los cierres de jornada ejecutados."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = datetime.now()
    stamp = dt.strftime("%Y%m%d_%H%M%S")
    fecha_legible = dt.strftime("%d/%m/%Y %H:%M")

    try:
        cierres = order_store.listar_cierres(limit=limite)
    except Exception:
        cierres = []

    if formato.lower() in ("excel", "xlsx"):
        ruta_salida = carpeta_destino / f"Reporte_Cierres_Jornada_{stamp}.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cierres Históricos"

        ws.append(["STOCKAGENT · HISTORIAL DE CIERRES DE JORNADA"])
        ws.cell(1, 1).font = Font(name="Calibri", size=14, bold=True, color="1E293B")
        ws.append([f"Fecha de emisión: {fecha_legible} | Generado por: {usuario} | Total cierres auditados: {len(cierres)}"])
        ws.append([])

        headers = ["Cierre #", "Fecha y Hora", "Total Pedidos", "Total Bultos", "Operador Responsable", "Archivo Informe"]
        ws.append(headers)
        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(4, c_idx)
            cell.fill = _FILL_HEADER
            cell.font = _FONT_HEADER
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for idx, c in enumerate(cierres, start=5):
            fill_actual = _FILL_ZEBRA if idx % 2 == 0 else _FILL_WHITE
            f_cie = str(getattr(c, "created_at", "") or getattr(c, "fecha_hora", ""))[:19]
            cant_ped = int(getattr(c, "cantidad_pedidos", 0) or getattr(c, "total_pedidos", 0) or 0)
            art_tot = int(getattr(c, "articulos_totales", 0) or getattr(c, "total_bultos", 0) or 0)
            op = getattr(c, "usuario", "") or getattr(c, "operador", "") or "-"
            arch = getattr(c, "archivo_pdf", "") or getattr(c, "archivo_informe", "") or "-"
            ws.append([
                getattr(c, "id", idx),
                f_cie,
                cant_ped,
                art_tot,
                op,
                arch,
            ])
            for c_idx in range(1, 7):
                cell_c = ws.cell(idx, c_idx)
                cell_c.fill = fill_actual
                cell_c.font = _FONT_BODY
                cell_c.border = _BORDER_THIN
                if c_idx in (3, 4):
                    cell_c.alignment = Alignment(horizontal="right")
                elif c_idx in (1, 2, 5):
                    cell_c.alignment = Alignment(horizontal="center")

        _autoajustar_columnas_excel(ws)
        wb.save(str(ruta_salida))
        return ruta_salida

    # PDF
    ruta_salida = carpeta_destino / f"Reporte_Cierres_Jornada_{stamp}.pdf"
    doc = SimpleDocTemplate(
        str(ruta_salida),
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("Titulo", parent=estilos["Heading1"], fontSize=18, leading=22, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold")
    estilo_sub = ParagraphStyle("Sub", parent=estilos["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#64748b"))
    estilo_th = ParagraphStyle("TH", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.white, fontName="Helvetica-Bold", alignment=1)
    estilo_td = ParagraphStyle("TD", parent=estilos["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#1e293b"))
    estilo_td_center = ParagraphStyle("TDC", parent=estilo_td, alignment=1)
    estilo_td_right = ParagraphStyle("TDR", parent=estilo_td, alignment=2)

    elementos: list[Any] = []
    elementos.append(Paragraph("StockAgent · Historial de Cierres de Jornada", estilo_titulo))
    elementos.append(Paragraph(f"Emitido el {fecha_legible} · Total cierres registrados: <b>{len(cierres)}</b>", estilo_sub))
    elementos.append(Spacer(1, 0.4 * cm))

    col_widths = [2.0 * cm, 4.4 * cm, 2.6 * cm, 2.6 * cm, 6.8 * cm]
    headers_pdf = [
        Paragraph("Cierre #", estilo_th),
        Paragraph("Fecha y Hora", estilo_th),
        Paragraph("Pedidos", estilo_th),
        Paragraph("Bultos", estilo_th),
        Paragraph("Operador / Archivo", estilo_th),
    ]
    filas_pdf = [headers_pdf]

    for c in cierres:
        f_cie = str(getattr(c, "created_at", "") or getattr(c, "fecha_hora", ""))[:19]
        cant_ped = str(getattr(c, "cantidad_pedidos", 0) or getattr(c, "total_pedidos", 0) or 0)
        art_tot = str(getattr(c, "articulos_totales", 0) or getattr(c, "total_bultos", 0) or 0)
        op = getattr(c, "usuario", "") or getattr(c, "operador", "") or "-"
        arch = getattr(c, "archivo_pdf", "") or getattr(c, "archivo_informe", "") or "-"
        filas_pdf.append([
            Paragraph(f"#{getattr(c, 'id', '')}", estilo_td_center),
            Paragraph(f_cie, estilo_td_center),
            Paragraph(cant_ped, estilo_td_right),
            Paragraph(art_tot, estilo_td_right),
            Paragraph(f"<b>{escape(str(op))}</b><br/>{escape(str(arch))}", estilo_td),
        ])

    t_cie = Table(filas_pdf, colWidths=col_widths, repeatRows=1)
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
    t_cie.setStyle(TableStyle(t_style))
    elementos.append(t_cie)

    def _make_canvas(*args, **kwargs):
        c = _ReporteNumberedCanvas(*args, **kwargs)
        c.titulo_reporte = "StockAgent · Cierres de Jornada"
        c.fecha_emision = fecha_legible
        return c

    doc.build(elementos, canvasmaker=_make_canvas)
    return ruta_salida
