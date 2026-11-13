"""Generación de rótulos A4 en grilla 2x5 (10 etiquetas por página) con QR vectorizado."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table, TableStyle

from .utils import (
    ETIQUETAS_POR_HOJA,
    _crear_qr_drawing,
    _formatear_cliente_etiqueta,
    compilar_grilla_a4_pdf,
)

if TYPE_CHECKING:
    from src.orders_store import Pedido


def _construir_tarjeta_etiqueta(
    pedido: Pedido,
    bulto_idx: int,
    total_bultos: int,
    fecha_emision: str,
    fecha_retiro: str,
    ancho_card: float = 9.6 * cm,
) -> Table:
    """Construye el componente visual autocontenido de una etiqueta individual (10 por hoja A4, 2x5)."""
    ancho_inner = ancho_card - (0.4 * cm)
    styles = getSampleStyleSheet()
    uid = f"{bulto_idx}_{id(pedido)}"

    estilo_top_izq = ParagraphStyle(f"TopIzq_{uid}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=5.5, leading=6.5, textColor=colors.HexColor("#475569"))
    estilo_top_der = ParagraphStyle(f"TopDer_{uid}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.0, leading=7.0, alignment=2, textColor=colors.HexColor("#0f172a"))
    estilo_cli_etiqueta = ParagraphStyle(f"CliEtiqueta_{uid}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=5.0, leading=6.0, alignment=1, textColor=colors.HexColor("#64748b"))
    estilo_cliente_grande = ParagraphStyle(f"ClienteGrande_{uid}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=12.0, alignment=1, textColor=colors.HexColor("#0f172a"))
    estilo_bulto_grande = ParagraphStyle(f"BultoGrande_{uid}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9.5, leading=11.0, alignment=1, textColor=colors.HexColor("#dc2626"))
    estilo_campo_k = ParagraphStyle(f"CampoK_{uid}", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=5.2, leading=6.2, textColor=colors.HexColor("#334155"))
    estilo_campo_v = ParagraphStyle(f"CampoV_{uid}", parent=styles["Normal"], fontName="Helvetica", fontSize=5.5, leading=6.5, textColor=colors.HexColor("#0f172a"))
    estilo_qr_pie = ParagraphStyle(f"QRPie_{uid}", parent=styles["Normal"], fontName="Helvetica", fontSize=4.5, leading=5.5, alignment=1, textColor=colors.HexColor("#64748b"))

    items_label = []

    t_top = Table(
        [[Paragraph("RÓTULO DE DESPACHO", estilo_top_izq), Paragraph(f"Remito: <b>{escape(pedido.nota_pedido)}</b>", estilo_top_der)]],
        colWidths=[4.2 * cm, ancho_inner - 4.2 * cm],
    )
    t_top.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    items_label.append(t_top)

    cliente_formateado = _formatear_cliente_etiqueta(pedido)
    tarjeta_cliente = Table(
        [[Paragraph("CLIENTE / DESTINATARIO", estilo_cli_etiqueta)], [Paragraph(escape(cliente_formateado), estilo_cliente_grande)]],
        colWidths=[ancho_inner],
    )
    tarjeta_cliente.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    items_label.append(tarjeta_cliente)

    tarjeta_bulto = Table([[Paragraph(f"BULTO {bulto_idx} DE {total_bultos}", estilo_bulto_grande)]], colWidths=[ancho_inner])
    tarjeta_bulto.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dc2626")),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    items_label.append(tarjeta_bulto)

    datos_filas = [
        [Paragraph("Logística:", estilo_campo_k), Paragraph(f"<b>{escape(pedido.logistica)}</b>", estilo_campo_v)],
        [Paragraph("Fecha:", estilo_campo_k), Paragraph(escape(fecha_retiro), estilo_campo_v)],
        [Paragraph("Armador:", estilo_campo_k), Paragraph(escape(pedido.armador), estilo_campo_v)],
    ]
    t_datos_mini = Table(datos_filas, colWidths=[1.6 * cm, 5.0 * cm])
    t_datos_mini.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
    ]))

    contenido_qr = (
        f"REMITO:{pedido.nota_pedido}|CLIENTE:{cliente_formateado}|"
        f"BULTO:{bulto_idx}/{total_bultos}|LOGISTICA:{pedido.logistica}|"
        f"FECHA:{fecha_retiro}|ARMADOR:{pedido.armador}"
    )
    t_qr_sub = Table(
        [[_crear_qr_drawing(contenido_qr, tamano_cm=1.35)], [Paragraph("<b>CONTROL QR</b>", estilo_qr_pie)]],
        colWidths=[2.2 * cm],
    )
    t_qr_sub.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))

    t_inferior = Table([[t_datos_mini, t_qr_sub]], colWidths=[6.8 * cm, 2.3 * cm])
    t_inferior.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    items_label.append(t_inferior)

    tarjeta_exterior = Table([[items_label]], colWidths=[ancho_card])
    tarjeta_exterior.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return tarjeta_exterior


def generar_etiquetas_bultos_pdf(
    pedido: Pedido,
    carpeta_destino: Path,
    llenar_hoja: bool = False,
) -> Path:
    """Genera el PDF con las etiquetas A4 (2x5) de todos los bultos de un pedido."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    remito_limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in pedido.nota_pedido)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_pdf = carpeta_destino / f"Rotulos_{remito_limpio}_{timestamp}.pdf"

    total_bultos = max(1, pedido.bultos)
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    fecha_retiro = pedido.fecha_retiro.strip() if pedido.fecha_retiro else "Inmediato"

    tarjetas = [
        _construir_tarjeta_etiqueta(pedido, idx, total_bultos, fecha_emision, fecha_retiro)
        for idx in range(1, total_bultos + 1)
    ]

    if llenar_hoja and tarjetas:
        resto = len(tarjetas) % ETIQUETAS_POR_HOJA
        if resto != 0:
            for k in range(ETIQUETAS_POR_HOJA - resto):
                tarjetas.append(
                    _construir_tarjeta_etiqueta(pedido, (k % total_bultos) + 1, total_bultos, fecha_emision, fecha_retiro)
                )

    return compilar_grilla_a4_pdf(tarjetas, ruta_pdf)


def generar_etiquetas_lote_pedidos_pdf(
    pedidos: list[Pedido],
    carpeta_destino: Path,
    llenar_hoja: bool = False,
) -> Path:
    """Genera un PDF combinando rótulos de múltiples pedidos en hojas A4 (2x5)."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_pdf = carpeta_destino / f"Rotulos_Lote_{timestamp}.pdf"
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")

    todas_tarjetas: list[Table] = []
    lista_pedidos_bultos: list[tuple[Pedido, int, int, str]] = []

    for ped in pedidos:
        total_bultos = max(1, ped.bultos)
        fecha_retiro = ped.fecha_retiro.strip() if ped.fecha_retiro else "Inmediato"
        for idx in range(1, total_bultos + 1):
            todas_tarjetas.append(_construir_tarjeta_etiqueta(ped, idx, total_bultos, fecha_emision, fecha_retiro))
            lista_pedidos_bultos.append((ped, idx, total_bultos, fecha_retiro))

    if not todas_tarjetas:
        raise ValueError("No hay bultos para generar rótulos en el lote.")

    if llenar_hoja:
        resto = len(todas_tarjetas) % ETIQUETAS_POR_HOJA
        if resto != 0:
            for k in range(ETIQUETAS_POR_HOJA - resto):
                ped_ref, b_idx, tot_b, f_ret = lista_pedidos_bultos[k % len(lista_pedidos_bultos)]
                todas_tarjetas.append(_construir_tarjeta_etiqueta(ped_ref, b_idx, tot_b, fecha_emision, f_ret))

    return compilar_grilla_a4_pdf(todas_tarjetas, ruta_pdf)
