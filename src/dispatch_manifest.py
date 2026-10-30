"""Generación de Hoja de Ruta y Manifiesto de Despacho por Transporte (PDF).

Este módulo agrupa los pedidos cerrados en la jornada por su logística/transporte
asignado, detallando remitos, clientes, bultos, armador, fecha de retiro y firma
de recepción para los choferes y transportistas.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

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

if TYPE_CHECKING:
    from src.orders_store import Pedido


class _NumberedCanvas(canvas.Canvas):
    """Canvas que realiza dos pasadas para calcular e imprimir el número total de páginas."""

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

        # Línea divisoria de pie de página
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(1.2 * cm, 1.3 * cm, A4[0] - 1.2 * cm, 1.3 * cm)

        texto_izq = f"Manifiesto de Despacho · Cierre #{self.cierre_id} · Emitido: {self.fecha_doc}"
        self.drawString(1.2 * cm, 0.85 * cm, texto_izq)

        texto_der = f"Página {self._pageNumber} de {total_paginas}"
        self.drawRightString(A4[0] - 1.2 * cm, 0.85 * cm, texto_der)
        self.restoreState()


def generar_hoja_ruta_pdf(
    cierre_id: int,
    pedidos: Sequence[Pedido],
    usuario: str,
    carpeta_destino: Path,
    fecha_hora: datetime | None = None,
    filtro_logistica: str | None = None,
) -> Path:
    """Genera la Hoja de Ruta de Despacho en PDF agrupada por transporte/logística.
    
    Si filtro_logistica está presente, genera la hoja exclusivamente para ese transporte.
    """
    if filtro_logistica:
        pedidos = [p for p in pedidos if (p.logistica or "").strip().lower() == filtro_logistica.strip().lower()]
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    dt = fecha_hora or datetime.now()
    fecha_formateada = dt.strftime("%d/%m/%Y %H:%M")
    timestamp_archivo = dt.strftime("%Y%m%d_%H%M%S")
    sufijo_log = f"_{filtro_logistica.replace(' ', '_')}" if filtro_logistica else ""
    nombre_archivo = f"Hoja_Ruta_Cierre_{cierre_id}{sufijo_log}_{timestamp_archivo}.pdf"
    ruta_pdf = carpeta_destino / nombre_archivo

    ancho_util = A4[0] - 2.4 * cm  # 18.6 cm

    # Estilos
    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle(
        "TituloManifiesto",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
    )
    estilo_subtitulo = ParagraphStyle(
        "SubtituloManifiesto",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )
    estilo_meta_clave = ParagraphStyle(
        "MetaClave",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )
    estilo_meta_valor = ParagraphStyle(
        "MetaValor",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    estilo_seccion = ParagraphStyle(
        "SeccionLogistica",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.white,
    )
    estilo_th = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
        alignment=1,  # Centrado
    )
    estilo_td = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#1e293b"),
    )
    estilo_td_center = ParagraphStyle(
        "TableCellCenter",
        parent=estilo_td,
        alignment=1,
    )
    estilo_td_bold = ParagraphStyle(
        "TableCellBold",
        parent=estilo_td,
        fontName="Helvetica-Bold",
    )
    estilo_subtotal = ParagraphStyle(
        "SubtotalText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
        alignment=2,  # Derecha
    )
    estilo_firma = ParagraphStyle(
        "FirmaText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )

    story: list = []

    # 1. ENCABEZADO PRINCIPAL
    total_pedidos = len(pedidos)
    total_bultos = sum(p.bultos for p in pedidos)

    # Agrupar pedidos por logística
    grupos_logistica: dict[str, list[Pedido]] = defaultdict(list)
    for p in pedidos:
        nombre_log = (p.logistica or "Sin Logística").strip()
        grupos_logistica[nombre_log].append(p)

    encabezado_data = [
        [
            Paragraph("<b>DEPÓSITO CENTRAL · LOGÍSTICA & DESPACHO</b>", estilo_subtitulo),
            Paragraph(f"<b>FECHA:</b> {fecha_formateada}", estilo_meta_valor),
        ],
        [
            Paragraph(f"HOJA DE RUTA Y MANIFIESTO DE DESPACHO · CIERRE #{cierre_id}", estilo_titulo),
            Paragraph(f"<b>RESPONSABLE:</b> {escape(usuario)}", estilo_meta_valor),
        ],
    ]
    t_encabezado = Table(encabezado_data, colWidths=[ancho_util * 0.70, ancho_util * 0.30])
    t_encabezado.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(t_encabezado)
    story.append(Spacer(1, 0.25 * cm))

    # BARRA DE RESUMEN EJECUTIVO (Cards resumen)
    resumen_data = [
        [
            Paragraph("<b>TOTAL PEDIDOS</b>", estilo_meta_clave),
            Paragraph("<b>TOTAL BULTOS</b>", estilo_meta_clave),
            Paragraph("<b>TRANSPORTES / DESTINOS</b>", estilo_meta_clave),
            Paragraph("<b>ESTADO CIERRE</b>", estilo_meta_clave),
        ],
        [
            Paragraph(f"<font size=12><b>{total_pedidos}</b></font>", estilo_meta_valor),
            Paragraph(f"<font size=12 color='#dc2626'><b>{total_bultos}</b></font>", estilo_meta_valor),
            Paragraph(f"<font size=12><b>{len(grupos_logistica)}</b></font>", estilo_meta_valor),
            Paragraph("<font size=10 color='#16a34a'><b>CONSOLIDADO</b></font>", estilo_meta_valor),
        ],
    ]
    t_resumen = Table(resumen_data, colWidths=[ancho_util / 4] * 4)
    t_resumen.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t_resumen)
    story.append(Spacer(1, 0.4 * cm))

    # 2. SECCIONES AGRUPADAS POR LOGÍSTICA
    # Ordenamos: primero las logísticas conocidas, luego alfabético
    logistica_orden = sorted(grupos_logistica.keys())

    # Anchos de columnas de la tabla de pedidos (total = 18.6 cm)
    col_w = [
        0.8 * cm,   # N°
        3.5 * cm,   # Remito / Factura
        4.8 * cm,   # Cliente
        1.5 * cm,   # Bultos
        2.4 * cm,   # Retiro / Despacho
        2.4 * cm,   # Armador
        3.2 * cm,   # Firma / Conformidad Chofer
    ]

    for logistica_nombre in logistica_orden:
        peds = grupos_logistica[logistica_nombre]
        bultos_log = sum(p.bultos for p in peds)

        bloque_logistica: list = []

        # Barra de título de logística
        titulo_log_data = [
            [
                Paragraph(f"LOGÍSTICA / TRANSPORTE: {escape(logistica_nombre.upper())}", estilo_seccion),
                Paragraph(
                    f"<b>{len(peds)} pedidos</b>  |  <b>{bultos_log} bultos totales</b>",
                    ParagraphStyle("Badge", parent=estilo_seccion, alignment=2),
                ),
            ]
        ]
        t_tit_log = Table(titulo_log_data, colWidths=[ancho_util * 0.65, ancho_util * 0.35])
        t_tit_log.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1e293b")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        bloque_logistica.append(t_tit_log)

        # Filas de tabla
        filas_tabla = [
            [
                Paragraph("<b>#</b>", estilo_th),
                Paragraph("<b>Remito / Factura</b>", estilo_th),
                Paragraph("<b>Cliente</b>", estilo_th),
                Paragraph("<b>Bultos</b>", estilo_th),
                Paragraph("<b>Fecha Retiro</b>", estilo_th),
                Paragraph("<b>Armador</b>", estilo_th),
                Paragraph("<b>Firma / Recepción Chofer</b>", estilo_th),
            ]
        ]

        for idx, ped in enumerate(peds, start=1):
            bg_color = colors.HexColor("#f8fafc") if idx % 2 == 0 else colors.white
            f_retiro = ped.fecha_retiro.strip() if ped.fecha_retiro else "Inmediato"
            remito_base = escape(ped.nota_pedido.strip())
            n_guia = getattr(ped, "numero_guia", "") or ""
            if n_guia:
                remito_txt = f"<b>{remito_base}</b><br/><font size=6 color='#64748b'>Guía: {escape(n_guia.strip())}</font>"
            else:
                remito_txt = f"<b>{remito_base}</b>"
            cliente_txt = ped.cliente.strip()
            armador_txt = ped.armador.strip()

            filas_tabla.append(
                [
                    Paragraph(str(idx), estilo_td_center),
                    Paragraph(remito_txt, estilo_td),
                    Paragraph(escape(cliente_txt), estilo_td),
                    Paragraph(f"<b>{ped.bultos}</b>", estilo_td_center),
                    Paragraph(escape(f_retiro), estilo_td_center),
                    Paragraph(escape(armador_txt), estilo_td),
                    Paragraph("", estilo_td),  # Espacio para firma
                ]
            )

        # Fila de subtotal
        filas_tabla.append(
            [
                Paragraph(f"<b>SUBTOTAL {escape(logistica_nombre.upper())}:</b>", estilo_subtotal),
                "",
                "",
                Paragraph(f"<b>{bultos_log}</b>", estilo_td_center),
                "",
                "",
                "",
            ]
        )

        t_pedidos = Table(filas_tabla, colWidths=col_w, repeatRows=1)
        estilo_t_pedidos = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            # Subtotal styling
            ("SPAN", (0, -1), (2, -1)),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
            ("BOX", (0, -1), (-1, -1), 1, colors.HexColor("#94a3b8")),
        ]

        # Aplicar colores alternados a las filas
        for idx in range(1, len(filas_tabla) - 1):
            if idx % 2 == 0:
                estilo_t_pedidos.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#f8fafc")))

        t_pedidos.setStyle(TableStyle(estilo_t_pedidos))
        bloque_logistica.append(t_pedidos)

        # Cuadro de firma y recepción por el chofer / transportista
        firma_chofer_data = [
            [
                Paragraph("<b>Transporte / Chofer:</b> ___________________________", estilo_firma),
                Paragraph("<b>DNI:</b> ___________________", estilo_firma),
                Paragraph("<b>Patente:</b> ___________", estilo_firma),
                Paragraph("<b>Firma Chofer:</b> ___________________", estilo_firma),
            ]
        ]
        t_firma = Table(firma_chofer_data, colWidths=[ancho_util * 0.38, ancho_util * 0.20, ancho_util * 0.16, ancho_util * 0.26])
        t_firma.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        bloque_logistica.append(t_firma)
        bloque_logistica.append(Spacer(1, 0.45 * cm))

        story.append(KeepTogether(bloque_logistica[:2]))
        for elem in bloque_logistica[2:]:
            story.append(elem)

    # 3. RESUMEN FINAL CONSOLIDADO Y FIRMA DE DEPÓSITO
    story.append(Spacer(1, 0.2 * cm))
    resumen_filas = [
        [
            Paragraph("<b>RESUMEN CONSOLIDADO DE DESPACHO POR TRANSPORTE</b>", estilo_th),
            Paragraph("<b>CANT. PEDIDOS</b>", estilo_th),
            Paragraph("<b>TOTAL BULTOS</b>", estilo_th),
        ]
    ]

    for logistica_nombre in logistica_orden:
        p_list = grupos_logistica[logistica_nombre]
        resumen_filas.append(
            [
                Paragraph(f"• {escape(logistica_nombre)}", estilo_td),
                Paragraph(str(len(p_list)), estilo_td_center),
                Paragraph(f"<b>{sum(p.bultos for p in p_list)}</b>", estilo_td_center),
            ]
        )

    resumen_filas.append(
        [
            Paragraph("<b>TOTAL GENERAL DESPACHADO:</b>", estilo_subtotal),
            Paragraph(f"<b>{total_pedidos}</b>", estilo_td_center),
            Paragraph(f"<b>{total_bultos}</b>", estilo_td_center),
        ]
    )

    t_resumen_final = Table(resumen_filas, colWidths=[ancho_util * 0.60, ancho_util * 0.20, ancho_util * 0.20])
    t_resumen_final.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    firma_deposito_data = [
        [
            Paragraph("<b>OBSERVACIONES DE DESPACHO:</b>", estilo_meta_clave),
            Paragraph("<b>CONFORMIDAD ENCARGADO DE DEPÓSITO</b>", estilo_meta_clave),
        ],
        [
            Paragraph(
                "Verificar que cada bulto contenga su respectivo rótulo de identificación antes de la entrega al transportista.",
                estilo_meta_valor,
            ),
            Paragraph(
                f"<br/><br/>________________________________________<br/>"
                f"<b>{escape(usuario)}</b><br/>Firma y Aclaración",
                estilo_meta_valor,
            ),
        ],
    ]
    t_deposito = Table(firma_deposito_data, colWidths=[ancho_util * 0.55, ancho_util * 0.45])
    t_deposito.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    bloque_cierre = [
        Spacer(1, 0.3 * cm),
        t_resumen_final,
        Spacer(1, 0.3 * cm),
        t_deposito,
    ]
    story.append(KeepTogether(bloque_cierre))

    # Construir documento
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
