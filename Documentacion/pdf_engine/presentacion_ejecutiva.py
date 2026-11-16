# -*- coding: utf-8 -*-
"""Generador modular de la Presentación Ejecutiva StockAgent en PDF."""

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
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .constants import (
    ALTO_PAGINA,
    ANCHO_PAGINA,
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
from .presentacion_data import (
    BENEFICIOS_DIA_UNO,
    COMPARATIVA_DIAGNOSTICO,
    HORIZONTE_1,
    HORIZONTE_2,
    HORIZONTE_3,
    KPIS_PORTADA,
    MATRIZ_SOD_EJECUTIVA,
    META_EJECUTIVA,
    PASOS_PILOTO,
    PASOS_PIPELINE,
    SINTESIS_HORIZONTES,
    TARJETAS_ARQUITECTURA_SEGURIDAD,
    VENTAJAS_OPERATIVAS,
)

MARGEN_H = 1.7 * cm
MARGEN_V_SUP = 1.9 * cm
MARGEN_V_INF = 1.55 * cm
ANCHO_EJEC = ANCHO_PAGINA - (2 * MARGEN_H)  # 17.6 cm aprox.

BORDE_SUAVE = colors.HexColor("#CBD5E1")
FONDO_VERDE = colors.HexColor("#F0FDF4")
BORDE_VERDE = colors.HexColor("#16A34A")
FONDO_CARD = colors.HexColor("#F8FAFC")


def _crear_canvas_presentacion(fecha_emision: str):
    """Canvas ejecutivo con encabezado y pie limpios en páginas interiores."""
    from reportlab.pdfgen import canvas

    class EjecutivoCanvas(canvas.Canvas):
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
                self._dibujar_marco(total)
                super().showPage()
            super().save()

        def _dibujar_marco(self, total: int) -> None:
            if self._pageNumber == 1:
                return
            self.saveState()
            y_top = ALTO_PAGINA - 1.15 * cm
            self.setFont("Helvetica-Bold", 7.8)
            self.setFillColor(COLOR_PRIMARIO)
            self.drawString(MARGEN_H, y_top, f"STOCKAGENT · PRESENTACIÓN EJECUTIVA ({VERSION_SOP_ACTUAL})")

            self.setFont("Helvetica", 7.5)
            self.setFillColor(COLOR_TEXTO_MUTED)
            self.drawRightString(ANCHO_PAGINA - MARGEN_H, y_top, f"Uso Interno · Jefatura y Operaciones | {fecha_emision}")

            self.setStrokeColor(COLOR_ACENTO_ROJO)
            self.setLineWidth(1.0)
            self.line(MARGEN_H, y_top - 4, ANCHO_PAGINA - MARGEN_H, y_top - 4)

            y_bot = 1.0 * cm
            self.setStrokeColor(BORDE_SUAVE)
            self.setLineWidth(0.6)
            self.line(MARGEN_H, y_bot + 9, ANCHO_PAGINA - MARGEN_H, y_bot + 9)
            self.setFont("Helvetica", 7.2)
            self.setFillColor(COLOR_TEXTO_MUTED)
            self.drawString(MARGEN_H, y_bot, "UltraTech · Arquitectura Modular SQLite-First, Composición Pura y Trazabilidad LAN")
            self.drawRightString(ANCHO_PAGINA - MARGEN_H, y_bot, f"Página {self._pageNumber} de {total}")
            self.restoreState()

    return EjecutivoCanvas


def _estilos_ejecutivos() -> dict[str, ParagraphStyle]:
    """Estilos tipográficos de alto contraste optimizados para lectura gerencial."""
    base = getSampleStyleSheet()["Normal"]
    return {
        "eyebrow": ParagraphStyle("EjecEyebrow", parent=base, fontName="Helvetica-Bold", fontSize=8.0, leading=10, textColor=colors.HexColor("#FCA5A5")),
        "hero_title": ParagraphStyle("EjecHeroTitle", parent=base, fontName="Helvetica-Bold", fontSize=24.0, leading=27, textColor=colors.white),
        "hero_sub": ParagraphStyle("EjecHeroSub", parent=base, fontName="Helvetica", fontSize=9.4, leading=13, textColor=colors.HexColor("#E2E8F0")),
        "sec_kicker": ParagraphStyle("EjecKicker", parent=base, fontName="Helvetica-Bold", fontSize=7.8, leading=10, textColor=COLOR_ACENTO_ROJO),
        "sec_title": ParagraphStyle("EjecSecTitle", parent=base, fontName="Helvetica-Bold", fontSize=13.5, leading=16.5, textColor=COLOR_PRIMARIO, spaceAfter=2),
        "h2": ParagraphStyle("EjecH2", parent=base, fontName="Helvetica-Bold", fontSize=10.2, leading=13.0, textColor=COLOR_SECUNDARIO, spaceBefore=4, spaceAfter=3),
        "lead": ParagraphStyle("EjecLead", parent=base, fontName="Helvetica", fontSize=8.6, leading=12.0, textColor=COLOR_TEXTO_MUTED, spaceAfter=4),
        "kpi_val": ParagraphStyle("EjecKpiVal", parent=base, fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=COLOR_PRIMARIO, alignment=1),
        "kpi_lbl": ParagraphStyle("EjecKpiLbl", parent=base, fontName="Helvetica-Bold", fontSize=7.6, leading=9.5, textColor=COLOR_ACENTO_ROJO, alignment=1),
        "kpi_desc": ParagraphStyle("EjecKpiDesc", parent=base, fontName="Helvetica", fontSize=7.0, leading=9.0, textColor=COLOR_TEXTO_MUTED, alignment=1),
        "card_title": ParagraphStyle("EjecCardTitle", parent=base, fontName="Helvetica-Bold", fontSize=8.8, leading=11.5, textColor=COLOR_PRIMARIO, spaceAfter=2),
        "card_body": ParagraphStyle("EjecCardBody", parent=base, fontName="Helvetica", fontSize=7.9, leading=10.8, textColor=COLOR_TEXTO),
        "th": ParagraphStyle("EjecTH", parent=base, fontName="Helvetica-Bold", fontSize=8.0, leading=10.5, textColor=colors.white),
        "td": ParagraphStyle("EjecTD", parent=base, fontName="Helvetica", fontSize=7.8, leading=10.5, textColor=COLOR_TEXTO),
        "td_bold": ParagraphStyle("EjecTDBold", parent=base, fontName="Helvetica-Bold", fontSize=7.8, leading=10.5, textColor=COLOR_PRIMARIO),
        "callout_title": ParagraphStyle("EjecCallTitle", parent=base, fontName="Helvetica-Bold", fontSize=8.8, leading=11.5, textColor=COLOR_PRIMARIO),
        "callout_body": ParagraphStyle("EjecCallBody", parent=base, fontName="Helvetica", fontSize=8.1, leading=11.2, textColor=COLOR_TEXTO),
    }


def _bloque_seccion(story: list, est: dict[str, ParagraphStyle], kicker: str, titulo: str, bajada: str) -> None:
    story.append(Paragraph(escape(kicker), est["sec_kicker"]))
    story.append(Paragraph(escape(titulo), est["sec_title"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_ACENTO_ROJO, spaceBefore=1, spaceAfter=4))
    if bajada:
        story.append(Paragraph(escape(bajada), est["lead"]))


def _grilla_tarjetas_2x2(items: list[tuple[str, str]], est: dict[str, ParagraphStyle], acento=COLOR_SECUNDARIO) -> Table:
    col_w = (ANCHO_EJEC - 0.3 * cm) / 2.0
    tarjetas = []
    for titulo, desc in items:
        contenido = [
            Paragraph(escape(titulo), est["card_title"]),
            Paragraph(escape(desc), est["card_body"]),
        ]
        card = Table([[c] for c in contenido], colWidths=[col_w])
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), FONDO_CARD),
            ("LINEABOVE", (0, 0), (-1, 0), 2.2, acento),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDE_SUAVE),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]))
        tarjetas.append(card)

    filas = [
        [tarjetas[0], "", tarjetas[1]],
        ["", "", ""],
        [tarjetas[2], "", tarjetas[3]],
    ]
    grid = Table(filas, colWidths=[col_w, 0.3 * cm, col_w], rowHeights=[None, 0.22 * cm, None])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return grid


def _tabla_ejecutiva(
    headers: list[str],
    filas: list[tuple[str, ...]],
    anchos: list[float],
    est: dict[str, ParagraphStyle],
    *,
    negrita_col0: bool = True,
    header_color=COLOR_PRIMARIO,
) -> Table:
    data = [[Paragraph(escape(h), est["th"]) for h in headers]]
    for fila in filas:
        row_cells = []
        for idx, celda in enumerate(fila):
            estilo = est["td_bold"] if (idx == 0 and negrita_col0) else est["td"]
            row_cells.append(Paragraph(escape(celda).replace("\n", "<br/>"), estilo))
        data.append(row_cells)

    tabla = Table(data, colWidths=anchos, repeatRows=1)
    estilos = [
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, BORDE_SUAVE),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            estilos.append(("BACKGROUND", (0, r), (-1, r), COLOR_FONDO_TABLA))
    tabla.setStyle(TableStyle(estilos))
    return tabla


def _caja_callout(titulo: str, texto: str, est: dict[str, ParagraphStyle], *, verde: bool = False, alerta: bool = False) -> Table:
    bg = FONDO_VERDE if verde else (COLOR_BG_ALERT if alerta else COLOR_BG_NOTE)
    borde = BORDE_VERDE if verde else (COLOR_ACENTO_ROJO if alerta else COLOR_SECUNDARIO)
    t = Table([[Paragraph(escape(titulo), est["callout_title"])], [Paragraph(escape(texto), est["callout_body"])]], colWidths=[ANCHO_EJEC])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3.0, borde),
        ("BOX", (0, 0), (-1, -1), 0.45, BORDE_SUAVE),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, 1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _dibujar_flujo_pipeline() -> Drawing:
    """Genera diagrama vectorial horizontal de 5 etapas operativas."""
    d = Drawing(ANCHO_EJEC, 66)
    pasos = PASOS_PIPELINE
    n = len(pasos)
    gap = 10.0
    box_w = (ANCHO_EJEC - gap * (n - 1)) / n
    box_h = 54.0
    y0 = 6.0

    paleta = [COLOR_PRIMARIO, COLOR_SECUNDARIO, COLOR_ACENTO_ROJO, COLOR_SECUNDARIO, COLOR_PRIMARIO]
    for i, (titulo, desc) in enumerate(pasos):
        x0 = i * (box_w + gap)
        col = paleta[i]
        d.add(Rect(x0, y0, box_w, box_h, rx=4, ry=4, fillColor=FONDO_CARD, strokeColor=col, strokeWidth=1.0))
        d.add(Rect(x0, y0 + box_h - 16, box_w, 16, rx=3, ry=3, fillColor=col, strokeColor=col, strokeWidth=0))
        d.add(String(x0 + box_w / 2.0, y0 + box_h - 11.5, titulo, fontName="Helvetica-Bold", fontSize=6.8, fillColor=colors.white, textAnchor="middle"))
        for line_idx, line in enumerate(desc.split("\n")[:2]):
            d.add(String(x0 + box_w / 2.0, y0 + 23 - (line_idx * 10.5), line, fontName="Helvetica", fontSize=6.7, fillColor=COLOR_TEXTO, textAnchor="middle"))
        if i < n - 1:
            ax1 = x0 + box_w + 1.5
            ax2 = x0 + box_w + gap - 2.0
            ym = y0 + box_h / 2.0
            d.add(Line(ax1, ym, ax2 - 3, ym, strokeColor=COLOR_ACENTO_ROJO, strokeWidth=1.3))
            d.add(Polygon([ax2 - 4, ym + 3.2, ax2, ym, ax2 - 4, ym - 3.2], fillColor=COLOR_ACENTO_ROJO, strokeWidth=0))
    return d


def _agregar_pagina_1_portada(story: list, est: dict[str, ParagraphStyle], fecha_hoy: str) -> None:
    logo = Path("src/img/ultratech.png")
    if not logo.exists():
        logo = Path("assets/favicon.png")

    titulo_bloque = [
        Paragraph(f"PROPUESTA DE IMPLEMENTACIÓN TECNOLÓGICA · VERSIÓN MODULAR {VERSION_SOP_ACTUAL}", est["eyebrow"]),
        Spacer(1, 3),
        Paragraph("StockAgent", est["hero_title"]),
        Spacer(1, 2),
        Paragraph(
            "Plataforma Integral para el Control de Stock SQLite-First, Trazabilidad de Despachos en 3 Canales y Auditoría LAN",
            est["hero_sub"],
        ),
    ]
    if logo.exists():
        hero = Table([[Image(str(logo), width=2.0 * cm, height=2.0 * cm), titulo_bloque]], colWidths=[2.5 * cm, ANCHO_EJEC - 2.5 * cm])
        hero.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_PRIMARIO),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, -1), 3.0, COLOR_ACENTO_ROJO),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
    else:
        hero = Table([[titulo_bloque]], colWidths=[ANCHO_EJEC])
        hero.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COLOR_PRIMARIO),
            ("LINEBELOW", (0, 0), (-1, -1), 3.0, COLOR_ACENTO_ROJO),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ]))
    story.append(hero)
    story.append(Spacer(1, 0.28 * cm))

    # Strip de 4 KPIs
    gap_w = 0.24 * cm
    kpi_w = (ANCHO_EJEC - 3 * gap_w) / 4.0
    kpi_cells = []
    for val, lbl, desc in KPIS_PORTADA:
        box = Table(
            [[Paragraph(escape(val), est["kpi_val"])], [Paragraph(escape(lbl), est["kpi_lbl"])], [Paragraph(escape(desc), est["kpi_desc"])]],
            colWidths=[kpi_w],
        )
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), FONDO_CARD),
            ("LINEABOVE", (0, 0), (-1, 0), 2.2, COLOR_ACENTO_ROJO),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDE_SUAVE),
            ("TOPPADDING", (0, 0), (-1, 0), 5),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 5),
            ("TOPPADDING", (0, 1), (-1, -1), 1),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        kpi_cells.append(box)
    strip = Table([[kpi_cells[0], "", kpi_cells[1], "", kpi_cells[2], "", kpi_cells[3]]], colWidths=[kpi_w, gap_w, kpi_w, gap_w, kpi_w, gap_w, kpi_w])
    strip.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    story.append(strip)
    story.append(Spacer(1, 0.25 * cm))

    filas_meta = [*META_EJECUTIVA, ("Fecha de emisión:", fecha_hoy)]
    story.append(_tabla_ejecutiva(["Concepto", "Detalle Ejecutivo"], filas_meta, [4.2 * cm, ANCHO_EJEC - 4.2 * cm], est))
    story.append(Spacer(1, 0.24 * cm))
    story.append(Paragraph("¿Qué aporta StockAgent desde el primer día?", est["h2"]))
    story.append(_grilla_tarjetas_2x2(BENEFICIOS_DIA_UNO, est, acento=COLOR_SECUNDARIO))
    story.append(Spacer(1, 0.24 * cm))
    story.append(_caja_callout(
        "Idea central para la toma de decisión",
        "StockAgent no obliga a abandonar de golpe Productos.xlsx ni exige servidores en la nube: opera SQLite-first "
        "desde la PC actual de trabajo, ordena los despachos diarios por canal desde la primera semana y deja una base "
        "modular verificada lista para movilidad, analítica predictiva e integración ERP.",
        est,
    ))


def _agregar_pagina_2_beneficios(story: list, est: dict[str, ParagraphStyle]) -> None:
    story.append(PageBreak())
    _bloque_seccion(
        story, est,
        "SECCIÓN 1 · DIAGNÓSTICO Y BENEFICIOS INMEDIATOS",
        "Principales Bondades Operativas de la Aplicación",
        "Comparativa directa entre la gestión manual tradicional y la operación SQLite-first asistida con StockAgent.",
    )
    story.append(_tabla_ejecutiva(
        ["Desafío Habitual del Depósito", "Solución Concreta en StockAgent"],
        COMPARATIVA_DIAGNOSTICO,
        [5.6 * cm, ANCHO_EJEC - 5.6 * cm],
        est,
    ))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("Ventajas prácticas para la operación diaria del equipo", est["h2"]))
    story.append(_grilla_tarjetas_2x2(VENTAJAS_OPERATIVAS, est, acento=COLOR_ACENTO_ROJO))
    story.append(Spacer(1, 0.24 * cm))
    story.append(_caja_callout(
        "Impacto directo en la curva de aprendizaje",
        "Cada acción del sistema cuenta con procedimientos documentados en PDF según el rol (8 manuales generados "
        "automáticamente desde Documentacion/), paleta de comandos F2 / Ctrl+K y validaciones claras en español.",
        est,
        verde=True,
    ))


def _agregar_pagina_3_gobierno_arquitectura(story: list, est: dict[str, ParagraphStyle]) -> None:
    story.append(PageBreak())
    _bloque_seccion(
        story, est,
        "SECCIÓN 2 · GOBIERNO, INTELIGENCIA OPERATIVA Y ARQUITECTURA LIMPIA",
        "Control Interno (Roles SoD), Analítica y Blindaje Técnico",
        "Cada perfil accede estrictamente a lo necesario para su función, sobre un núcleo modular sin monolitos ni ciclos.",
    )
    story.append(_tabla_ejecutiva(
        ["Rol", "Qué Puede Hacer", "Límite de Seguridad (SoD)"],
        MATRIZ_SOD_EJECUTIVA,
        [2.5 * cm, 9.2 * cm, ANCHO_EJEC - 11.7 * cm],
        est,
    ))
    story.append(Spacer(1, 0.28 * cm))
    story.append(Paragraph("Capacidades analíticas, seguridad LAN y nueva base modular", est["h2"]))
    story.append(_grilla_tarjetas_2x2(TARJETAS_ARQUITECTURA_SEGURIDAD, est, acento=COLOR_PRIMARIO))


def _agregar_pagina_4_horizonte_1(story: list, est: dict[str, ParagraphStyle]) -> None:
    story.append(PageBreak())
    _bloque_seccion(
        story, est,
        "SECCIÓN 3 · HOJA DE RUTA DE IMPLEMENTACIÓN",
        "Flujo Operativo y Corto Plazo (Semanas 1 a 4)",
        "Estabilidad operativa y trazabilidad por 3 canales desde la primera semana sobre la infraestructura existente.",
    )
    story.append(_dibujar_flujo_pipeline())
    story.append(Spacer(1, 0.22 * cm))
    story.append(Paragraph("HORIZONTE 1 · CORTO PLAZO (SEMANAS 1–4): Puesta en Marcha y Orden Inmediato", est["h2"]))
    story.append(_tabla_ejecutiva(
        ["Iniciativa (Semanas 1–4)", "Acción Concreta en el Sitio de Trabajo", "Solución / Beneficio Inmediato"],
        HORIZONTE_1,
        [4.2 * cm, 7.6 * cm, ANCHO_EJEC - 11.8 * cm],
        est,
    ))


def _agregar_pagina_5_horizonte_2(story: list, est: dict[str, ParagraphStyle]) -> None:
    story.append(PageBreak())
    _bloque_seccion(
        story, est,
        "SECCIÓN 3 · HOJA DE RUTA DE IMPLEMENTACIÓN (CONTINUACIÓN)",
        "Soluciones a Mediano Plazo (Meses 2 a 4)",
        "Movilidad en pasillos, conteo físico ciego, sincronización OAuth Mercado Libre y prevención predictiva.",
    )
    story.append(Paragraph("HORIZONTE 2 · MEDIANO PLAZO (MESES 2–4): Movilidad, Precisión y Alertas", est["h2"]))
    story.append(_tabla_ejecutiva(
        ["Iniciativa (Meses 2–4)", "Implementación Progresiva", "Solución / Beneficio Operativo"],
        HORIZONTE_2,
        [4.2 * cm, 7.6 * cm, ANCHO_EJEC - 11.8 * cm],
        est,
    ))
    story.append(Spacer(1, 0.28 * cm))
    story.append(_caja_callout(
        "Ventaja financiera para la empresa en el mediano plazo",
        "A diferencia de soluciones comerciales donde cada módulo móvil o analítico exige licencias adicionales, "
        "StockAgent ya incluye la app móvil Flutter (25 archivos en lib/), el radar Z-score, el mapa de slotting ABC "
        "y las alertas SMTP/Telegram dentro del mismo ecosistema.",
        est,
        verde=True,
    ))


def _agregar_pagina_6_horizonte_3(story: list, est: dict[str, ParagraphStyle]) -> None:
    story.append(PageBreak())
    _bloque_seccion(
        story, est,
        "SECCIÓN 3 · HOJA DE RUTA DE IMPLEMENTACIÓN (CIERRE)",
        "Soluciones a Largo Plazo (Meses 5+) y Visión Global",
        "Arquitectura modular por composición pura y API REST v1 listas para escalar hacia ERP y multi-depósito.",
    )
    story.append(Paragraph("HORIZONTE 3 · LARGO PLAZO (MESES 5+): Integración Corporativa y Escalamiento", est["h2"]))
    story.append(_tabla_ejecutiva(
        ["Iniciativa (Meses 5+)", "Capacidad Habilitada", "Solución Estratégica"],
        HORIZONTE_3,
        [4.2 * cm, 7.6 * cm, ANCHO_EJEC - 11.8 * cm],
        est,
    ))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("Síntesis comparativa de los tres horizontes", est["h2"]))
    story.append(_tabla_ejecutiva(
        ["Horizonte", "Foco Principal", "Componentes Clave", "Esfuerzo", "Valor Central"],
        SINTESIS_HORIZONTES,
        [2.5 * cm, 3.0 * cm, 5.7 * cm, 2.7 * cm, ANCHO_EJEC - 13.9 * cm],
        est,
        header_color=COLOR_SECUNDARIO,
    ))


def _agregar_pagina_7_piloto(story: list, est: dict[str, ParagraphStyle]) -> None:
    story.append(PageBreak())
    _bloque_seccion(
        story, est,
        "SECCIÓN 4 · PROPUESTA DE INICIO CONTROLADO",
        "Plan Práctico de Piloto y Próximos Pasos Recomendados",
        "Prueba piloto controlada de 1 a 2 semanas para validar métricas operativas reales antes de ampliar alcance.",
    )
    story.append(_tabla_ejecutiva(
        ["Etapa", "Actividad", "Acción Concreta"],
        PASOS_PILOTO,
        [1.7 * cm, 4.3 * cm, ANCHO_EJEC - 6.0 * cm],
        est,
    ))
    story.append(Spacer(1, 0.24 * cm))
    story.append(_caja_callout(
        "Recursos Requeridos vs. Disponibles · Inversión en Licencias: USD 0",
        "Infraestructura base cubierta (PC Windows en oficina + red LAN + exportación compatible a Productos.xlsx). "
        "Ecosistema listo: ejecutable empaquetable (crear_exe.bat), 8 manuales PDF por rol (v2.3 / 3.2), cliente "
        "móvil Flutter y 67 módulos de prueba automatizados (360 tests verificados en sandbox + 6 módulos ASGI).",
        est,
    ))
    story.append(Spacer(1, 0.24 * cm))
    story.append(KeepTogether([
        Paragraph("Espacio de Revisión y Autorización de Piloto", est["h2"]),
        _tabla_ejecutiva(
            ["Responsable / Firma", "Dictamen y Observaciones"],
            [
                (
                    "Presentado por:\n________________________\nÁrea Operativa / TI\n\n"
                    "Revisado por (Jefatura):\n________________________\nFecha: ____ / ____ / 202__",
                    "Decisión:  [ ] Aprobado Piloto   [ ] Con Ajustes   [ ] Postergado\n\n"
                    "Observaciones y prioridades de Jefatura:\n"
                    "___________________________________________________________\n"
                    "___________________________________________________________",
                )
            ],
            [6.4 * cm, ANCHO_EJEC - 6.4 * cm],
            est,
            negrita_col0=False,
            header_color=COLOR_SECUNDARIO,
        ),
    ]))


def construir_presentacion_ejecutiva(ruta_destino: Path | str) -> Path:
    """Compila la Presentación Ejecutiva StockAgent en PDF y retorna la ruta generada."""
    destino = Path(ruta_destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    doc = SimpleDocTemplate(
        str(destino),
        pagesize=(ANCHO_PAGINA, ALTO_PAGINA),
        leftMargin=MARGEN_H,
        rightMargin=MARGEN_H,
        topMargin=MARGEN_V_SUP,
        bottomMargin=MARGEN_V_INF,
        title="Presentación Ejecutiva · StockAgent",
        author="UltraTech · StockAgent",
    )
    est = _estilos_ejecutivos()
    story: list = []

    _agregar_pagina_1_portada(story, est, fecha_hoy)
    _agregar_pagina_2_beneficios(story, est)
    _agregar_pagina_3_gobierno_arquitectura(story, est)
    _agregar_pagina_4_horizonte_1(story, est)
    _agregar_pagina_5_horizonte_2(story, est)
    _agregar_pagina_6_horizonte_3(story, est)
    _agregar_pagina_7_piloto(story, est)

    doc.build(story, canvasmaker=_crear_canvas_presentacion(fecha_hoy))
    return destino


__all__ = ["construir_presentacion_ejecutiva"]
