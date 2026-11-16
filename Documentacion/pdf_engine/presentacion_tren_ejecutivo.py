# -*- coding: utf-8 -*-
"""Generador modular de la Presentación al Tren Ejecutivo de StockAgent en PDF 16:9."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .constants import (
    COLOR_ACENTO_ROJO,
    COLOR_BG_ALERT,
    COLOR_BG_NOTE,
    COLOR_FONDO_TABLA,
    COLOR_PRIMARIO,
    COLOR_SECUNDARIO,
    COLOR_TEXTO,
    COLOR_TEXTO_MUTED,
    VERSION_SOP_ACTUAL,
)
from .presentacion_tren_ejecutivo_data import (
    SLIDE_1_KPIS,
    SLIDE_1_PILARES,
    SLIDE_2_COMPARATIVA,
    SLIDE_3_PLATAFORMAS,
    SLIDE_4_ENTRADAS,
    SLIDE_5_CANALES,
    SLIDE_5_PIPELINE,
    SLIDE_6_INVENTARIO,
    SLIDE_7_CIERRES,
    SLIDE_8_ANALITICA,
    SLIDE_9_COLABORACION,
    SLIDE_10_ROLES_SOD,
    SLIDE_11_ECOSISTEMA,
    SLIDE_12_HORIZONTES,
)

SLIDE_W = 29.7 * cm
SLIDE_H = 16.706 * cm  # Formato panorámico 16:9
MARGEN_X = 1.35 * cm
MARGEN_TOP = 1.15 * cm
MARGEN_BOT = 1.05 * cm
ANCHO_SLIDE = SLIDE_W - (2 * MARGEN_X)  # 27.0 cm

BORDE_SUAVE = colors.HexColor("#CBD5E1")
FONDO_CARD = colors.HexColor("#F8FAFC")
FONDO_VERDE = colors.HexColor("#F0FDF4")
BORDE_VERDE = colors.HexColor("#16A34A")


def _crear_canvas_slides(fecha_emision: str):
    """Canvas panorámico con pie institucional y numeración de diapositivas."""
    from reportlab.pdfgen import canvas

    class SlideCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._estados: list[dict] = []

        def showPage(self):
            self._estados.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._estados)
            for estado in self._estados:
                self.__dict__.update(estado)
                self._dibujar_marco_slide(total)
                super().showPage()
            super().save()

        def _dibujar_marco_slide(self, total: int) -> None:
            self.saveState()
            # Línea sutil inferior en todas las diapositivas
            y_bot = 0.55 * cm
            self.setStrokeColor(BORDE_SUAVE)
            self.setLineWidth(0.6)
            self.line(MARGEN_X, y_bot + 10, SLIDE_W - MARGEN_X, y_bot + 10)
            self.setFont("Helvetica", 7.3)
            self.setFillColor(COLOR_TEXTO_MUTED)
            self.drawString(
                MARGEN_X,
                y_bot,
                f"StockAgent · Presentación Tren Ejecutivo ({VERSION_SOP_ACTUAL}) | Emisión: {fecha_emision}",
            )
            self.setFont("Helvetica-Bold", 7.6)
            self.setFillColor(COLOR_PRIMARIO)
            self.drawRightString(SLIDE_W - MARGEN_X, y_bot, f"Diapositiva {self._pageNumber} de {total}")
            self.restoreState()

    return SlideCanvas


def _estilos_slides() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()["Normal"]
    return {
        "eyebrow": ParagraphStyle("SlEyebrow", parent=base, fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#FCA5A5")),
        "hero_title": ParagraphStyle("SlHeroTitle", parent=base, fontName="Helvetica-Bold", fontSize=24.0, leading=27, textColor=colors.white),
        "hero_sub": ParagraphStyle("SlHeroSub", parent=base, fontName="Helvetica", fontSize=10.2, leading=13.8, textColor=colors.HexColor("#E2E8F0")),
        "kicker": ParagraphStyle("SlKicker", parent=base, fontName="Helvetica-Bold", fontSize=8.2, leading=10.5, textColor=COLOR_ACENTO_ROJO),
        "title": ParagraphStyle("SlTitle", parent=base, fontName="Helvetica-Bold", fontSize=16.0, leading=19.5, textColor=COLOR_PRIMARIO),
        "subtitle": ParagraphStyle("SlSubtitle", parent=base, fontName="Helvetica", fontSize=9.2, leading=12.4, textColor=COLOR_TEXTO_MUTED, spaceAfter=4),
        "kpi_val": ParagraphStyle("SlKpiVal", parent=base, fontName="Helvetica-Bold", fontSize=14.0, leading=17, textColor=COLOR_PRIMARIO, alignment=1),
        "kpi_lbl": ParagraphStyle("SlKpiLbl", parent=base, fontName="Helvetica-Bold", fontSize=8.3, leading=10.5, textColor=COLOR_ACENTO_ROJO, alignment=1),
        "kpi_desc": ParagraphStyle("SlKpiDesc", parent=base, fontName="Helvetica", fontSize=7.8, leading=10.2, textColor=COLOR_TEXTO_MUTED, alignment=1),
        "card_title": ParagraphStyle("SlCardTitle", parent=base, fontName="Helvetica-Bold", fontSize=9.8, leading=12.6, textColor=COLOR_PRIMARIO, spaceAfter=2),
        "card_body": ParagraphStyle("SlCardBody", parent=base, fontName="Helvetica", fontSize=8.8, leading=12.0, textColor=COLOR_TEXTO),
        "th": ParagraphStyle("SlTH", parent=base, fontName="Helvetica-Bold", fontSize=8.6, leading=11.0, textColor=colors.white),
        "td": ParagraphStyle("SlTD", parent=base, fontName="Helvetica", fontSize=8.4, leading=11.3, textColor=COLOR_TEXTO),
        "td_bold": ParagraphStyle("SlTDBold", parent=base, fontName="Helvetica-Bold", fontSize=8.4, leading=11.3, textColor=COLOR_PRIMARIO),
        "call_title": ParagraphStyle("SlCallTitle", parent=base, fontName="Helvetica-Bold", fontSize=9.2, leading=12.0, textColor=COLOR_PRIMARIO),
        "call_body": ParagraphStyle("SlCallBody", parent=base, fontName="Helvetica", fontSize=8.6, leading=11.8, textColor=COLOR_TEXTO),
    }


def _encabezado_slide(
    story: list,
    est: dict[str, ParagraphStyle],
    kicker: str,
    titulo: str,
    bajada: str,
) -> None:
    story.append(Paragraph(escape(kicker), est["kicker"]))
    story.append(Paragraph(escape(titulo), est["title"]))
    story.append(HRFlowable(width="100%", thickness=1.4, color=COLOR_ACENTO_ROJO, spaceBefore=2, spaceAfter=4))
    if bajada:
        story.append(Paragraph(escape(bajada), est["subtitle"]))


def _grilla_2x2(
    items: list[tuple[str, str]],
    est: dict[str, ParagraphStyle],
    acento=COLOR_SECUNDARIO,
    alto_espacio: float = 0.28 * cm,
) -> Table:
    gap_w = 0.45 * cm
    col_w = (ANCHO_SLIDE - gap_w) / 2.0
    cards = []
    for titulo, desc in items:
        card = Table(
            [[Paragraph(escape(titulo), est["card_title"])], [Paragraph(escape(desc), est["card_body"])]],
            colWidths=[col_w],
        )
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), FONDO_CARD),
            ("LINEABOVE", (0, 0), (-1, 0), 2.6, acento),
            ("BOX", (0, 0), (-1, -1), 0.55, BORDE_SUAVE),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 7),
            ("TOPPADDING", (0, 1), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ]))
        cards.append(card)

    filas = [
        [cards[0], "", cards[1]],
        ["", "", ""],
        [cards[2], "", cards[3]],
    ]
    grid = Table(filas, colWidths=[col_w, gap_w, col_w], rowHeights=[None, alto_espacio, None])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return grid


def _tabla_slide(
    headers: list[str],
    filas: list[tuple[str, ...]],
    anchos: list[float],
    est: dict[str, ParagraphStyle],
    *,
    header_color=COLOR_PRIMARIO,
    pad_v: float = 5.5,
) -> Table:
    data = [[Paragraph(escape(h), est["th"]) for h in headers]]
    for fila in filas:
        row_cells = []
        for idx, celda in enumerate(fila):
            estilo = est["td_bold"] if idx == 0 else est["td"]
            row_cells.append(Paragraph(escape(celda).replace("\n", "<br/>"), estilo))
        data.append(row_cells)

    tabla = Table(data, colWidths=anchos, repeatRows=1)
    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDE_SUAVE),
        ("TOPPADDING", (0, 0), (-1, -1), pad_v),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad_v),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            estilos.append(("BACKGROUND", (0, r), (-1, r), COLOR_FONDO_TABLA))
    tabla.setStyle(TableStyle(estilos))
    return tabla


def _callout_slide(
    titulo: str,
    texto: str,
    est: dict[str, ParagraphStyle],
    *,
    verde: bool = False,
    alerta: bool = False,
) -> Table:
    bg = FONDO_VERDE if verde else (COLOR_BG_ALERT if alerta else COLOR_BG_NOTE)
    borde = BORDE_VERDE if verde else (COLOR_ACENTO_ROJO if alerta else COLOR_SECUNDARIO)
    t = Table(
        [[Paragraph(escape(titulo), est["call_title"])], [Paragraph(escape(texto), est["call_body"])]],
        colWidths=[ANCHO_SLIDE],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3.4, borde),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDE_SUAVE),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _dibujar_pipeline_widescreen() -> Drawing:
    d = Drawing(ANCHO_SLIDE, 68)
    n = len(SLIDE_5_PIPELINE)
    gap = 14.0
    box_w = (ANCHO_SLIDE - gap * (n - 1)) / n
    box_h = 56.0
    y0 = 6.0
    paleta = [COLOR_PRIMARIO, COLOR_SECUNDARIO, COLOR_ACENTO_ROJO, COLOR_SECUNDARIO, COLOR_PRIMARIO]

    for i, (titulo, desc) in enumerate(SLIDE_5_PIPELINE):
        x0 = i * (box_w + gap)
        col = paleta[i]
        d.add(Rect(x0, y0, box_w, box_h, rx=5, ry=5, fillColor=FONDO_CARD, strokeColor=col, strokeWidth=1.1))
        d.add(Rect(x0, y0 + box_h - 17, box_w, 17, rx=4, ry=4, fillColor=col, strokeColor=col, strokeWidth=0))
        d.add(String(x0 + box_w / 2.0, y0 + box_h - 12.2, titulo, fontName="Helvetica-Bold", fontSize=7.8, fillColor=colors.white, textAnchor="middle"))
        for idx, line in enumerate(desc.split("\n")[:2]):
            d.add(String(x0 + box_w / 2.0, y0 + 23.5 - (idx * 11.2), line, fontName="Helvetica", fontSize=7.8, fillColor=COLOR_TEXTO, textAnchor="middle"))
        if i < n - 1:
            ax1 = x0 + box_w + 2.0
            ax2 = x0 + box_w + gap - 2.5
            ym = y0 + box_h / 2.0
            d.add(Line(ax1, ym, ax2 - 4, ym, strokeColor=COLOR_ACENTO_ROJO, strokeWidth=1.5))
            d.add(Polygon([ax2 - 5, ym + 3.6, ax2, ym, ax2 - 5, ym - 3.6], fillColor=COLOR_ACENTO_ROJO, strokeWidth=0))
    return d


def _slide_1_portada(story: list, est: dict[str, ParagraphStyle]) -> None:
    logo = Path("src/img/ultratech.png")
    if not logo.exists():
        logo = Path("assets/favicon.png")

    titulo_bloque = [
        Paragraph(f"PRESENTACIÓN AL TREN EJECUTIVO · VERSIÓN {VERSION_SOP_ACTUAL}", est["eyebrow"]),
        Spacer(1, 3),
        Paragraph("StockAgent · Plataforma Integral de Depósito", est["hero_title"]),
        Spacer(1, 3),
        Paragraph(
            "Control de Inventario SQLite-First, Trazabilidad de Despachos en 3 Canales, Movilidad Offline, Analítica Predictiva y Seguridad SoD",
            est["hero_sub"],
        ),
    ]
    if logo.exists():
        hero = Table([[Image(str(logo), width=2.1 * cm, height=2.1 * cm), titulo_bloque]], colWidths=[2.7 * cm, ANCHO_SLIDE - 2.7 * cm])
        hero.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_PRIMARIO),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 3.4, COLOR_ACENTO_ROJO),
            ("TOPPADDING", (0, 0), (-1, -1), 11),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ]))
    else:
        hero = Table([[titulo_bloque]], colWidths=[ANCHO_SLIDE])
        hero.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_PRIMARIO),
            ("LINEBELOW", (0, 0), (-1, -1), 3.4, COLOR_ACENTO_ROJO),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ]))
    story.append(hero)
    story.append(Spacer(1, 0.34 * cm))

    gap_w = 0.35 * cm
    kpi_w = (ANCHO_SLIDE - 3 * gap_w) / 4.0
    kpi_cells = []
    for val, lbl, desc in SLIDE_1_KPIS:
        box = Table(
            [[Paragraph(escape(val), est["kpi_val"])], [Paragraph(escape(lbl), est["kpi_lbl"])], [Paragraph(escape(desc), est["kpi_desc"])]],
            colWidths=[kpi_w],
        )
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), FONDO_CARD),
            ("LINEABOVE", (0, 0), (-1, 0), 2.5, COLOR_ACENTO_ROJO),
            ("BOX", (0, 0), (-1, -1), 0.55, BORDE_SUAVE),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 1.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        kpi_cells.append(box)
    strip = Table(
        [[kpi_cells[0], "", kpi_cells[1], "", kpi_cells[2], "", kpi_cells[3]]],
        colWidths=[kpi_w, gap_w, kpi_w, gap_w, kpi_w, gap_w, kpi_w],
    )
    strip.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    story.append(strip)
    story.append(Spacer(1, 0.34 * cm))
    story.append(_grilla_2x2(SLIDE_1_PILARES, est, acento=COLOR_SECUNDARIO, alto_espacio=0.24 * cm))


def _agregar_slide_tarjetas(
    story: list,
    est: dict[str, ParagraphStyle],
    kicker: str,
    titulo: str,
    bajada: str,
    tarjetas: list[tuple[str, str]],
    callout_titulo: str,
    callout_texto: str,
    *,
    acento=COLOR_SECUNDARIO,
    verde: bool = False,
) -> None:
    story.append(PageBreak())
    _encabezado_slide(story, est, kicker, titulo, bajada)
    story.append(Spacer(1, 0.25 * cm))
    story.append(_grilla_2x2(tarjetas, est, acento=acento, alto_espacio=0.35 * cm))
    story.append(Spacer(1, 0.4 * cm))
    story.append(_callout_slide(callout_titulo, callout_texto, est, verde=verde))


def construir_presentacion_tren_ejecutivo(ruta_destino: Path | str) -> Path:
    """Genera el deck panorámico 16:9 de 12 diapositivas para el Tren Ejecutivo."""
    destino = Path(ruta_destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    doc = SimpleDocTemplate(
        str(destino),
        pagesize=(SLIDE_W, SLIDE_H),
        leftMargin=MARGEN_X,
        rightMargin=MARGEN_X,
        topMargin=MARGEN_TOP,
        bottomMargin=MARGEN_BOT,
        title="Presentación Tren Ejecutivo · StockAgent",
        author="StockAgent · Operaciones y Tecnología",
    )
    est = _estilos_slides()
    story: list = []

    # Diapositiva 1: Portada
    _slide_1_portada(story, est)

    # Diapositiva 2: Diagnóstico vs. Solución
    story.append(PageBreak())
    _encabezado_slide(
        story, est,
        "DIAPOSITIVA 2 · DIAGNÓSTICO OPERATIVO",
        "De la Operación Manual al Control en Tiempo Real",
        "Comparativa concreta de los dolores habituales del depósito frente a las capacidades activas de StockAgent.",
    )
    story.append(Spacer(1, 0.18 * cm))
    story.append(_tabla_slide(
        ["Desafío Tradicional del Depósito", "Solución Implementada en StockAgent"],
        SLIDE_2_COMPARATIVA,
        [9.8 * cm, ANCHO_SLIDE - 9.8 * cm],
        est,
        pad_v=6.0,
    ))

    # Diapositiva 3: Arquitectura Multiplataforma
    _agregar_slide_tarjetas(
        story, est,
        "DIAPOSITIVA 3 · ARQUITECTURA MULTICANAL",
        "Despliegue Híbrido: Red Local HTTPS, PWA Offline y App Móvil",
        "Flexibilidad total para operar desde PCs de oficina, tablets de pasillo, celulares Android/iOS o modo automático.",
        SLIDE_3_PLATAFORMAS,
        "Cero fricción operativa entre puestos y ambientes",
        "StockAgent prioriza HTTPS en red LAN con instancia única inteligente, permite separar Producción de QA sin contaminar saldos reales y conserva compatibilidad total con Descuentos/Productos.xlsx.",
        acento=COLOR_PRIMARIO,
    )

    # Diapositiva 4: Entradas y Movimientos Ágiles
    _agregar_slide_tarjetas(
        story, est,
        "DIAPOSITIVA 4 · RECEPCIÓN Y AJUSTES DE STOCK",
        "Gestión de Entradas de Fábrica y Movimientos Rápidos",
        "Registro veloz y auditado de mercadería entrante, devoluciones, mermas y ajustes por lector de barras.",
        SLIDE_4_ENTRADAS,
        "Seguridad ante errores humanos en tiempo real",
        "Cada ajuste de stock exige motivo tipificado, registra trazabilidad en SQLite y Kardex, ofrece ventana Deshacer durante 6 segundos en movimientos rápidos y revierte unidades atómicamente si se anula un pedido.",
        acento=COLOR_ACENTO_ROJO,
        verde=True,
    )

    # Diapositiva 5: Operación Comercial y Despacho QR
    story.append(PageBreak())
    _encabezado_slide(
        story, est,
        "DIAPOSITIVA 5 · PREPARACIÓN DE PEDIDOS Y DESPACHO",
        "Flujo Comercial Multicanal, Picking Full y Etiquetado QR",
        "Integración punta a punta desde la lectura del comprobante hasta el rótulo térmico y la entrega.",
    )
    story.append(Spacer(1, 0.1 * cm))
    story.append(_dibujar_pipeline_widescreen())
    story.append(Spacer(1, 0.24 * cm))
    story.append(_grilla_2x2(SLIDE_5_CANALES, est, acento=COLOR_SECUNDARIO, alto_espacio=0.28 * cm))

    # Diapositiva 6: Inventario en Vivo, Conteo y Reposición
    _agregar_slide_tarjetas(
        story, est,
        "DIAPOSITIVA 6 · CONTROL PATRIMONIAL DE EXISTENCIAS",
        "Inventario en Vivo, Conteo Físico Ciego y Reposición",
        "Control exacto entre estantería y sistema mediante escáner, auditorías ciegas y alertas de quiebre.",
        SLIDE_6_INVENTARIO,
        "Integridad bidireccional SQLite <-> Productos.xlsx",
        "Toda lectura o ajuste opera primero en SQLite transaccional (WAL) eliminando bloqueos entre usuarios, manteniendo exportación atómica hacia Descuentos/Productos.xlsx cuando Administración lo requiera.",
        acento=COLOR_PRIMARIO,
    )

    # Diapositiva 7: Cierres Operativos e Informes
    _agregar_slide_tarjetas(
        story, est,
        "DIAPOSITIVA 7 · CIERRES E INFORMES DE GESTIÓN",
        "Cierre de Jornada en 3 Canales, Hojas de Ruta y Reportes",
        "Conciliación diaria automática discriminada por canal para Depósito, Transporte y Administración.",
        SLIDE_7_CIERRES,
        "Distribución ágil y segura de la información",
        "Los informes generados se consultan desde el Centro de Reportes, se descargan mediante enlaces efímeros autenticados (?dt=) y se comparten directamente por Correo SMTP o WhatsApp Web.",
        acento=COLOR_ACENTO_ROJO,
        verde=True,
    )

    # Diapositiva 8: Analítica Avanzada y Heatmap ABC
    _agregar_slide_tarjetas(
        story, est,
        "DIAPOSITIVA 8 · ANALÍTICA E INTELIGENCIA OPERATIVA",
        "Métricas 360°, Radar de Anomalías y Heatmap de Depósito",
        "Herramientas estadísticas y visuales para anticipar quiebres, detectar desvíos y optimizar recorridos de picking.",
        SLIDE_8_ANALITICA,
        "Optimización real del depósito en 1 clic",
        "Desde el módulo Heatmap y Picking, Administración identifica artículos clase A mal ubicados y ejecuta la reubicación hacia la Zona Dorada directamente sobre la base de productos con confirmación instantánea.",
        acento=COLOR_PRIMARIO,
    )

    # Diapositiva 9: Colaboración Interna y Experiencia de Operador
    _agregar_slide_tarjetas(
        story, est,
        "DIAPOSITIVA 9 · COLABORACIÓN Y USABILIDAD",
        "Asistente Bot, Chat de Equipo con Campana e Interfaz Adaptable",
        "Comunicación en vivo entre terminales del depósito, accesibilidad por teclado y configuración personal por usuario.",
        SLIDE_9_COLABORACION,
        "Curva de aprendizaje mínima para todo el equipo",
        "Incluye 8 manuales procedimentales en PDF botón por botón según rol (Operador, Picker, Admin, Master y Consulta) accesibles desde el propio sistema.",
        acento=COLOR_SECUNDARIO,
        verde=True,
    )

    # Diapositiva 10: Gobernanza SoD y Ciberseguridad
    story.append(PageBreak())
    _encabezado_slide(
        story, est,
        "DIAPOSITIVA 10 · GOBIERNO Y SEGURIDAD",
        "Segregación de Funciones (SoD) y Controles Cibernéticos",
        "Cada perfil accede estrictamente a las operaciones de su responsabilidad, evitando conflictos de control interno.",
    )
    story.append(Spacer(1, 0.14 * cm))
    story.append(_tabla_slide(
        ["Rol", "Facultades Operativas Habilitadas", "Límite de Seguridad (Segregación SoD)"],
        SLIDE_10_ROLES_SOD,
        [3.1 * cm, 13.0 * cm, ANCHO_SLIDE - 16.1 * cm],
        est,
        pad_v=5.0,
    ))
    story.append(Spacer(1, 0.25 * cm))
    story.append(_callout_slide(
        "Blindaje técnico transversal en red y datos",
        "Contraseñas con PBKDF2 (600.000 iteraciones), bloqueo por intentos fallidos, cierre por inactividad (12 h), secretos cifrados (DPAPI/Fernet), TLS/HTTPS obligatorio LAN, firewall Privado y Swagger apagado por defecto.",
        est,
    ))

    # Diapositiva 11: Integraciones, API REST y Resguardo
    _agregar_slide_tarjetas(
        story, est,
        "DIAPOSITIVA 11 · ECOSISTEMA EXTENDIDO Y CONTINUIDAD",
        "API REST v1, Alertas Proactivas, Respaldos y QA Aislado",
        "Capacidades corporativas listas para conectar sistemas externos y resguardar la continuidad operativa.",
        SLIDE_11_ECOSISTEMA,
        "Base de código modular sin deuda monolítica",
        "Núcleo dividido por dominios (core, auth, orders, products, inventory, stock, integrations, api y ui por composición pura) preparado para auditar, testear y evolucionar de forma segura.",
        acento=COLOR_PRIMARIO,
    )

    # Diapositiva 12: Hoja de Ruta y Decisión Ejecutiva
    story.append(PageBreak())
    _encabezado_slide(
        story, est,
        "DIAPOSITIVA 12 · IMPACTO ESTRATÉGICO Y HOJA DE RUTA",
        "Plan de Adopción Progresiva Recomendado para el Tren Ejecutivo",
        "Implementación gradual de bajo riesgo que entrega resultados tangibles desde la primera semana.",
    )
    story.append(Spacer(1, 0.16 * cm))
    story.append(_tabla_slide(
        ["Horizonte", "Hitos y Funcionalidades Clave a Activar", "Impacto Directo para la Organización"],
        SLIDE_12_HORIZONTES,
        [3.8 * cm, 13.8 * cm, ANCHO_SLIDE - 17.6 * cm],
        est,
        header_color=COLOR_SECUNDARIO,
        pad_v=7.0,
    ))
    story.append(Spacer(1, 0.35 * cm))
    story.append(_callout_slide(
        "Conclusión para el Tren Ejecutivo",
        "StockAgent concentra en una sola plataforma propia la operación diaria del depósito, la trazabilidad comercial multicanal, la analítica preventiva (Radar y Heatmap ABC), la movilidad offline/Flutter y el control interno SoD, eliminando costos recurrentes de licencias externas.",
        est,
        verde=True,
    ))

    doc.build(story, canvasmaker=_crear_canvas_slides(fecha_hoy))
    return destino


__all__ = ["construir_presentacion_tren_ejecutivo"]
