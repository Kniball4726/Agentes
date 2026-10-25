"""Generación de Rótulos / Etiquetas de Bultos de Despacho con Código QR.

Genera un documento PDF (formato estándar de etiqueta de 10x15 cm) con una página
por cada bulto del pedido (Bulto 1 de N, Bulto 2 de N, etc.), incluyendo datos de remito,
cliente, logística, armador y un código QR escaneable con teléfono o lector de mano.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from src.orders_store import Pedido


def _crear_qr_drawing(contenido: str, tamano_cm: float = 2.8) -> Drawing:
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


def generar_etiquetas_bultos_pdf(
    pedido: Pedido,
    carpeta_destino: Path,
) -> Path:
    """Genera el PDF con las etiquetas de todos los bultos de un pedido."""
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    remito_limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in pedido.nota_pedido)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"Rotulos_{remito_limpio}_{timestamp}.pdf"
    ruta_pdf = carpeta_destino / nombre_archivo

    ancho_etiqueta = 10.0 * cm
    alto_etiqueta = 15.0 * cm
    margen = 0.5 * cm
    ancho_util = ancho_etiqueta - (2 * margen)  # 9.0 cm

    styles = getSampleStyleSheet()

    estilo_empresa = ParagraphStyle(
        "EmpresaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=1,  # Centrado
        textColor=colors.HexColor("#475569"),
    )
    estilo_titulo_rotulo = ParagraphStyle(
        "TituloRotulo",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    )
    estilo_bulto_grande = ParagraphStyle(
        "BultoGrande",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=1,
        textColor=colors.HexColor("#dc2626"),
    )
    estilo_campo_clave = ParagraphStyle(
        "CampoClave",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    estilo_campo_valor = ParagraphStyle(
        "CampoValor",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )
    estilo_campo_valor_bold = ParagraphStyle(
        "CampoValorBold",
        parent=estilo_campo_valor,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
    )
    estilo_pie = ParagraphStyle(
        "PieLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        alignment=1,
        textColor=colors.HexColor("#64748b"),
    )

    total_bultos = max(1, pedido.bultos)
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    fecha_retiro = pedido.fecha_retiro.strip() if pedido.fecha_retiro else "Inmediato"

    story: list = []

    for bulto_idx in range(1, total_bultos + 1):
        # 1. ENCABEZADO DE LA ETIQUETA
        story.append(Paragraph("SISTEMA DE GESTIÓN DE DEPÓSITO", estilo_empresa))
        story.append(Paragraph("RÓTULO DE DESPACHO LOGÍSTICO", estilo_titulo_rotulo))
        story.append(Spacer(1, 0.2 * cm))

        # 2. CUADRO DESTACADO: BULTO X DE Y
        tarjeta_bulto = Table(
            [
                [
                    Paragraph(f"BULTO {bulto_idx} DE {total_bultos}", estilo_bulto_grande),
                ]
            ],
            colWidths=[ancho_util],
        )
        tarjeta_bulto.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#dc2626")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )
        story.append(tarjeta_bulto)
        story.append(Spacer(1, 0.25 * cm))

        # 3. TABLA DE DATOS DEL ENVÍO
        datos_tabla = [
            [
                Paragraph("<b>REMITO / FACTURA:</b>", estilo_campo_clave),
                Paragraph(escape(pedido.nota_pedido), estilo_campo_valor_bold),
            ],
            [
                Paragraph("<b>CLIENTE:</b>", estilo_campo_clave),
                Paragraph(escape(pedido.cliente), estilo_campo_valor_bold),
            ],
            [
                Paragraph("<b>TRANSPORTE / DESTINO:</b>", estilo_campo_clave),
                Paragraph(f"<b>{escape(pedido.logistica)}</b>", estilo_campo_valor),
            ],
            [
                Paragraph("<b>FECHA RETIRO / DESPACHO:</b>", estilo_campo_clave),
                Paragraph(escape(fecha_retiro), estilo_campo_valor),
            ],
            [
                Paragraph("<b>ARMADOR / OPERARIO:</b>", estilo_campo_clave),
                Paragraph(escape(pedido.armador), estilo_campo_valor),
            ],
            [
                Paragraph("<b>TOTAL BULTOS PEDIDO:</b>", estilo_campo_clave),
                Paragraph(f"{total_bultos} unidad(es)", estilo_campo_valor),
            ],
        ]

        t_datos = Table(datos_tabla, colWidths=[3.2 * cm, ancho_util - 3.2 * cm])
        t_datos.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(t_datos)
        story.append(Spacer(1, 0.25 * cm))

        # 4. CÓDIGO QR Y SEGURIDAD
        contenido_qr = (
            f"REMITO:{pedido.nota_pedido}|CLIENTE:{pedido.cliente}|"
            f"BULTO:{bulto_idx}/{total_bultos}|LOGISTICA:{pedido.logistica}|"
            f"FECHA:{fecha_retiro}|ARMADOR:{pedido.armador}"
        )
        qr_drawing = _crear_qr_drawing(contenido_qr, tamano_cm=2.7)

        bloque_qr_data = [
            [
                qr_drawing,
                Paragraph(
                    "<b>CÓDIGO DE CONTROL</b><br/>"
                    "Escanear para verificar recepción.<br/>"
                    f"Emitido: {fecha_emision}<br/>"
                    "<i>No cubrir ni rayar el código QR.</i>",
                    estilo_pie,
                ),
            ]
        ]
        t_qr = Table(bloque_qr_data, colWidths=[3.0 * cm, ancho_util - 3.0 * cm])
        t_qr.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(t_qr)
        story.append(Spacer(1, 0.15 * cm))

        # 5. PIE DE PÁGINA DE ETIQUETA
        story.append(
            Paragraph("Adherir en un lateral visible del bulto · Mantener seco", estilo_pie)
        )

        # Salto de página para el siguiente bulto si no es el último
        if bulto_idx < total_bultos:
            story.append(PageBreak())

    doc = SimpleDocTemplate(
        str(ruta_pdf),
        pagesize=(ancho_etiqueta, alto_etiqueta),
        leftMargin=margen,
        rightMargin=margen,
        topMargin=margen,
        bottomMargin=margen,
    )
    doc.build(story)
    return ruta_pdf
