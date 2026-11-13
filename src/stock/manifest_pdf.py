"""Generación de Hoja de Ruta y Manifiesto de Despacho por Transporte (PDF)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

if TYPE_CHECKING:
    from src.orders_store import Pedido


class _NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para imprimir el número total de páginas en cada hoja."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []
        self.cierre_id: int = 0
        self.fecha_doc: str = ""

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total_paginas = len(self._saved_page_states)
        for estado in self._saved_page_states:
            self.__dict__.update(estado)
            self.dibujar_pie(total_paginas)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def dibujar_pie(self, total_paginas: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(1.2 * cm, 1.3 * cm, A4[0] - 1.2 * cm, 1.3 * cm)
        self.drawString(1.2 * cm, 0.85 * cm, f"Manifiesto de Despacho · Cierre #{self.cierre_id} · Emitido: {self.fecha_doc}")
        self.drawRightString(A4[0] - 1.2 * cm, 0.85 * cm, f"Página {self._pageNumber} de {total_paginas}")
        self.restoreState()


def _crear_estilos_manifiesto() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    td = ParagraphStyle("TableCell", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=colors.HexColor("#1e293b"))
    return {
        "titulo": ParagraphStyle("TituloManifiesto", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=colors.HexColor("#0f172a")),
        "subtitulo": ParagraphStyle("SubtituloManifiesto", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#475569")),
        "meta_clave": ParagraphStyle("MetaClave", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#1e293b")),
        "meta_valor": ParagraphStyle("MetaValor", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#334155")),
        "seccion": ParagraphStyle("SeccionLogistica", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=colors.white),
        "th": ParagraphStyle("TableHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9.5, textColor=colors.white, alignment=1),
        "td": td,
        "td_center": ParagraphStyle("TableCellCenter", parent=td, alignment=1),
        "subtotal": ParagraphStyle("SubtotalText", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#0f172a"), alignment=2),
        "firma": ParagraphStyle("FirmaText", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=colors.HexColor("#334155")),
    }


def _construir_bloque_logistica(
    logistica_nombre: str,
    peds: list[Pedido],
    ancho_util: float,
    st: dict[str, ParagraphStyle],
) -> list[Any]:
    """Construye la sección de pedidos agrupados para un transporte con cuadro de firma chofer."""
    bultos_log = sum(p.bultos for p in peds)
    t_tit_log = Table(
        [[
            Paragraph(f"LOGÍSTICA / TRANSPORTE: {escape(logistica_nombre.upper())}", st["seccion"]),
            Paragraph(
                f"<b>{len(peds)} pedidos</b>  |  <b>{bultos_log} bultos totales</b>",
                ParagraphStyle("Badge", parent=st["seccion"], alignment=2),
            ),
        ]],
        colWidths=[ancho_util * 0.65, ancho_util * 0.35],
    )
    t_tit_log.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1e293b")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    col_w = [0.8 * cm, 3.5 * cm, 4.8 * cm, 1.5 * cm, 2.4 * cm, 2.4 * cm, 3.2 * cm]
    filas_tabla = [[
        Paragraph(h, st["th"])
        for h in ("<b>#</b>", "<b>Remito / Factura</b>", "<b>Cliente</b>", "<b>Bultos</b>", "<b>Fecha Retiro</b>", "<b>Armador</b>", "<b>Firma / Recepción Chofer</b>")
    ]]
    for idx, ped in enumerate(peds, start=1):
        f_retiro = ped.fecha_retiro.strip() if ped.fecha_retiro else "Inmediato"
        remito_base = escape(ped.nota_pedido.strip())
        n_guia = getattr(ped, "numero_guia", "") or ""
        remito_txt = (
            f"<b>{remito_base}</b><br/><font size=6 color='#64748b'>Guía: {escape(n_guia.strip())}</font>"
            if n_guia
            else f"<b>{remito_base}</b>"
        )
        filas_tabla.append([
            Paragraph(str(idx), st["td_center"]),
            Paragraph(remito_txt, st["td"]),
            Paragraph(escape(ped.cliente.strip()), st["td"]),
            Paragraph(f"<b>{ped.bultos}</b>", st["td_center"]),
            Paragraph(escape(f_retiro), st["td_center"]),
            Paragraph(escape(ped.armador.strip()), st["td"]),
            Paragraph("", st["td"]),
        ])

    filas_tabla.append([
        Paragraph(f"<b>SUBTOTAL {escape(logistica_nombre.upper())}:</b>", st["subtotal"]),
        "", "", Paragraph(f"<b>{bultos_log}</b>", st["td_center"]), "", "", "",
    ])

    t_pedidos = Table(filas_tabla, colWidths=col_w, repeatRows=1)
    estilo_t = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (0, -1), (2, -1)),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
        ("BOX", (0, -1), (-1, -1), 1, colors.HexColor("#94a3b8")),
    ]
    for idx in range(1, len(filas_tabla) - 1):
        if idx % 2 == 0:
            estilo_t.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#f8fafc")))
    t_pedidos.setStyle(TableStyle(estilo_t))

    t_firma = Table(
        [[
            Paragraph("<b>Transporte / Chofer:</b> ___________________________", st["firma"]),
            Paragraph("<b>DNI:</b> ___________________", st["firma"]),
            Paragraph("<b>Patente:</b> ___________", st["firma"]),
            Paragraph("<b>Firma Chofer:</b> ___________________", st["firma"]),
        ]],
        colWidths=[ancho_util * 0.38, ancho_util * 0.20, ancho_util * 0.16, ancho_util * 0.26],
    )
    t_firma.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    return [KeepTogether([t_tit_log, t_pedidos]), t_firma, Spacer(1, 0.45 * cm)]


def _construir_cierre_deposito(
    grupos_logistica: dict[str, list[Pedido]],
    logistica_orden: list[str],
    total_pedidos: int,
    total_bultos: int,
    usuario: str,
    ancho_util: float,
    st: dict[str, ParagraphStyle],
) -> KeepTogether:
    """Construye la tabla final de resumen consolidado y conformidad de depósito."""
    resumen_filas = [[
        Paragraph("<b>RESUMEN CONSOLIDADO DE DESPACHO POR TRANSPORTE</b>", st["th"]),
        Paragraph("<b>CANT. PEDIDOS</b>", st["th"]),
        Paragraph("<b>TOTAL BULTOS</b>", st["th"]),
    ]]
    for logistica_nombre in logistica_orden:
        p_list = grupos_logistica[logistica_nombre]
        resumen_filas.append([
            Paragraph(f"• {escape(logistica_nombre)}", st["td"]),
            Paragraph(str(len(p_list)), st["td_center"]),
            Paragraph(f"<b>{sum(p.bultos for p in p_list)}</b>", st["td_center"]),
        ])
    resumen_filas.append([
        Paragraph("<b>TOTAL GENERAL DESPACHADO:</b>", st["subtotal"]),
        Paragraph(f"<b>{total_pedidos}</b>", st["td_center"]),
        Paragraph(f"<b>{total_bultos}</b>", st["td_center"]),
    ])

    t_resumen_final = Table(resumen_filas, colWidths=[ancho_util * 0.60, ancho_util * 0.20, ancho_util * 0.20])
    t_resumen_final.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    t_deposito = Table(
        [
            [
                Paragraph("<b>OBSERVACIONES DE DESPACHO:</b>", st["meta_clave"]),
                Paragraph("<b>CONFORMIDAD ENCARGADO DE DEPÓSITO</b>", st["meta_clave"]),
            ],
            [
                Paragraph("Verificar que cada bulto contenga su respectivo rótulo de identificación antes de la entrega al transportista.", st["meta_valor"]),
                Paragraph(f"<br/><br/>________________________________________<br/><b>{escape(usuario)}</b><br/>Firma y Aclaración", st["meta_valor"]),
            ],
        ],
        colWidths=[ancho_util * 0.55, ancho_util * 0.45],
    )
    t_deposito.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    return KeepTogether([Spacer(1, 0.3 * cm), t_resumen_final, Spacer(1, 0.3 * cm), t_deposito])


def generar_hoja_ruta_pdf(
    cierre_id: int,
    pedidos: Sequence[Pedido],
    usuario: str,
    carpeta_destino: Path,
    fecha_hora: datetime | None = None,
    filtro_logistica: str | None = None,
) -> Path:
    """Genera la Hoja de Ruta de Despacho en PDF agrupada por transporte/logística."""
    if filtro_logistica:
        pedidos = [p for p in pedidos if (p.logistica or "").strip().lower() == filtro_logistica.strip().lower()]
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = fecha_hora or datetime.now()
    fecha_formateada = dt.strftime("%d/%m/%Y %H:%M")
    timestamp_archivo = dt.strftime("%Y%m%d_%H%M%S")
    sufijo_log = f"_{filtro_logistica.replace(' ', '_')}" if filtro_logistica else ""
    ruta_pdf = carpeta_destino / f"Hoja_Ruta_Cierre_{cierre_id}{sufijo_log}_{timestamp_archivo}.pdf"

    ancho_util = A4[0] - 2.4 * cm
    st = _crear_estilos_manifiesto()

    total_pedidos = len(pedidos)
    total_bultos = sum(p.bultos for p in pedidos)
    grupos_logistica: dict[str, list[Pedido]] = defaultdict(list)
    for p in pedidos:
        grupos_logistica[(p.logistica or "Sin Logística").strip()].append(p)

    t_encabezado = Table(
        [
            [
                Paragraph("<b>DEPÓSITO CENTRAL · LOGÍSTICA & DESPACHO</b>", st["subtitulo"]),
                Paragraph(f"<b>FECHA:</b> {fecha_formateada}", st["meta_valor"]),
            ],
            [
                Paragraph(f"HOJA DE RUTA Y MANIFIESTO DE DESPACHO · CIERRE #{cierre_id}", st["titulo"]),
                Paragraph(f"<b>RESPONSABLE:</b> {escape(usuario)}", st["meta_valor"]),
            ],
        ],
        colWidths=[ancho_util * 0.70, ancho_util * 0.30],
    )
    t_encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    t_resumen = Table(
        [
            [
                Paragraph("<b>TOTAL PEDIDOS</b>", st["meta_clave"]),
                Paragraph("<b>TOTAL BULTOS</b>", st["meta_clave"]),
                Paragraph("<b>TRANSPORTES / DESTINOS</b>", st["meta_clave"]),
                Paragraph("<b>ESTADO CIERRE</b>", st["meta_clave"]),
            ],
            [
                Paragraph(f"<font size=12><b>{total_pedidos}</b></font>", st["meta_valor"]),
                Paragraph(f"<font size=12 color='#dc2626'><b>{total_bultos}</b></font>", st["meta_valor"]),
                Paragraph(f"<font size=12><b>{len(grupos_logistica)}</b></font>", st["meta_valor"]),
                Paragraph("<font size=10 color='#16a34a'><b>CONSOLIDADO</b></font>", st["meta_valor"]),
            ],
        ],
        colWidths=[ancho_util / 4] * 4,
    )
    t_resumen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story: list[Any] = [t_encabezado, Spacer(1, 0.25 * cm), t_resumen, Spacer(1, 0.4 * cm)]
    logistica_orden = sorted(grupos_logistica.keys())
    for logistica_nombre in logistica_orden:
        story.extend(_construir_bloque_logistica(logistica_nombre, grupos_logistica[logistica_nombre], ancho_util, st))

    story.append(Spacer(1, 0.2 * cm))
    story.append(_construir_cierre_deposito(grupos_logistica, logistica_orden, total_pedidos, total_bultos, usuario, ancho_util, st))

    doc = SimpleDocTemplate(
        str(ruta_pdf),
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.5 * cm,
    )

    def preparar_canvas(canv, _doc) -> None:
        canv.cierre_id = cierre_id
        canv.fecha_doc = fecha_formateada

    doc.build(story, canvasmaker=_NumberedCanvas, onFirstPage=preparar_canvas, onLaterPages=preparar_canvas)
    return ruta_pdf
