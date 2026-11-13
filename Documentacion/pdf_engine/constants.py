# -*- coding: utf-8 -*-
"""Constantes dimensionales, cromáticas, estilos tipográficos y helpers APA/UPEL."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Table

# Dimensiones y Márgenes Reglamentarios según Manual UPEL (5ta ed.) / APA 7ma ed.
ANCHO_PAGINA, ALTO_PAGINA = A4
MARGEN_IZQ = 3.0 * cm  # Margen izquierdo reglamentario para encuadernación institucional
MARGEN_DER = 2.5 * cm
MARGEN_SUP = 2.5 * cm
MARGEN_INF = 2.5 * cm
ANCHO_UTIL = ANCHO_PAGINA - MARGEN_IZQ - MARGEN_DER  # 15.5 cm exactos

# Paleta Cromática Institucional de Alto Contraste (Norma ISO 40500 / WCAG 2.1)
COLOR_PRIMARIO = colors.HexColor("#17365D")     # Azul marino institucional profundo
COLOR_SECUNDARIO = colors.HexColor("#1F4E78")   # Azul corporativo técnico
COLOR_ACENTO_ROJO = colors.HexColor("#D32F2F")  # Rojo institucional UltraTech
COLOR_TEXTO = colors.HexColor("#111827")        # Texto oscuro de máximo contraste
COLOR_TEXTO_MUTED = colors.HexColor("#4B5563")  # Gris técnico secundario
COLOR_BORDE_APA = colors.HexColor("#1E293B")    # Filete horizontal oscuro para tablas APA
COLOR_FONDO_TABLA = colors.HexColor("#F8FAFC")  # Fondo alterno sutil
COLOR_BG_ALERT = colors.HexColor("#FEF2F2")     # Fondo advertencia / SoD
COLOR_BG_NOTE = colors.HexColor("#F0F9FF")      # Fondo nota técnica

VERSION_SOP_ACTUAL = "v2.2.0"


def obtener_estilos_iso_upel() -> dict[str, ParagraphStyle]:
    """Retorna la colección completa de estilos tipográficos estandarizados ISO y APA/UPEL."""
    hoja = getSampleStyleSheet()
    return {
        "portada_titulo": ParagraphStyle(
            "PortadaTitulo_UPEL",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=24,
            textColor=COLOR_PRIMARIO,
            alignment=1,
        ),
        "portada_sub": ParagraphStyle(
            "PortadaSub_UPEL",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=COLOR_SECUNDARIO,
            alignment=1,
        ),
        "portada_desc": ParagraphStyle(
            "PortadaDesc_UPEL",
            parent=hoja["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12.0,
            textColor=COLOR_TEXTO_MUTED,
            alignment=1,
        ),
        "h1": ParagraphStyle(
            "H1_APA",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12.0,
            leading=15.5,
            textColor=COLOR_PRIMARIO,
            spaceBefore=7,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "H2_APA",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.0,
            leading=13.5,
            textColor=COLOR_SECUNDARIO,
            spaceBefore=5,
            spaceAfter=2.5,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "H3_APA",
            parent=hoja["Normal"],
            fontName="Helvetica-BoldOblique",
            fontSize=8.8,
            leading=11.5,
            textColor=COLOR_TEXTO,
            spaceBefore=3.5,
            spaceAfter=2,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Cuerpo_ISO",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.5,
            textColor=COLOR_TEXTO,
            spaceAfter=3.5,
            alignment=4,
        ),
        "body_sangria": ParagraphStyle(
            "CuerpoSangria_UPEL",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.5,
            textColor=COLOR_TEXTO,
            firstLineIndent=1.0 * cm,
            spaceAfter=3.5,
            alignment=4,
        ),
        "bullet": ParagraphStyle(
            "Bullet_UPEL",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=COLOR_TEXTO,
            leftIndent=0.8 * cm,
            spaceAfter=2,
            alignment=4,
        ),
        "apa_tabla_num": ParagraphStyle(
            "APATablaNum",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11.0,
            textColor=COLOR_PRIMARIO,
            spaceBefore=5,
            spaceAfter=1,
            keepWithNext=True,
        ),
        "apa_tabla_titulo": ParagraphStyle(
            "APATablaTitulo",
            parent=hoja["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.0,
            leading=10.5,
            textColor=COLOR_SECUNDARIO,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "apa_tabla_nota": ParagraphStyle(
            "APATablaNota",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.2,
            textColor=COLOR_TEXTO_MUTED,
            spaceBefore=2,
            spaceAfter=3.5,
        ),
        "apa_figura_num": ParagraphStyle(
            "APAFiguraNum",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11.0,
            textColor=COLOR_PRIMARIO,
            spaceBefore=5,
            spaceAfter=1,
            keepWithNext=True,
        ),
        "apa_figura_titulo": ParagraphStyle(
            "APAFiguraTitulo",
            parent=hoja["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.0,
            leading=10.5,
            textColor=COLOR_SECUNDARIO,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "th_apa": ParagraphStyle(
            "TH_APA",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=COLOR_PRIMARIO,
            alignment=1,
        ),
        "td_apa": ParagraphStyle(
            "TD_APA",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.2,
            textColor=COLOR_TEXTO,
        ),
        "td_apa_center": ParagraphStyle(
            "TD_APA_Center",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.2,
            textColor=COLOR_TEXTO,
            alignment=1,
        ),
        "td_apa_bold_center": ParagraphStyle(
            "TD_APA_BoldCenter",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9.2,
            textColor=COLOR_PRIMARIO,
            alignment=1,
        ),
        "meta_bold": ParagraphStyle(
            "MetaBold_UPEL",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9.2,
            textColor=COLOR_PRIMARIO,
        ),
        "meta": ParagraphStyle(
            "Meta_UPEL",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.2,
            textColor=COLOR_TEXTO,
        ),
        "ref_apa": ParagraphStyle(
            "RefAPA",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10.5,
            textColor=COLOR_TEXTO,
            leftIndent=1.0 * cm,
            firstLineIndent=-1.0 * cm,
            spaceAfter=3.5,
        ),
        "th_firma": ParagraphStyle(
            "THFirma",
            parent=hoja["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.8,
            leading=10.0,
            textColor=COLOR_PRIMARIO,
            alignment=1,
        ),
        "sub_firma": ParagraphStyle(
            "SubFirma",
            parent=hoja["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=6.8,
            leading=8.8,
            textColor=COLOR_TEXTO_MUTED,
            alignment=1,
        ),
        "meta_firma": ParagraphStyle(
            "MetaFirma",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=7.0,
            leading=9.2,
            textColor=COLOR_TEXTO,
        ),
        "sig_firma": ParagraphStyle(
            "SigFirma",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=6.5,
            leading=8.5,
            textColor=COLOR_TEXTO,
            alignment=1,
        ),
        "toc_line": ParagraphStyle(
            "TOCLine",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=8.0,
            leading=12.0,
            textColor=COLOR_TEXTO,
        ),
    }


def crear_documento_iso(ruta_destino: Path) -> tuple[SimpleDocTemplate, dict[str, ParagraphStyle], list]:
    """Crea la carpeta padre y retorna `(doc, est, story)` configurados con márgenes UPEL."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(ruta_destino),
        pagesize=A4,
        leftMargin=MARGEN_IZQ,
        rightMargin=MARGEN_DER,
        topMargin=MARGEN_SUP,
        bottomMargin=MARGEN_INF,
    )
    return doc, obtener_estilos_iso_upel(), []


def agregar_titulo_capitulo(
    story: list,
    est: dict,
    titulo: str,
    page_break: bool = False,
) -> None:
    """Agrega un encabezado de capítulo H1 con filete horizontal azul marino."""
    if page_break:
        story.append(PageBreak())
    story.append(Paragraph(titulo, est["h1"]))
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.0,
            color=COLOR_PRIMARIO,
            spaceBefore=2,
            spaceAfter=4,
        )
    )


def crear_filas_tabla_apa(
    headers: Iterable[str],
    filas: Iterable[tuple[str, ...]],
    est: dict,
    estilos_columnas: list[str],
    *,
    negrita_col0: bool = False,
) -> list[list[Paragraph]]:
    """Convierte cabeceras y filas de texto en celdas Paragraph tipografiadas APA."""
    header_row = [Paragraph(f"<b>{h}</b>", est["th_apa"]) for h in headers]
    data: list[list[Paragraph]] = [header_row]
    for fila in filas:
        row_cells = []
        for idx, val in enumerate(fila):
            texto = f"<b>{val}</b>" if idx == 0 and negrita_col0 else val
            row_cells.append(Paragraph(texto, est[estilos_columnas[idx]]))
        data.append(row_cells)
    return data
