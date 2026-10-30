"""Generación de Rótulos / Etiquetas de Bultos de Despacho con Código QR en hoja A4.

Genera un documento PDF en formato estándar A4 con exactamente 6 etiquetas por hoja (disposición 2x3),
haciendo las etiquetas compactas y eficientes para impresión y corte sobre papel común o autoadhesivo.
Optimiza el aprovechamiento del papel A4 llenando completamente la hoja con los rótulos disponibles
para no desperdiciar adhesivo ni papel en blanco.
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


ETIQUETAS_POR_HOJA = 10
FILAS_POR_HOJA = 5
COLUMNAS_POR_HOJA = 2


def _construir_tarjeta_etiqueta(
    pedido: Pedido,
    bulto_idx: int,
    total_bultos: int,
    fecha_emision: str,
    fecha_retiro: str,
    ancho_card: float = 9.6 * cm,
) -> Table:
    """Construye el componente visual autocontenido de una etiqueta individual (10 por hoja A4, 2x5)."""
    ancho_inner = ancho_card - (0.4 * cm)  # Espacio interior util dentro de la tarjeta
    styles = getSampleStyleSheet()

    # Estilos tipograficos optimizados para grilla de 10 etiquetas por hoja A4
    estilo_top_izq = ParagraphStyle(
        f"TopIzq_{bulto_idx}_{id(pedido)}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=5.5,
        leading=6.5,
        textColor=colors.HexColor("#475569"),
    )
    estilo_top_der = ParagraphStyle(
        f"TopDer_{bulto_idx}_{id(pedido)}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=6.0,
        leading=7.0,
        alignment=2,  # Alineado a la derecha
        textColor=colors.HexColor("#0f172a"),
    )

    # Cliente GRANDE y visible
    estilo_cli_etiqueta = ParagraphStyle(
        f"CliEtiqueta_{bulto_idx}_{id(pedido)}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=5.0,
        leading=6.0,
        alignment=1,  # Centrado
        textColor=colors.HexColor("#64748b"),
    )
    estilo_cliente_grande = ParagraphStyle(
        f"ClienteGrande_{bulto_idx}_{id(pedido)}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=12.0,
        alignment=1,  # Centrado
        textColor=colors.HexColor("#0f172a"),
    )

    # Numero de Bulto GRANDE
    estilo_bulto_grande = ParagraphStyle(
        f"BultoGrande_{bulto_idx}_{id(pedido)}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=11.0,
        alignment=1,  # Centrado
        textColor=colors.HexColor("#dc2626"),
    )

    estilo_campo_k = ParagraphStyle(
        f"CampoK_{bulto_idx}_{id(pedido)}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=5.2,
        leading=6.2,
        textColor=colors.HexColor("#334155"),
    )
    estilo_campo_v = ParagraphStyle(
        f"CampoV_{bulto_idx}_{id(pedido)}",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=5.5,
        leading=6.5,
        textColor=colors.HexColor("#0f172a"),
    )
    estilo_qr_pie = ParagraphStyle(
        f"QRPie_{bulto_idx}_{id(pedido)}",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=4.5,
        leading=5.5,
        alignment=1,
        textColor=colors.HexColor("#64748b"),
    )

    items_label = []

    # 1. ENCABEZADO SUPERIOR: Tipo de rotulo y Remito / Factura
    t_top = Table(
        [
            [
                Paragraph("RÓTULO DE DESPACHO", estilo_top_izq),
                Paragraph(f"Remito: <b>{escape(pedido.nota_pedido)}</b>", estilo_top_der),
            ]
        ],
        colWidths=[4.2 * cm, ancho_inner - 4.2 * cm],
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

    # 2. NOMBRE DEL CLIENTE GRANDE (Destacado) Y CONCATENACION CON NUMERO DE PEDIDO
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
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    items_label.append(tarjeta_cliente)

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
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#dc2626")),
                ("TOPPADDING", (0, 0), (-1, -1), 1.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    items_label.append(tarjeta_bulto)

    # 4. DATOS COMPACTOS (Izquierda) + CODIGO QR (Derecha)
    datos_filas = [
        [Paragraph("Logística:", estilo_campo_k), Paragraph(f"<b>{escape(pedido.logistica)}</b>", estilo_campo_v)],
        [Paragraph("Fecha:", estilo_campo_k), Paragraph(escape(fecha_retiro), estilo_campo_v)],
        [Paragraph("Armador:", estilo_campo_k), Paragraph(escape(pedido.armador), estilo_campo_v)],
    ]
    t_datos_mini = Table(datos_filas, colWidths=[1.6 * cm, 5.0 * cm])
    t_datos_mini.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 0.8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
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
    qr_drawing = _crear_qr_drawing(contenido_qr, tamano_cm=1.35)
    info_qr = Paragraph("<b>CONTROL QR</b>", estilo_qr_pie)

    t_qr_sub = Table([[qr_drawing], [info_qr]], colWidths=[2.2 * cm])
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

    t_inferior = Table([[t_datos_mini, t_qr_sub]], colWidths=[6.8 * cm, 2.3 * cm])
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
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94a3b8")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return tarjeta_exterior


def generar_etiquetas_bultos_pdf(
    pedido: Pedido,
    carpeta_destino: Path,
    llenar_hoja: bool = False,
) -> Path:
    """Genera el PDF con las etiquetas de todos los bultos de un pedido.
    
    Distribuye exactamente 10 etiquetas por hoja A4 (disposicion cuadricula 2 columnas x 5 filas).
    Si llenar_hoja es True (por defecto), completa los espacios vacios de la hoja A4
    repitiendo equitativamente los rotulos del pedido para aprovechar al 100% la hoja.
    """
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    remito_limpio = "".join(c if c.isalnum() or c in "-_" else "_" for c in pedido.nota_pedido)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"Rotulos_{remito_limpio}_{timestamp}.pdf"
    ruta_pdf = carpeta_destino / nombre_archivo

    total_bultos = max(1, pedido.bultos)
    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")
    fecha_retiro = pedido.fecha_retiro.strip() if pedido.fecha_retiro else "Inmediato"

    # Construir todas las tarjetas individuales originales del pedido
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

    # Si se solicita llenar la hoja A4 y la ultima pagina no llega a 10 etiquetas,
    # completamos la cuadricula repitiendo equitativamente los bultos
    if llenar_hoja and tarjetas:
        resto = len(tarjetas) % ETIQUETAS_POR_HOJA
        if resto != 0:
            faltantes = ETIQUETAS_POR_HOJA - resto
            for k in range(faltantes):
                b_idx = (k % total_bultos) + 1
                tarjetas.append(
                    _construir_tarjeta_etiqueta(
                        pedido=pedido,
                        bulto_idx=b_idx,
                        total_bultos=total_bultos,
                        fecha_emision=fecha_emision,
                        fecha_retiro=fecha_retiro,
                        ancho_card=9.6 * cm,
                    )
                )

    story: list = []

    # Agrupar de a 10 etiquetas por pagina A4 (grilla 2 columnas x 5 filas)
    for i in range(0, len(tarjetas), ETIQUETAS_POR_HOJA):
        chunk = tarjetas[i : i + ETIQUETAS_POR_HOJA]
        while len(chunk) < ETIQUETAS_POR_HOJA:
            chunk.append("")  # Celdas vacias si llenar_hoja fuera False

        grid_data = [
            [chunk[0], chunk[1]],
            [chunk[2], chunk[3]],
            [chunk[4], chunk[5]],
            [chunk[6], chunk[7]],
            [chunk[8], chunk[9]],
        ]
        grid_table = Table(
            grid_data,
            colWidths=[9.8 * cm, 9.8 * cm],
            rowHeights=[5.55 * cm] * 5,
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

        # Salto de pagina para el siguiente bloque de 10 etiquetas
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


def generar_etiquetas_lote_pedidos_pdf(
    pedidos: list[Pedido],
    carpeta_destino: Path,
    llenar_hoja: bool = False,
) -> Path:
    """Genera un PDF combinando los rotulos de multiples pedidos en hojas A4 optimizadas (10 por hoja).
    
    Acomoda consecutivamente todos los bultos de los pedidos dados en grillas 2 columnas x 5 filas.
    Si llenar_hoja es True, completa los espacios sobrantes de la ultima pagina para no desperdiciar papel.
    """
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"Rotulos_Lote_{timestamp}.pdf"
    ruta_pdf = carpeta_destino / nombre_archivo

    fecha_emision = datetime.now().strftime("%d/%m/%Y %H:%M")

    todas_tarjetas = []
    lista_pedidos_bultos = []

    for ped in pedidos:
        total_bultos = max(1, ped.bultos)
        fecha_retiro = ped.fecha_retiro.strip() if ped.fecha_retiro else "Inmediato"
        for idx in range(1, total_bultos + 1):
            tarjeta = _construir_tarjeta_etiqueta(
                pedido=ped,
                bulto_idx=idx,
                total_bultos=total_bultos,
                fecha_emision=fecha_emision,
                fecha_retiro=fecha_retiro,
                ancho_card=9.6 * cm,
            )
            todas_tarjetas.append(tarjeta)
            lista_pedidos_bultos.append((ped, idx, total_bultos, fecha_retiro))

    if not todas_tarjetas:
        raise ValueError("No hay bultos para generar rótulos en el lote.")

    if llenar_hoja and todas_tarjetas:
        resto = len(todas_tarjetas) % ETIQUETAS_POR_HOJA
        if resto != 0:
            faltantes = ETIQUETAS_POR_HOJA - resto
            for k in range(faltantes):
                ped_ref, b_idx, tot_b, f_ret = lista_pedidos_bultos[k % len(lista_pedidos_bultos)]
                todas_tarjetas.append(
                    _construir_tarjeta_etiqueta(
                        pedido=ped_ref,
                        bulto_idx=b_idx,
                        total_bultos=tot_b,
                        fecha_emision=fecha_emision,
                        fecha_retiro=f_ret,
                        ancho_card=9.6 * cm,
                    )
                )

    story: list = []

    for i in range(0, len(todas_tarjetas), ETIQUETAS_POR_HOJA):
        chunk = todas_tarjetas[i : i + ETIQUETAS_POR_HOJA]
        while len(chunk) < ETIQUETAS_POR_HOJA:
            chunk.append("")

        grid_data = [
            [chunk[0], chunk[1]],
            [chunk[2], chunk[3]],
            [chunk[4], chunk[5]],
            [chunk[6], chunk[7]],
            [chunk[8], chunk[9]],
        ]
        grid_table = Table(
            grid_data,
            colWidths=[9.8 * cm, 9.8 * cm],
            rowHeights=[5.55 * cm] * 5,
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

        if i + ETIQUETAS_POR_HOJA < len(todas_tarjetas):
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


def generar_etiquetas_termicas_pdf(
    pedido: Pedido,
    carpeta_destino: Path | None = None,
    tamano_mm: tuple[float, float] = (100.0, 150.0),
    fecha_hora: datetime | None = None,
) -> Path:
    """Genera rótulos de despacho en formato continuo para impresoras térmicas (Zebra, Xprinter).
    
    Cada bulto del pedido ocupa exactamente 1 página individual del PDF con dimensiones exactas
    (por defecto 100mm x 150mm / 4"x6", o personalizable), permitiendo impresión continua sin cortes.
    """
    if carpeta_destino is None:
        raiz = Path(__file__).resolve().parent.parent
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
        # 1. Cabecera Térmica: Identificador de comprobante
        estilo_hdr_izq = ParagraphStyle(
            f"Term_HdrI_{bulto_idx}",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#dc2626"),
        )
        estilo_hdr_der = ParagraphStyle(
            f"Term_HdrD_{bulto_idx}",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=2,
            textColor=colors.HexColor("#0f172a"),
        )
        t_header = Table(
            [
                [
                    Paragraph("RÓTULO DE DESPACHO", estilo_hdr_izq),
                    Paragraph(f"Remito: <b>{escape(pedido.nota_pedido)}</b>", estilo_hdr_der),
                ]
            ],
            colWidths=[ancho_util * 0.5, ancho_util * 0.5],
        )
        t_header.setStyle(
            TableStyle(
                [
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        # 2. Tarjeta Destinatario / Cliente (Grande y destacado)
        num_ped = str(getattr(pedido, "numero_pedido", "") or "").strip()
        if num_ped:
            if not re.search(r"\b(nro|n°|nº|numero)\b", num_ped, re.IGNORECASE):
                sufijo_ped = f"Nro {num_ped}"
            else:
                sufijo_ped = num_ped
            cli_txt = f"{pedido.cliente.strip()} {sufijo_ped}"
        else:
            cli_txt = pedido.cliente.strip()

        estilo_cli_lbl = ParagraphStyle(
            f"Term_CliLbl_{bulto_idx}",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            alignment=1,
            textColor=colors.HexColor("#64748b"),
        )
        estilo_cli_val = ParagraphStyle(
            f"Term_CliVal_{bulto_idx}",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            alignment=1,
            textColor=colors.HexColor("#0f172a"),
        )
        t_cliente = Table(
            [
                [Paragraph("DESTINATARIO / CLIENTE", estilo_cli_lbl)],
                [Paragraph(escape(cli_txt), estilo_cli_val)],
            ],
            colWidths=[ancho_util],
        )
        t_cliente.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor("#94a3b8")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        # 3. Badge Gigante de Bulto: BULTO X DE Y
        estilo_bulto_txt = ParagraphStyle(
            f"Term_BultoTxt_{bulto_idx}",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=23,
            alignment=1,
            textColor=colors.white,
        )
        t_bulto = Table(
            [[Paragraph(f"BULTO {bulto_idx} DE {total_bultos}", estilo_bulto_txt)]],
            colWidths=[ancho_util],
        )
        t_bulto.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#dc2626")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            )
        )

        # 4. Datos Logísticos y N° de Guía
        n_guia = getattr(pedido, "numero_guia", "") or ""
        guia_txt = f"<br/><b>N° DE GUÍA / TRACKING:</b> <font color='#dc2626'>{escape(n_guia)}</font>" if n_guia else ""
        
        info_logistica_txt = (
            f"<b>TRANSPORTE / VÍA:</b> {escape(pedido.logistica)}<br/>"
            f"<b>ARMADOR:</b> {escape(pedido.armador)}  |  <b>FECHA:</b> {f_ret}"
            f"{guia_txt}"
        )
        estilo_log_info = ParagraphStyle(
            f"Term_LogInfo_{bulto_idx}",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1e293b"),
        )
        t_info = Table(
            [[Paragraph(info_logistica_txt, estilo_log_info)]],
            colWidths=[ancho_util],
        )
        t_info.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        # 5. Código QR de gran formato (3.5 cm)
        guia_part = f"|GUIA:{n_guia}" if n_guia else ""
        qr_payload = (
            f"REMITO:{pedido.nota_pedido}|"
            f"CLIENTE:{pedido.cliente}|"
            f"BULTO:{bulto_idx}/{total_bultos}|"
            f"LOGISTICA:{pedido.logistica}"
            f"{guia_part}"
        )
        qr_draw = _crear_qr_drawing(qr_payload, tamano_cm=3.6)
        estilo_pie_qr = ParagraphStyle(
            f"Term_PieQR_{bulto_idx}",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=1,
            textColor=colors.HexColor("#64748b"),
        )
        t_qr = Table(
            [
                [qr_draw],
                [Paragraph("Escaneá con la app para control de despacho en depósito", estilo_pie_qr)],
            ],
            colWidths=[ancho_util],
        )
        t_qr.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )

        story.append(t_header)
        story.append(Spacer(1, 0.25 * cm))
        story.append(t_cliente)
        story.append(Spacer(1, 0.25 * cm))
        story.append(t_bulto)
        story.append(Spacer(1, 0.25 * cm))
        story.append(t_info)
        story.append(Spacer(1, 0.25 * cm))
        story.append(t_qr)

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
