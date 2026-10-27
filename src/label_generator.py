"""Generación de Rótulos / Etiquetas de Bultos de Despacho con Código QR en hoja A4.

Genera un documento PDF en formato estándar A4 con exactamente 6 etiquetas por hoja (disposición 2x3),
haciendo las etiquetas compactas y eficientes para impresión y corte sobre papel común o autoadhesivo.
Incluye por cada bulto del pedido (Bulto 1 de N, Bulto 2 de N, etc.):
- Nombre del cliente destacado en tamaño grande (igual de visible que el número de bulto).
- Cuadro destacado 'BULTO X DE Y' en gran tamaño y color contrastante.
- Datos de remito, logística, armador y fecha de despacho.
- Código QR vectorizado de alta resolución para trazabilidad y lectura con celular o escáner.
"""

from __future__ import annotations

import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
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


def _construir_tarjeta_etiqueta(
    pedido: Pedido,
    bulto_idx: int,
    total_bultos: int,
    fecha_emision: str,
    fecha_retiro: str,
    ancho_card: float = 9.6 * cm,
) -> Table:
    """Construye el componente visual autocontenido de una etiqueta individual (6 por hoja)."""
    ancho_inner = ancho_card - (0.5 * cm)  # Espacio interior útil dentro de la tarjeta
    styles = getSampleStyleSheet()

    # Estilos tipográficos
    estilo_top_izq = ParagraphStyle(
        f"TopIzq_{bulto_idx}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#475569"),
    )
    estilo_top_der = ParagraphStyle(
        f"TopDer_{bulto_idx}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.5,
        leading=8,
        alignment=2,  # Alineado a la derecha
        textColor=colors.HexColor("#0f172a"),
    )

    # Cliente GRANDE (tan visible como el número de bulto)
    estilo_cli_etiqueta = ParagraphStyle(
        f"CliEtiqueta_{bulto_idx}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=5.5,
        leading=6.5,
        alignment=1,  # Centrado
        textColor=colors.HexColor("#64748b"),
    )
    estilo_cliente_grande = ParagraphStyle(
        f"ClienteGrande_{bulto_idx}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13.5,
        leading=15.5,
        alignment=1,  # Centrado
        textColor=colors.HexColor("#0f172a"),
    )

    # Número de Bulto GRANDE
    estilo_bulto_grande = ParagraphStyle(
        f"BultoGrande_{bulto_idx}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=13.5,
        alignment=1,  # Centrado
        textColor=colors.HexColor("#dc2626"),
    )

    estilo_campo_k = ParagraphStyle(
        f"CampoK_{bulto_idx}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.2,
        leading=7.5,
        textColor=colors.HexColor("#334155"),
    )
    estilo_campo_v = ParagraphStyle(
        f"CampoV_{bulto_idx}",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=7.5,
        textColor=colors.HexColor("#0f172a"),
    )
    estilo_qr_pie = ParagraphStyle(
        f"QRPie_{bulto_idx}",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=5,
        leading=6,
        alignment=1,
        textColor=colors.HexColor("#64748b"),
    )

    items_label = []

    # 1. ENCABEZADO SUPERIOR: Tipo de rótulo y Remito / Factura
    t_top = Table(
        [
            [
                Paragraph("RÓTULO DE DESPACHO", estilo_top_izq),
                Paragraph(f"Remito: <b>{escape(pedido.nota_pedido)}</b>", estilo_top_der),
            ]
        ],
        colWidths=[4.5 * cm, ancho_inner - 4.5 * cm],
    )
    t_top.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    items_label.append(t_top)
    items_label.append(Spacer(1, 0.08 * cm))

    # 2. NOMBRE DEL CLIENTE GRANDE (Destacado) Y CONCATENACIÓN CON NÚMERO DE PEDIDO
    num_ped = str(getattr(pedido, "numero_pedido", "") or "").strip()
    if num_ped:
        if not re.search(r"\b(nro|n°|nº|numero)\b", num_ped, re.IGNORECASE):
            sufijo_pedido = f"Nro {num_ped}"
        else:
            sufijo_pedido = num_ped
        cliente_formateado = f"{pedido.cliente.strip()} {sufijo_pedido}"
    else:
        cliente_formateado = pedido.cliente.strip()

    nombre_cliente_txt = escape(cliente_formateado)
    tarjeta_cliente = Table(
        [
            [Paragraph("CLIENTE / DESTINATARIO", estilo_cli_etiqueta)],
            [Paragraph(nombre_cliente_txt, estilo_cliente_grande)],
        ],
        colWidths=[ancho_inner],
    )
    tarjeta_cliente.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    items_label.append(tarjeta_cliente)
    items_label.append(Spacer(1, 0.08 * cm))

    # 3. CUADRO DESTACADO: BULTO X DE Y
    tarjeta_bulto = Table(
        [
            [
                Paragraph(f"BULTO {bulto_idx} DE {total_bultos}", estilo_bulto_grande),
            ]
        ],
        colWidths=[ancho_inner],
    )
    tarjeta_bulto.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef2f2")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#dc2626")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    items_label.append(tarjeta_bulto)
    items_label.append(Spacer(1, 0.08 * cm))

    # 4. DATOS COMPACTOS (Izquierda) + CÓDIGO QR (Derecha)
    datos_filas = [
        [Paragraph("Logística:", estilo_campo_k), Paragraph(f"<b>{escape(pedido.logistica)}</b>", estilo_campo_v)],
        [Paragraph("Fecha:", estilo_campo_k), Paragraph(escape(fecha_retiro), estilo_campo_v)],
        [Paragraph("Armador:", estilo_campo_k), Paragraph(escape(pedido.armador), estilo_campo_v)],
    ]
    t_datos_mini = Table(datos_filas, colWidths=[1.8 * cm, 4.3 * cm])
    t_datos_mini.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 1.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ]
        )
    )

    contenido_qr = (
        f"REMITO:{pedido.nota_pedido}|CLIENTE:{cliente_formateado}|"
        f"BULTO:{bulto_idx}/{total_bultos}|LOGISTICA:{pedido.logistica}|"
        f"FECHA:{fecha_retiro}|ARMADOR:{pedido.armador}"
    )
    qr_drawing = _crear_qr_drawing(contenido_qr, tamano_cm=1.7)
    info_qr = Paragraph("<b>CONTROL QR</b><br/>Escanear despacho", estilo_qr_pie)

    t_qr_sub = Table([[qr_drawing], [info_qr]], colWidths=[2.6 * cm])
    t_qr_sub.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )

    t_inferior = Table([[t_datos_mini, t_qr_sub]], colWidths=[6.3 * cm, 2.8 * cm])
    t_inferior.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    items_label.append(t_inferior)

    # Tarjeta externa con borde perimetral para corte
    tarjeta_exterior = Table([[items_label]], colWidths=[ancho_card])
    tarjeta_exterior.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#94a3b8")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return tarjeta_exterior


def generar_etiquetas_bultos_pdf(
    pedido: Pedido,
    carpeta_destino: Path,
) -> Path:
    """Genera el PDF con las etiquetas de todos los bultos de un pedido.
    
    Distribuye exactamente 6 etiquetas por hoja A4 (disposición cuadrícula 2x3).
    """
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    remito_limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in pedido.nota_pedido)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"Rotulos_{remito_limpio}_{timestamp}.pdf"
    ruta_pdf = carpeta_destino / nombre_archivo

    total_bultos = max(1, pedido.bultos)
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    fecha_retiro = pedido.fecha_retiro.strip() if pedido.fecha_retiro else "Inmediato"

    # Construir todas las tarjetas individuales
    tarjetas = [
        _construir_tarjeta_etiqueta(
            pedido=pedido,
            bulto_idx=idx,
            total_bultos=total_bultos,
            fecha_emision=fecha_emision,
            fecha_retiro=fecha_retiro,
            ancho_card=9.6 * cm,
        )
        for idx in range(1, total_bultos + 1)
    ]

    story: list = []

    # Agrupar de a 6 etiquetas por página A4 (grilla 2 columnas x 3 filas)
    for i in range(0, len(tarjetas), 6):
        chunk = tarjetas[i : i + 6]
        while len(chunk) < 6:
            chunk.append("")  # Celdas vacías si la última página tiene menos de 6

        grid_data = [
            [chunk[0], chunk[1]],
            [chunk[2], chunk[3]],
            [chunk[4], chunk[5]],
        ]
        grid_table = Table(
            grid_data,
            colWidths=[9.8 * cm, 9.8 * cm],
            rowHeights=[9.2 * cm, 9.2 * cm, 9.2 * cm],
        )
        grid_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )
        story.append(grid_table)

        # Salto de página para el siguiente bloque de 6 etiquetas
        if i + 6 < len(tarjetas):
            story.append(PageBreak())

    doc = SimpleDocTemplate(
        str(ruta_pdf),
        pagesize=A4,
        leftMargin=0.5 * cm,
        rightMargin=0.5 * cm,
        topMargin=0.5 * cm,
        bottomMargin=0.5 * cm,
    )
    doc.build(story)
    return ruta_pdf
