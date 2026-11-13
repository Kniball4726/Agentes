"""Generación de rótulos continuos para impresoras térmicas (Zebra, Xprinter, 100x150 mm)."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .utils import _crear_qr_drawing, _formatear_cliente_etiqueta

if TYPE_CHECKING:
    from src.orders_store import Pedido


def _construir_elementos_etiqueta_termica(
    pedido: Pedido,
    bulto_idx: int,
    total_bultos: int,
    f_ret: str,
    ancho_util: float,
    styles,
) -> list:
    """Construye los flowables ReportLab para una etiqueta térmica individual."""
    estilo_hdr_izq = ParagraphStyle(f"Term_HdrI_{bulto_idx}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=colors.HexColor("#dc2626"))
    estilo_hdr_der = ParagraphStyle(f"Term_HdrD_{bulto_idx}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, alignment=2, textColor=colors.HexColor("#0f172a"))
    t_header = Table(
        [[Paragraph("RÓTULO DE DESPACHO", estilo_hdr_izq), Paragraph(f"Remito: <b>{escape(pedido.nota_pedido)}</b>", estilo_hdr_der)]],
        colWidths=[ancho_util * 0.5, ancho_util * 0.5],
    )
    t_header.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))

    cli_txt = _formatear_cliente_etiqueta(pedido)
    estilo_cli_lbl = ParagraphStyle(f"Term_CliLbl_{bulto_idx}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, alignment=1, textColor=colors.HexColor("#64748b"))
    estilo_cli_val = ParagraphStyle(f"Term_CliVal_{bulto_idx}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=1, textColor=colors.HexColor("#0f172a"))
    t_cliente = Table([[Paragraph("DESTINATARIO / CLIENTE", estilo_cli_lbl)], [Paragraph(escape(cli_txt), estilo_cli_val)]], colWidths=[ancho_util])
    t_cliente.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor("#94a3b8")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    estilo_bulto_txt = ParagraphStyle(f"Term_BultoTxt_{bulto_idx}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=20, leading=23, alignment=1, textColor=colors.white)
    t_bulto = Table([[Paragraph(f"BULTO {bulto_idx} DE {total_bultos}", estilo_bulto_txt)]], colWidths=[ancho_util])
    t_bulto.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dc2626")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))

    n_guia = getattr(pedido, "numero_guia", "") or ""
    guia_txt = f"<br/><b>N° DE GUÍA / TRACKING:</b> <font color='#dc2626'>{escape(n_guia)}</font>" if n_guia else ""
    info_logistica_txt = (
        f"<b>TRANSPORTE / VÍA:</b> {escape(pedido.logistica)}<br/>"
        f"<b>ARMADOR:</b> {escape(pedido.armador)}  |  <b>FECHA:</b> {f_ret}{guia_txt}"
    )
    estilo_log_info = ParagraphStyle(f"Term_LogInfo_{bulto_idx}", parent=styles["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#1e293b"))
    t_info = Table([[Paragraph(info_logistica_txt, estilo_log_info)]], colWidths=[ancho_util])
    t_info.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))

    guia_part = f"|GUIA:{n_guia}" if n_guia else ""
    qr_payload = (
        f"REMITO:{pedido.nota_pedido}|CLIENTE:{cli_txt}|BULTO:{bulto_idx}/{total_bultos}|"
        f"LOGISTICA:{pedido.logistica}{guia_part}"
    )
    estilo_pie_qr = ParagraphStyle(f"Term_PieQR_{bulto_idx}", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=9, alignment=1, textColor=colors.HexColor("#64748b"))
    t_qr = Table(
        [[_crear_qr_drawing(qr_payload, tamano_cm=3.6)], [Paragraph("Escaneá con la app para control de despacho en depósito", estilo_pie_qr)]],
        colWidths=[ancho_util],
    )
    t_qr.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))

    return [t_header, Spacer(1, 0.25 * cm), t_cliente, Spacer(1, 0.25 * cm), t_bulto, Spacer(1, 0.25 * cm), t_info, Spacer(1, 0.25 * cm), t_qr]


def generar_etiquetas_termicas_pdf(
    pedido: Pedido,
    carpeta_destino: Path | None = None,
    tamano_mm: tuple[float, float] = (100.0, 150.0),
    fecha_hora: datetime | None = None,
) -> Path:
    """Genera rótulos de despacho en formato continuo para impresoras térmicas."""
    if carpeta_destino is None:
        raiz = Path(__file__).resolve().parent.parent.parent
        carpeta_destino = raiz / "Descuentos" / "Rotulos"
    carpeta_destino.mkdir(parents=True, exist_ok=True)

    dt = fecha_hora or datetime.now()
    fecha_emision = dt.strftime("%d/%m/%Y")
    f_ret = pedido.fecha_retiro.strip() if getattr(pedido, "fecha_retiro", "") else fecha_emision
    nota_segura = "".join(c for c in pedido.nota_pedido if c.isalnum() or c in ("-", "_")).strip()
    ruta_pdf = carpeta_destino / f"Rotulo_Termico_{nota_segura}.pdf"

    ancho_pt = (tamano_mm[0] / 10.0) * cm
    alto_pt = (tamano_mm[1] / 10.0) * cm
    margen_pt = 0.4 * cm
    ancho_util = ancho_pt - (margen_pt * 2)

    styles = getSampleStyleSheet()
    total_bultos = max(1, int(pedido.bultos))
    story: list = []

    for bulto_idx in range(1, total_bultos + 1):
        story.extend(_construir_elementos_etiqueta_termica(pedido, bulto_idx, total_bultos, f_ret, ancho_util, styles))
        if bulto_idx < total_bultos:
            story.append(PageBreak())

    doc = SimpleDocTemplate(
        str(ruta_pdf),
        pagesize=(ancho_pt, alto_pt),
        leftMargin=margen_pt,
        rightMargin=margen_pt,
        topMargin=margen_pt,
        bottomMargin=margen_pt,
    )
    doc.build(story)
    return ruta_pdf
