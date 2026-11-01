# -*- coding: utf-8 -*-
"""Generador de Manuales de Procedimientos Administrativos y de Uso de Sistemas Informáticos.

Estructurado conforme a:
- ISO/IEC/IEEE 26514:2022: Documentación de usuario para software e ingeniería de sistemas.
- ISO 9001:2015: Cláusulas 4.4 (Procesos), 7.1.3 (Infraestructura), 7.2 (Competencia), 7.5 (Información Documentada),
                 8.5.6 (Control de Cambios), 9.1 (KPIs) y 10.2 (No Conformidades y Acciones Correctivas).
- ISO/IEC 27001:2022: Control de Accesos y Segregación de Funciones (SoD Control 5.3, Auditoría 8.15).
- BPMN 2.0 (OMG Specification / Bizagi Modeler): Modelado de flujos con Pools, Swimlanes y eventos normados.
- Normas APA (7ma edición) y Manual de Trabajos de Grado UPEL (5ta edición):
  * Tipografía normalizada ISO: Helvetica lineal a 9.5-10 pt (cuerpo) y 7.5-8 pt (tablas y notas).
  * Redacción formal en tercera persona e impersonal.
  * Tablas y Figuras en formato reglamentario APA: sin líneas verticales, con filetes horizontales normados,
    etiquetado superior 'Tabla X' / 'Figura X' en negrita, título descriptivo en cursiva y 'Nota.' al pie.
  * Márgenes UPEL: 3.0 cm izquierdo (encuadernación) y 2.5 cm superior, derecho e inferior.
  * Formulario formal de firmas autorizadas y validación institucional (ISO 9001 §7.5.2).
  * Matriz de control de distribución de copias controladas (ISO 9001 §7.5.3).
  * Procedimiento Estándar de Gestión del Cambio y Actualización de Manuales (POE-SGC-01).
  * Acta de Capacitación, Inducción y Notificación de Conocimiento del Personal (ISO 9001 §7.2).
  * Tarjeta de Referencia Rápida plastificable (Cheat Sheet de atajos de teclado y alertas sonoras).
  * Glosario formal de términos y referencias normativas con sangría francesa APA.
"""

from datetime import datetime
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import (
    Circle,
    Drawing,
    Group,
    Line,
    Polygon,
    Rect,
    String,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
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


def crear_canvas_iso_upel(codigo_doc: str, titulo_doc: str, version: str = "v2.1.0"):
    """Fábrica de Canvas con encabezados y pies de página normalizados ISO 26514 y UPEL/APA."""
    class ISOUPELNumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_paginas = len(self._saved_page_states)
            for estado in self._saved_page_states:
                self.__dict__.update(estado)
                self._dibujar_encabezado_y_pie(num_paginas)
                super().showPage()
            super().save()

        def _dibujar_encabezado_y_pie(self, total_paginas: int):
            if self._pageNumber == 1:
                return  # Portada cuenta con diagramación propia

            self.saveState()

            # Encabezado institucional ISO / APA
            y_header = ALTO_PAGINA - 1.5 * cm
            self.setFont("Helvetica-Bold", 8.0)
            self.setFillColor(COLOR_SECUNDARIO)
            self.drawString(MARGEN_IZQ, y_header, f"StockAgent · {titulo_doc}")

            self.setFont("Helvetica", 7.5)
            self.setFillColor(COLOR_TEXTO_MUTED)
            self.drawRightString(ANCHO_PAGINA - MARGEN_DER, y_header, f"{codigo_doc} | {version} | ISO/APA/UPEL")

            self.setStrokeColor(COLOR_BORDE_APA)
            self.setLineWidth(0.6)
            self.line(MARGEN_IZQ, y_header - 3, ANCHO_PAGINA - MARGEN_DER, y_header - 3)

            # Pie de página institucional con numeración de dos pasadas
            y_footer = 1.3 * cm
            self.line(MARGEN_IZQ, y_footer + 8, ANCHO_PAGINA - MARGEN_DER, y_footer + 8)

            self.setFont("Helvetica", 7.5)
            self.setFillColor(COLOR_TEXTO_MUTED)
            self.drawString(MARGEN_IZQ, y_footer, "CONFIDENCIAL — Sistema de Gestión Documental UltraTech S.A. · Control de Calidad")

            texto_pag = f"Página {self._pageNumber} de {total_paginas}"
            self.drawRightString(ANCHO_PAGINA - MARGEN_DER, y_footer, texto_pag)

            self.restoreState()

    return ISOUPELNumberedCanvas


def obtener_estilos_iso_upel():
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
        # Encabezados según jerarquía formal APA 7ma / UPEL
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
        # Cuerpo de texto conforme a norma tipográfica ISO: 9.5 pt / 13 pt leading
        "body": ParagraphStyle(
            "Cuerpo_ISO",
            parent=hoja["Normal"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.5,
            textColor=COLOR_TEXTO,
            spaceAfter=3.5,
            alignment=4,  # Justificado
        ),
        # Sangría de primera línea reglamentaria UPEL (1.0 cm)
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
        # Estilos reglamentarios de Tablas y Figuras APA 7ma Edición
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


def crear_caja_alerta_iso(titulo: str, texto: str, tipo: str = "nota") -> Table:
    """Genera una caja técnica destacada para notas normativas o de seguridad SoD."""
    color_borde = COLOR_ACENTO_ROJO if tipo == "sod" else (COLOR_SECUNDARIO if tipo == "nota" else colors.HexColor("#16A34A"))
    color_bg = COLOR_BG_ALERT if tipo == "sod" else (COLOR_BG_NOTE if tipo == "nota" else colors.HexColor("#F0FDF4"))

    estilo_caja = ParagraphStyle(
        name=f"CajaISOUPEL_{tipo}_{hash(titulo+texto)}",
        fontName="Helvetica",
        fontSize=8.0,
        leading=11.2,
        textColor=COLOR_TEXTO,
    )

    html = f"<font color='{color_borde.hexval()}'><b>{escape(titulo)}</b></font><br/>{texto}"
    p = Paragraph(html, estilo_caja)

    t = Table([[p]], colWidths=[ANCHO_UTIL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color_bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3.0, color_borde),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def aplicar_estilo_tabla_apa(tabla: Table, filas_totales: int) -> Table:
    """Aplica rigurosamente las pautas de presentación de tablas APA 7ma / UPEL."""
    estilos = [
        # Las normas APA prohíben líneas verticales
        ("INNERGRID", (0, 0), (-1, -1), 0, colors.transparent),
        ("BOX", (0, 0), (-1, -1), 0, colors.transparent),
        # Tres líneas horizontales reglamentarias:
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, COLOR_BORDE_APA),   # Borde superior de tabla
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, COLOR_BORDE_APA),   # Separador encabezado
        ("LINEBELOW", (0, filas_totales - 1), (-1, filas_totales - 1), 1.0, COLOR_BORDE_APA), # Borde inferior
        # Fondo sutil de encabezado
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.2),
    ]
    # Sombreado alterno muy sutil para facilitar la lectura de filas densas
    for i in range(1, filas_totales):
        if i % 2 == 1:
            estilos.append(("BACKGROUND", (0, i), (-1, i), COLOR_FONDO_TABLA))
    tabla.setStyle(TableStyle(estilos))
    return tabla


# =============================================================================
# MOTOR DE DIAGRAMACIÓN VECTORIAL BPMN 2.0 (ESTILO BIZAGI MODELER / CAMUNDA)
# =============================================================================
def crear_dibujo_bpmn_swimlanes(
    titulo_pool: str,
    lanes: list[str],
    nodos: list[dict],
    flujos: list[tuple[float, float, float, float]],
    ancho: float = 439,
    alto: float = 115,
) -> Drawing:
    """Genera un diagrama vectorial BPMN 2.0 con Pool y Swimlanes al estilo Bizagi Modeler."""
    d = Drawing(ancho, alto)

    # Fondo general del Pool
    d.add(Rect(0, 0, ancho, alto, fillColor=colors.HexColor("#FFFFFF"), strokeColor=COLOR_PRIMARIO, strokeWidth=1.0))

    num_lanes = len(lanes)
    lane_h = alto / num_lanes
    ancho_pool_header = 16
    ancho_lane_header = 78

    # Franja vertical izquierda: Identificador de Pool
    d.add(Rect(0, 0, ancho_pool_header, alto, fillColor=COLOR_PRIMARIO, strokeColor=COLOR_PRIMARIO))
    d.add(String(ancho_pool_header / 2 + 1, alto / 2, "POOL", textAnchor="middle", fontName="Helvetica-Bold", fontSize=6.0, fillColor=colors.HexColor("#FFFFFF")))

    # Franja de cabecera de Swimlanes (Roles / Autores)
    d.add(Rect(ancho_pool_header, 0, ancho_lane_header, alto, fillColor=colors.HexColor("#F1F5F9"), strokeColor=colors.HexColor("#64748B"), strokeWidth=0.8))

    # Líneas divisorias de carriles (calles)
    for i, lane_name in enumerate(reversed(lanes)):
        y = i * lane_h
        if i > 0:
            d.add(Line(ancho_pool_header, y, ancho, y, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=0.7, strokeDashArray=[3, 2]))
        d.add(String(ancho_pool_header + 4, y + lane_h / 2 - 2.5, lane_name, fontName="Helvetica-Bold", fontSize=6.2, fillColor=COLOR_SECUNDARIO))

    # Flujos de secuencia (Flechas BPMN)
    for x1, y1, x2, y2 in flujos:
        d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#475569"), strokeWidth=0.9))
        # Punta de flecha triangular rellena según dirección
        if x2 > x1 and abs(y1 - y2) < 2:  # Horizontal derecha
            d.add(Polygon([x2, y2, x2 - 4.5, y2 + 2.5, x2 - 4.5, y2 - 2.5], fillColor=colors.HexColor("#475569"), strokeColor=None))
        elif x2 == x1 and y2 < y1:  # Vertical abajo
            d.add(Polygon([x2, y2, x2 - 2.5, y2 + 4.5, x2 + 2.5, y2 + 4.5], fillColor=colors.HexColor("#475569"), strokeColor=None))
        elif x2 == x1 and y2 > y1:  # Vertical arriba
            d.add(Polygon([x2, y2, x2 - 2.5, y2 - 4.5, x2 + 2.5, y2 - 4.5], fillColor=colors.HexColor("#475569"), strokeColor=None))
        elif x2 > x1 and y2 < y1:  # Diagonal abajo-derecha
            d.add(Polygon([x2, y2, x2 - 4.5, y2 + 3.0, x2 - 3.0, y2 - 3.5], fillColor=colors.HexColor("#475569"), strokeColor=None))
        elif x2 > x1 and y2 > y1:  # Diagonal arriba-derecha
            d.add(Polygon([x2, y2, x2 - 4.5, y2 - 3.0, x2 - 3.0, y2 + 3.5], fillColor=colors.HexColor("#475569"), strokeColor=None))
        else:
            d.add(Polygon([x2, y2, x2 - 4.5, y2 + 2.5, x2 - 4.5, y2 - 2.5], fillColor=colors.HexColor("#475569"), strokeColor=None))

    # Nodos BPMN 2.0 normalizados
    for n in nodos:
        tipo = n["tipo"]
        x, y = n["x"], n["y"]
        if tipo == "inicio":
            d.add(Circle(x, y, 6.5, fillColor=colors.HexColor("#DCFCE7"), strokeColor=colors.HexColor("#16A34A"), strokeWidth=1.5))
            if "label" in n:
                d.add(String(x, y - 10.5, n["label"], textAnchor="middle", fontName="Helvetica-Bold", fontSize=5.0, fillColor=colors.HexColor("#166534")))
        elif tipo == "fin":
            d.add(Circle(x, y, 6.5, fillColor=colors.HexColor("#FEE2E2"), strokeColor=colors.HexColor("#DC2626"), strokeWidth=2.2))
            if "label" in n:
                d.add(String(x, y - 10.5, n["label"], textAnchor="middle", fontName="Helvetica-Bold", fontSize=5.0, fillColor=colors.HexColor("#991B1B")))
        elif tipo == "tarea":
            w_t = n.get("w", 58)
            h_t = n.get("h", 22)
            d.add(Rect(x, y - h_t / 2, w_t, h_t, rx=3, ry=3, fillColor=colors.HexColor("#EFF6FF"), strokeColor=colors.HexColor("#2563EB"), strokeWidth=0.8))
            txts = n.get("texto", ["Actividad"])
            if len(txts) == 1:
                d.add(String(x + w_t / 2, y - 2.0, txts[0], textAnchor="middle", fontName="Helvetica-Bold", fontSize=5.5, fillColor=colors.HexColor("#0F172A")))
            elif len(txts) == 2:
                d.add(String(x + w_t / 2, y + 2.0, txts[0], textAnchor="middle", fontName="Helvetica-Bold", fontSize=5.3, fillColor=colors.HexColor("#0F172A")))
                d.add(String(x + w_t / 2, y - 5.5, txts[1], textAnchor="middle", fontName="Helvetica", fontSize=5.0, fillColor=colors.HexColor("#334155")))
            elif len(txts) >= 3:
                d.add(String(x + w_t / 2, y + 4.5, txts[0], textAnchor="middle", fontName="Helvetica-Bold", fontSize=5.0, fillColor=colors.HexColor("#0F172A")))
                d.add(String(x + w_t / 2, y - 1.5, txts[1], textAnchor="middle", fontName="Helvetica", fontSize=4.8, fillColor=colors.HexColor("#334155")))
                d.add(String(x + w_t / 2, y - 7.0, txts[2], textAnchor="middle", fontName="Helvetica", fontSize=4.8, fillColor=colors.HexColor("#334155")))
        elif tipo == "decision":
            r = 9.0
            d.add(Polygon([x, y + r, x + r, y, x, y - r, x - r, y], fillColor=colors.HexColor("#FEF3C7"), strokeColor=colors.HexColor("#D97706"), strokeWidth=1.0))
            d.add(String(x, y - 2.5, "X", textAnchor="middle", fontName="Helvetica-Bold", fontSize=6.5, fillColor=colors.HexColor("#92400E")))
            if "label" in n:
                d.add(String(x, y + r + 2.0, n["label"], textAnchor="middle", fontName="Helvetica-Bold", fontSize=4.8, fillColor=colors.HexColor("#B45309")))

    return d


def agregar_diagrama_bpmn_apa(
    story: list,
    est: dict,
    num_figura: int,
    titulo_figura: str,
    lanes: list[str],
    nodos: list[dict],
    flujos: list[tuple[float, float, float, float]],
    nota: str = "Modelado de procesos bajo el estándar BPMN 2.0 (OMG) y metodología Bizagi Modeler con carriles (swimlanes) por actor.",
    alto: float = 115,
):
    """Inserta formalmente un diagrama de flujo BPMN 2.0 en el cuerpo del manual bajo formato APA 7 / UPEL."""
    story.append(Paragraph(f"<b>Figura {num_figura}</b>", est["apa_figura_num"]))
    story.append(Paragraph(f"<i>{escape(titulo_figura)}</i>", est["apa_figura_titulo"]))

    dibujo = crear_dibujo_bpmn_swimlanes(titulo_figura, lanes, nodos, flujos, ancho=ANCHO_UTIL, alto=alto)
    story.append(dibujo)
    story.append(Paragraph(f"<i>Nota.</i> {escape(nota)}", est["apa_tabla_nota"]))
    story.append(Spacer(1, 3))


# =============================================================================
# PORTADA, FIRMAS, DISTRIBUCIÓN, ACTAS Y RECURSOS INSTITUCIONALES (ISO 9001)
# =============================================================================
def agregar_portada_iso_upel(
    story: list,
    est: dict,
    codigo_doc: str,
    titulo_doc: str,
    rol_destinatario: str,
    descripcion_alcance: str,
    version: str = "2.1.0",
):
    """Genera la portada formal con control documental ISO 9001 e identificación APA/UPEL."""
    story.append(Spacer(1, 0.2 * cm))

    # Logotipo institucional
    logo_path = Path("src/img/ultratech.png")
    if not logo_path.exists():
        logo_path = Path("assets/favicon.png")
    if logo_path.exists():
        story.append(Image(str(logo_path), width=2.5 * cm, height=2.5 * cm))
        story.append(Spacer(1, 0.2 * cm))
    else:
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("StockAgent · Sistema de Inventario y Control Logístico", est["portada_titulo"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"<b>{escape(titulo_doc)}</b>", est["portada_sub"]))
    story.append(Paragraph(f"Perfil de Aplicación: <b>{escape(rol_destinatario)}</b>", est["h2"]))
    story.append(Spacer(1, 2))

    story.append(HRFlowable(width="75%", thickness=1.5, color=COLOR_ACENTO_ROJO, spaceBefore=2, spaceAfter=5))
    story.append(Paragraph(descripcion_alcance, est["portada_desc"]))
    story.append(Spacer(1, 0.3 * cm))

    # TABLA 1 (APA/UPEL): Ficha de Control Documental
    story.append(Paragraph("<b>Tabla 1</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Ficha Técnica de Control Documental y Aprobación Institucional</i>", est["apa_tabla_titulo"]))

    tabla_control = [
        [
            Paragraph("<b>Código Documental:</b>", est["meta_bold"]),
            Paragraph(codigo_doc, est["meta"]),
            Paragraph("<b>Versión Vigente:</b>", est["meta_bold"]),
            Paragraph(f"v{version}", est["meta"]),
        ],
        [
            Paragraph("<b>Fecha de Vigencia:</b>", est["meta_bold"]),
            Paragraph(datetime.now().strftime("%d/%m/%Y"), est["meta"]),
            Paragraph("<b>Estado del Documento:</b>", est["meta_bold"]),
            Paragraph("Aprobado / Nivel Producción", est["meta"]),
        ],
        [
            Paragraph("<b>Elaborado por:</b>", est["meta_bold"]),
            Paragraph("Ingeniería de Software & Logística", est["meta"]),
            Paragraph("<b>Revisado por:</b>", est["meta_bold"]),
            Paragraph("Aseguramiento de Calidad (QA / ISO)", est["meta"]),
        ],
        [
            Paragraph("<b>Aprobado por:</b>", est["meta_bold"]),
            Paragraph("Gerencia de Operaciones y TI", est["meta"]),
            Paragraph("<b>Clasificación de Seguridad:</b>", est["meta_bold"]),
            Paragraph("Información Interna Confidencial", est["meta"]),
        ],
    ]
    t_ctrl = Table(tabla_control, colWidths=[3.0 * cm, 4.75 * cm, 3.0 * cm, 4.75 * cm])
    aplicar_estilo_tabla_apa(t_ctrl, len(tabla_control))
    story.append(t_ctrl)
    story.append(Paragraph("<i>Nota.</i> Sistema de Gestión Documental de UltraTech S.A. Conforme a las Normas ISO 9001:2015 e ISO/IEC/IEEE 26514:2022.", est["apa_tabla_nota"]))

    story.append(Spacer(1, 0.3 * cm))

    # TABLA 2 (APA/UPEL): Historial de Revisiones
    story.append(Paragraph("<b>Tabla 2</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Historial de Versiones y Trazabilidad de Cambios del Manual</i>", est["apa_tabla_titulo"]))

    headers_rev = [
        Paragraph("<b>Versión</b>", est["th_apa"]),
        Paragraph("<b>Fecha</b>", est["th_apa"]),
        Paragraph("<b>Responsable</b>", est["th_apa"]),
        Paragraph("<b>Descripción Detallada del Cambio / Actualización</b>", est["th_apa"]),
        Paragraph("<b>Aprobador</b>", est["th_apa"]),
    ]
    tabla_rev = [headers_rev]
    filas_rev = [
        ("v1.0.0", "15/01/2026", "Dev Team", "Lanzamiento inicial en arquitectura monopuesto de escritorio.", "Gerencia"),
        ("v1.5.0", "10/05/2026", "Logística / TI", "Incorporación de Mercado Libre DOCX, Rótulos QR continuos y SQLite WAL.", "Operaciones"),
        ("v2.0.0", "18/08/2026", "Dev Team", "Servidor LAN HTTPS Multi-equipo, PWA offline-first y cliente móvil Flutter nativo.", "Dirección TI"),
        (f"v{version}", datetime.now().strftime("%d/%m/%Y"), "Dev Team", "Flujogramas BPMN 2.0 (Bizagi), Firmas ISO 9001 §7.5.2, Gestión Cambio POE-SGC-01 y Acta Inducción.", "Dirección TI"),
    ]
    for r_v, r_f, r_r, r_d, r_a in filas_rev:
        tabla_rev.append([
            Paragraph(f"<b>{r_v}</b>", est["td_apa_bold_center"]),
            Paragraph(r_f, est["td_apa_center"]),
            Paragraph(r_r, est["td_apa"]),
            Paragraph(r_d, est["td_apa"]),
            Paragraph(r_a, est["td_apa_center"]),
        ])
    t_rev = Table(tabla_rev, colWidths=[1.5 * cm, 2.0 * cm, 2.5 * cm, 7.5 * cm, 2.0 * cm])
    aplicar_estilo_tabla_apa(t_rev, len(tabla_rev))
    story.append(t_rev)
    story.append(Paragraph("<i>Nota.</i> Control de versiones gestionado bajo la Cláusula 7.5.3 de la Norma ISO 9001:2015.", est["apa_tabla_nota"]))

    story.append(PageBreak())


def agregar_ficha_procedimiento_apa(
    story: list,
    est: dict,
    num_tabla: int,
    codigo_proc: str,
    nombre_proc: str,
    objetivo: str,
    proveedor: str,
    entrada: str,
    salida: str,
    cliente: str,
    raci: str,
    precondiciones: list[str],
    pasos: list[str],
    postcondiciones: list[str],
    control_calidad: str,
):
    """Inserta un Procedimiento Operativo Estandarizado (SOP) formal con tabla SIPOC reglamentaria APA/UPEL."""
    story.append(Paragraph(f"<b>{escape(codigo_proc)}: {escape(nombre_proc)}</b>", est["h2"]))
    story.append(Paragraph(f"<b>Objetivo Operativo:</b> {escape(objetivo)}", est["body_sangria"]))

    # Tabla SIPOC en formato APA
    story.append(Paragraph(f"<b>Tabla {num_tabla}</b>", est["apa_tabla_num"]))
    story.append(Paragraph(f"<i>Caracterización de Proceso SIPOC y Asignación RACI para {escape(codigo_proc)}</i>", est["apa_tabla_titulo"]))

    sipoc_headers = [
        Paragraph("<b>Proveedor (S)</b>", est["th_apa"]),
        Paragraph("<b>Entrada (I)</b>", est["th_apa"]),
        Paragraph("<b>Salida (O)</b>", est["th_apa"]),
        Paragraph("<b>Cliente / Destino (C)</b>", est["th_apa"]),
        Paragraph("<b>Matriz RACI</b>", est["th_apa"]),
    ]
    sipoc_row = [
        Paragraph(escape(proveedor), est["td_apa"]),
        Paragraph(escape(entrada), est["td_apa"]),
        Paragraph(escape(salida), est["td_apa"]),
        Paragraph(escape(cliente), est["td_apa"]),
        Paragraph(escape(raci), est["td_apa_bold_center"]),
    ]
    t_sipoc = Table([sipoc_headers, sipoc_row], colWidths=[2.8 * cm, 3.5 * cm, 3.7 * cm, 3.2 * cm, 2.3 * cm])
    aplicar_estilo_tabla_apa(t_sipoc, 2)
    story.append(t_sipoc)
    story.append(Paragraph(f"<i>Nota.</i> R: Responsable de ejecución, A: Autoridad de aprobación, C: Consultado, I: Informado.", est["apa_tabla_nota"]))

    # Precondiciones
    if precondiciones:
        story.append(Paragraph("<b>Condiciones Previas del Entorno Operativo:</b>", est["h3"]))
        for pre in precondiciones:
            story.append(Paragraph(f"• {pre}", est["bullet"]))

    # Pasos en redacción impersonal formal UPEL
    story.append(Paragraph("<b>Secuencia Operativa Estandarizada (Paso a Paso):</b>", est["h3"]))
    for p in pasos:
        story.append(Paragraph(f"• {p}", est["bullet"]))

    # Postcondiciones
    if postcondiciones:
        story.append(Paragraph("<b>Resultados y Postcondiciones del Sistema:</b>", est["h3"]))
        for post in postcondiciones:
            story.append(Paragraph(f"• {post}", est["bullet"]))

    story.append(Paragraph(f"<b>Criterio de Aceptación y Validación de Calidad:</b> {escape(control_calidad)}", est["body_sangria"]))
    story.append(Spacer(1, 3))


def agregar_formulario_firmas_autorizadas_iso(story: list, est: dict, num_tabla: int):
    """Inserta el Formulario Gráfico Formal de Firmas Autorizadas y Validación Institucional (ISO 9001 §7.5.2)."""
    story.append(Paragraph(f"<b>Tabla {num_tabla}</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Formulario de Validación Institucional y Firmas Autorizadas (ISO 9001:2015 §7.5.2)</i>", est["apa_tabla_titulo"]))

    headers = [
        Paragraph("<b>ELABORADO POR</b>", est["th_firma"]),
        Paragraph("<b>REVISADO POR</b>", est["th_firma"]),
        Paragraph("<b>APROBADO POR</b>", est["th_firma"]),
    ]
    subheaders = [
        Paragraph("Desarrollo & Procesos de Software", est["sub_firma"]),
        Paragraph("Aseguramiento de Calidad (QA / ISO)", est["sub_firma"]),
        Paragraph("Dirección General de Operaciones y TI", est["sub_firma"]),
    ]
    detalles = [
        Paragraph("<b>Nombre:</b> Ing. Equipo de Desarrollo<br/><b>Cargo:</b> Líder Técnico de Software<br/><b>Fecha:</b> " + datetime.now().strftime("%d/%m/%Y"), est["meta_firma"]),
        Paragraph("<b>Nombre:</b> Lic. Auditoría de Calidad<br/><b>Cargo:</b> Auditor Líder ISO 9001<br/><b>Fecha:</b> " + datetime.now().strftime("%d/%m/%Y"), est["meta_firma"]),
        Paragraph("<b>Nombre:</b> Dirección de Operaciones<br/><b>Cargo:</b> Gerente General de TI y Logística<br/><b>Fecha:</b> " + datetime.now().strftime("%d/%m/%Y"), est["meta_firma"]),
    ]
    cajas_firma = [
        Paragraph("<font color='#2563EB'><b>[ RÚBRICA DIGITAL VALIDADA ]</b></font><br/><i>Ing. Dev Team Lead</i><br/><font size=5 color='#64748B'>SHA-256: 4a9fe821bc7d3a01...e4</font>", est["sig_firma"]),
        Paragraph("<font color='#16A34A'><b>[ SELLO DE CONFORMIDAD QA ]</b></font><br/><i>Lic. Auditoría ISO 9001</i><br/><font size=5 color='#64748B'>Dictamen: CONFORME SIN OBJ.</font>", est["sig_firma"]),
        Paragraph("<font color='#B91C1C'><b>[ AUTORIZACIÓN GERENCIAL ]</b></font><br/><i>Dirección TI & Operaciones</i><br/><font size=5 color='#64748B'>Resolución: RES-2026-STK-088</font>", est["sig_firma"]),
    ]

    ancho_col = ANCHO_UTIL / 3.0
    t_firmas = Table([headers, subheaders, detalles, cajas_firma], colWidths=[ancho_col, ancho_col, ancho_col])
    t_firmas.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, COLOR_BORDE_APA),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, COLOR_BORDE_APA),
        ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, 2), (-1, 2), 0.5, colors.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, 3), (-1, 3), 1.0, COLOR_BORDE_APA),
        ("BOX", (0, 3), (0, 3), 0.6, colors.HexColor("#93C5FD")),
        ("BOX", (1, 3), (1, 3), 0.6, colors.HexColor("#86EFAC")),
        ("BOX", (2, 3), (2, 3), 0.6, colors.HexColor("#FCA5A5")),
        ("BACKGROUND", (0, 3), (0, 3), colors.HexColor("#EFF6FF")),
        ("BACKGROUND", (1, 3), (1, 3), colors.HexColor("#F0FDF4")),
        ("BACKGROUND", (2, 3), (2, 3), colors.HexColor("#FEF2F2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_firmas)
    story.append(Paragraph("<i>Nota.</i> Validación y suscripción electrónica conforme a los requerimientos de información documentada de la Norma ISO 9001:2015 (Cláusula 7.5.2) y directrices de control interno SoD de ISO/IEC 27001.", est["apa_tabla_nota"]))
    story.append(Spacer(1, 3))


def agregar_matriz_distribucion_copias(story: list, est: dict, num_tabla: int):
    """Inserta la matriz de control y distribución de copias controladas (ISO 9001 §7.5.3)."""
    story.append(Paragraph(f"<b>Tabla {num_tabla}</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Matriz de Asignación y Distribución de Copias Controladas</i>", est["apa_tabla_titulo"]))

    headers = [
        Paragraph("<b>Copia N°</b>", est["th_apa"]),
        Paragraph("<b>Destinatario / Custodio</b>", est["th_apa"]),
        Paragraph("<b>Área / Ubicación</b>", est["th_apa"]),
        Paragraph("<b>Soporte / Formato</b>", est["th_apa"]),
        Paragraph("<b>Tipo de Copia</b>", est["th_apa"]),
    ]
    filas = [
        ("Copia 01", "Encargado de Depósito", "Muelle de Carga y Despacho", "Digital / Impreso", "Controlada"),
        ("Copia 02", "Supervisor Administrativo", "Oficina Central de Logística", "Digital (.pdf)", "Controlada"),
        ("Copia 03", "Auditor Interno de Calidad", "Oficina de Aseguramiento ISO", "Digital (.pdf)", "Controlada"),
        ("Copia 04", "Repositorio Central de TI", "Servidor LAN (`/documentacion/`)", "Digital (.pdf)", "Maestra"),
        ("Copia 05", "Personal Operativo y Consulta", "Terminales Web y Móviles", "Pantalla (HTML / PDF)", "No Controlada"),
    ]
    data = [headers]
    for c1, c2, c3, c4, c5 in filas:
        data.append([
            Paragraph(f"<b>{c1}</b>", est["td_apa_bold_center"]),
            Paragraph(c2, est["td_apa"]),
            Paragraph(c3, est["td_apa"]),
            Paragraph(c4, est["td_apa_center"]),
            Paragraph(c5, est["td_apa_bold_center"] if c5 in ("Controlada", "Maestra") else est["td_apa_center"]),
        ])
    t = Table(data, colWidths=[2.0 * cm, 4.0 * cm, 4.5 * cm, 2.5 * cm, 2.5 * cm])
    aplicar_estilo_tabla_apa(t, len(data))
    story.append(t)
    story.append(Paragraph("<i>Nota.</i> Las copias marcadas como 'Controlada' están sujetas a retiro y sustitución automática ante la promulgación de nuevas versiones del manual.", est["apa_tabla_nota"]))
    story.append(Spacer(1, 3))


def agregar_acta_capacitacion_personal(story: list, est: dict, num_tabla: int):
    """Inserta el Acta Oficial de Notificación, Capacitación y Toma de Conocimiento del Personal (ISO 9001 §7.2)."""
    story.append(Paragraph(f"<b>Tabla {num_tabla}</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Acta Oficial de Notificación, Capacitación y Toma de Conocimiento del Personal Operativo (ISO 9001 §7.2)</i>", est["apa_tabla_titulo"]))

    headers = [
        Paragraph("<b>N°</b>", est["th_apa"]),
        Paragraph("<b>Fecha</b>", est["th_apa"]),
        Paragraph("<b>Apellido y Nombre del Empleado</b>", est["th_apa"]),
        Paragraph("<b>DNI / Legajo</b>", est["th_apa"]),
        Paragraph("<b>Puesto / Rol Asignado</b>", est["th_apa"]),
        Paragraph("<b>Firma del Operario</b>", est["th_apa"]),
        Paragraph("<b>Instructor / V°B°</b>", est["th_apa"]),
    ]
    filas_acta = [
        ("01", "____/____/2026", "____________________________________", "_____________", "Operador Depósito", "[________________]", "[________________]"),
        ("02", "____/____/2026", "____________________________________", "_____________", "Operador Depósito", "[________________]", "[________________]"),
        ("03", "____/____/2026", "____________________________________", "_____________", "Supervisor Depósito", "[________________]", "[________________]"),
        ("04", "____/____/2026", "____________________________________", "_____________", "Encargado de Compras", "[________________]", "[________________]"),
        ("05", "____/____/2026", "____________________________________", "_____________", "Administrador", "[________________]", "[________________]"),
    ]
    data_acta = [headers]
    for n, f, nom, leg, rol, fir, ins in filas_acta:
        data_acta.append([
            Paragraph(f"<b>{n}</b>", est["td_apa_center"]),
            Paragraph(f, est["td_apa_center"]),
            Paragraph(nom, est["td_apa"]),
            Paragraph(leg, est["td_apa_center"]),
            Paragraph(rol, est["td_apa"]),
            Paragraph(fir, est["td_apa_center"]),
            Paragraph(ins, est["td_apa_center"]),
        ])
    t_acta = Table(data_acta, colWidths=[1.0 * cm, 2.2 * cm, 4.3 * cm, 2.0 * cm, 2.5 * cm, 1.8 * cm, 1.7 * cm])
    aplicar_estilo_tabla_apa(t_acta, len(data_acta))
    story.append(t_acta)
    story.append(Paragraph(
        "<i>Nota.</i> El personal firmante certifica bajo juramento haber recibido inducción teórico-práctica sobre los procedimientos "
        "establecidos en este manual, comprometiéndose a su estricto cumplimiento operativo y aceptando la responsabilidad sobre la trazabilidad de sus acciones.",
        est["apa_tabla_nota"],
    ))
    story.append(Spacer(1, 3))


def agregar_tarjeta_referencia_rapida(story: list, est: dict):
    """Inserta la Tarjeta Plastificable de Referencia Rápida (Cheat Sheet Operativo)."""
    story.append(Paragraph("Tarjeta de Referencia Rápida para Estaciones de Trabajo (Cheat Sheet)", est["h2"]))
    story.append(Paragraph(
        "Esta carilla sintética está diseñada para su impresión plastificada y exhibición directa en muelle de despacho y estaciones de picking:",
        est["body_sangria"],
    ))

    data_rapida = [
        [Paragraph("<b>Comando / Atajo</b>", est["th_apa"]), Paragraph("<b>Acción Ejecutada</b>", est["th_apa"]), Paragraph("<b>Contexto de Aplicación</b>", est["th_apa"])],
        [Paragraph("<b>Ctrl + K</b> o <b>F2</b>", est["td_apa_bold_center"]), Paragraph("Abre la Paleta de Búsqueda Rápida de artículos en vivo.", est["td_apa"]), Paragraph("Global en cualquier pantalla del sistema.", est["td_apa"])],
        [Paragraph("<b>Enter (en lector)</b>", est["td_apa_bold_center"]), Paragraph("Valida código de barra o QR leído por pistola óptica.", est["td_apa"]), Paragraph("Inventario en Vivo y Carga de Remitos.", est["td_apa"])],
        [Paragraph("<b>Esc</b>", est["td_apa_bold_center"]), Paragraph("Cierra ventanas modales, diálogos emergentes o cancela.", est["td_apa"]), Paragraph("Todos los formularios activos.", est["td_apa"])],
        [Paragraph("<b>Beep 880 Hz (Agudo)</b>", est["td_apa_bold_center"]), Paragraph("Transacción confirmada y stock descontado exitosamente.", est["td_apa"]), Paragraph("Confirmación acústica en depósito ruidoso.", est["td_apa"])],
        [Paragraph("<b>Beep 440 Hz (Medio)</b>", est["td_apa_bold_center"]), Paragraph("Advertencia operativa: artículo en stock mínimo o cercano a quiebre.", est["td_apa"]), Paragraph("Descuento de pedidos y alertas.", est["td_apa"])],
        [Paragraph("<b>Beep 220 Hz (Grave)</b>", est["td_apa_bold_center"]), Paragraph("Error crítico: Hash SHA-256 duplicado o comprobante ya ingresado.", est["td_apa"]), Paragraph("Filtro anti-duplicados.", est["td_apa"])],
    ]
    t_rapida = Table(data_rapida, colWidths=[3.2 * cm, 7.8 * cm, 4.5 * cm])
    aplicar_estilo_tabla_apa(t_rapida, len(data_rapida))
    story.append(t_rapida)
    story.append(Spacer(1, 3))


def agregar_requisitos_infraestructura_iso(story: list, est: dict):
    """Inserta la sección formal de infraestructura técnica y puesto de trabajo conforme a ISO 9001 §7.1.3."""
    story.append(Paragraph("Requisitos de Infraestructura Técnica y Puesto de Trabajo (ISO 9001 §7.1.3)", est["h2"]))
    story.append(Paragraph(
        "Para garantizar la continuidad operativa y la confiabilidad en la ejecución de los procedimientos descritos, "
        "las estaciones de trabajo deben reunir las siguientes condiciones técnicas mínimas:",
        est["body_sangria"],
    ))
    story.append(Paragraph("• <b>Terminal de Cómputo:</b> PC o estación de muelle con arquitectura x86-64 / ARM, mínimo 4 GB RAM y sistema operativo Windows 10/11 o Linux con navegador moderno.", est["bullet"]))
    story.append(Paragraph("• <b>Dispositivo de Captura Óptica:</b> Lector de códigos de barra y QR (1D/2D) interfaz USB o Bluetooth con soporte de emulación de teclado (HID).", est["bullet"]))
    story.append(Paragraph("• <b>Dispositivos de Impresión:</b> Impresora térmica continua de 80 mm para rótulos adhesivos con código QR e impresora láser/inyección para Hojas de Ruta A4.", est["bullet"]))
    story.append(Paragraph("• <b>Conectividad de Red:</b> Enlace LAN Ethernet a 1 Gbps o red Wi-Fi empresarial en banda de 5 GHz con aislamiento de clientes (*Client Isolation*) desactivado hacia el puerto 8550.", est["bullet"]))
    story.append(Paragraph("• <b>Ergonomía y Seguridad (ISO 45001):</b> Iluminación uniforme mínima de 300 lux en zona de picking y empaque, calzado de seguridad con puntera reforzada en muelle.", est["bullet"]))
    story.append(Spacer(1, 3))


def agregar_glosario_terminos_iso_upel(story: list, est: dict):
    """Inserta el glosario terminológico reglamentario según ISO 9000:2015 y manual UPEL."""
    story.append(Paragraph("Glosario de Términos Técnicos y Operativos (ISO 9000 & UPEL)", est["h2"]))
    terminos = [
        ("Algoritmo SHA-256", "Función criptográfica unidireccional que produce un valor hash único de 64 caracteres para certificar la integridad y unicidad absoluta de cada comprobante cargado."),
        ("BPMN 2.0 (Business Process Model and Notation)", "Estándar internacional de notación gráfica para el modelado de procesos de negocio mediante piscinas (*pools*) y carriles de responsabilidad (*swimlanes*)."),
        ("Bulto", "Unidad logística física acondicionada, paletizada y rotulada con código QR correlativo que ampara la mercadería despachada hacia el cliente."),
        ("Modo WAL (Write-Ahead Logging)", "Mecanismo de concurrencia y persistencia de SQLite que garantiza transacciones atómicas seguras evitando el bloqueo entre lecturas y escrituras simultáneas."),
        ("No Conformidad", "Incumplimiento de un requisito preestablecido en el proceso operativo o desviación entre el recuento físico y el saldo digital del sistema."),
        ("POE / SOP (Standard Operating Procedure)", "Procedimiento Operativo Estandarizado que formaliza las instrucciones de trabajo secuenciales para asegurar la uniformidad en la ejecución de tareas."),
        ("RACI", "Matriz de asignación de responsabilidades: R (Responsable ejecutor), A (Aprobador final), C (Consultado técnico) e I (Informado de resultados)."),
        ("Remito", "Comprobante comercial formal de traslado y entrega de mercadería que sustenta contable y operativamente el decremento del inventario."),
        ("Segregación de Funciones (SoD)", "Principio de seguridad (ISO/IEC 27001 §5.3) que distribuye privilegios críticos entre distintos perfiles para mitigar riesgos de fraude o colisión."),
        ("SIPOC", "Herramienta de análisis de procesos que desglosa Proveedor (*Supplier*), Entrada (*Input*), Proceso (*Process*), Salida (*Output*) y Cliente (*Customer*)."),
    ]
    for t_nom, t_def in terminos:
        story.append(Paragraph(f"• <b>{t_nom}:</b> {t_def}", est["bullet"]))
    story.append(Spacer(1, 3))


def agregar_referencias_bibliograficas_apa_upel(story: list, est: dict):
    """Inserta la sección formal de referencias bibliográficas en estilo APA 7ma / UPEL."""
    story.append(Paragraph("Referencias Normativas y Bibliográficas (APA 7.ª ed. / UPEL 5.ª ed.)", est["h2"]))
    referencias = [
        "International Organization for Standardization. (2015). <i>Sistemas de gestión de la calidad — Requisitos</i> (Norma ISO 9001:2015). Ginebra: Secretaría Central de ISO.",
        "International Organization for Standardization & International Electrotechnical Commission. (2022). <i>Seguridad de la información, ciberseguridad y protección de la privacidad — Controles de seguridad de la información</i> (Norma ISO/IEC 27001:2022). Ginebra: ISO/IEC.",
        "ISO/IEC/IEEE. (2022). <i>Systems and software engineering — Requirements for designers and developers of user documentation</i> (ISO/IEC/IEEE Standard No. 26514:2022). Piscataway, NJ: IEEE Standards Association.",
        "Object Management Group. (2011). <i>Business Process Model and Notation (BPMN), Version 2.0</i>. Needham, MA: OMG Document formal/2011-01-03.",
        "Universidad Pedagógica Experimental Libertador. (2022). <i>Manual de trabajos de grado de especialización y maestría y tesis doctorales</i> (5.ª ed.). Caracas: Fondo Editorial de la Universidad Pedagógica Experimental Libertador (FEDUPEL).",
    ]
    for ref in referencias:
        story.append(Paragraph(ref, est["ref_apa"]))
    story.append(Spacer(1, 4))


# =============================================================================
# PROCEDIMIENTO ESTÁNDAR DE GESTIÓN DEL CAMBIO Y ACTUALIZACIÓN (POE-SGC-01)
# =============================================================================
def agregar_procedimiento_gestion_cambio_sgc(story: list, est: dict, num_tabla: int, num_figura: int):
    """Inserta el POE-SGC-01 de Gestión del Cambio y Actualización de Manuales (ISO 9001 §7.5 / §8.5.6)."""
    agregar_ficha_procedimiento_apa(
        story, est, num_tabla,
        "POE-SGC-01", "Gestión del Cambio, Incorporación de Nuevos Módulos y Actualización de Manuales",
        "Estandarizar el ciclo de solicitud, desarrollo, validación y promulgación de modificaciones operativas y nuevos módulos de software.",
        "Cualquier Usuario / Área Operativa", "Solicitud formal de cambio (RFC - Request for Change) o requerimiento técnico",
        "Software actualizado, manuales recompilados en PDF con control de versiones y personal capacitado", "Toda la Organización",
        "R: Líder TI & QA | A: Dirección General | C: Operarios | I: Toda la Organización",
        ["El requerimiento cuenta con justificación operativa.", "El código fuente se encuentra versionado en repositorio Git."],
        [
            "<b>1. Solicitud Formal (RFC):</b> Se completa el formulario de solicitud de cambio detallando la necesidad operativa o nuevo módulo.",
            "<b>2. Evaluación de Impacto y Seguridad SoD:</b> El Oficial de Seguridad y el Líder Técnico evalúan que el cambio no viole la Segregación de Funciones (ISO 27001).",
            "<b>3. Desarrollo y Documentación Concurrente:</b> Toda modificación en el código fuente (`src/`) debe ir acompañada en el mismo sprint de la actualización en `Documentacion/generar_manual_pdf.py`.",
            "<b>4. Auditoría QA y Pruebas Automatizadas:</b> Se ejecutan los tests de regresión (`pytest`) y se valida que los manuales cumplan las pautas ISO, BPMN y APA/UPEL.",
            "<b>5. Aprobación y Firma Electrónica:</b> La Dirección de Operaciones y TI aprueba formalmente e incrementa la versión semántica (v2.1 -> v2.2).",
            "<b>6. Compilación y Despliegue Zero-Cache:</b> Se compilan los PDFs y se despliegan en el servidor `/documentacion/` con cabeceras anti-caché y parámetro de timestamp (`?v={ts}`).",
            "<b>7. Retiro de Documentación Obsoleta:</b> Se retiran las copias impresas previas y se archivan digitalmente con marca de agua 'OBSOLETO' (ISO 9001 §7.5.3.2).",
            "<b>8. Jornada de Capacitación:</b> Se adiestra al personal afectado y se suscribe el Acta Oficial de Notificación y Toma de Conocimiento.",
        ],
        ["Manuales disponibles en el botón 'Manual de Uso'.", "Actas de capacitación firmadas y archivadas."],
        "Aprobación formal de las tres autoridades y 100% de tests automatizados aprobados en verde.",
    )

    # FIGURA BPMN 2.0 para POE-SGC-01
    agregar_diagrama_bpmn_apa(
        story, est, num_figura,
        "Flujograma BPMN 2.0: Ciclo de Gestión del Cambio y Actualización Documental (POE-SGC-01)",
        lanes=["Área Solicitante", "Ingeniería de Software", "Calidad QA & Dirección"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Solicitud RFC"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Emitir Petición", "Fundamentar"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Desarrollar Módulo", "Actualizar Doc"]},
            {"tipo": "decision", "x": 280, "y": 19, "label": "¿Auditoría QA?"},
            {"tipo": "tarea", "x": 310, "y": 19, "w": 62, "h": 22, "texto": ["Aprobar Versión", "Firmar Acta"]},
            {"tipo": "fin", "x": 410, "y": 58, "label": "Despliegue"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 280, 19),
            (289, 19, 310, 19),
            (372, 19, 403, 58),
        ],
    )


# =============================================================================
# 1. MANUAL ROL OPERADOR (ISO 26514, ISO 9001, BPMN 2.0 & APA/UPEL)
# =============================================================================
def construir_manual_operador(ruta_destino: Path) -> Path:
    """Compila el Manual del Rol Operador bajo Normas ISO, BPMN y APA/UPEL."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(ruta_destino), pagesize=A4, leftMargin=MARGEN_IZQ, rightMargin=MARGEN_DER, topMargin=MARGEN_SUP, bottomMargin=MARGEN_INF)
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "SOP-STK-OPE-2026-v2.1"
    titulo_doc = "Manual de Procedimientos de Depósito (Rol Operador)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Operador (Preparación de Pedidos, Rotulación y Despacho)",
        "Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015, ISO/IEC/IEEE 26514:2022,<br/>"
        "modelado BPMN 2.0 estilo Bizagi y pautas metodológicas UPEL (5ta ed.) para el procesamiento de remitos, Mercado Libre y cierre",
        version="2.1.0",
    )

    # CAPÍTULO 1
    story.append(Paragraph("1. Marco Normativo, Alcance y Responsabilidades (ISO 9001 §4.3 & §5.3)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "El presente manual tiene por objeto formalizar y estandarizar las actividades operativas de recepción "
        "de comprobantes, validación criptográfica anti-duplicados (SHA-256), descuento atómico de inventario, "
        "rotulación de bultos mediante códigos ópticos QR y despacho controlado hacia los transportistas.",
        est["body_sangria"],
    ))
    story.append(Paragraph(
        "El alcance del documento comprende al personal de depósito asignado a la preparación de pedidos, "
        "empaque y entrega en muelle de despacho, de conformidad con las directrices de la Norma ISO 9001:2015 "
        "(Cláusulas 8.1 y 8.5.2) y el Manual de Trabajos de Grado de la UPEL en cuanto a rigor metodológico y estilo.",
        est["body_sangria"],
    ))

    story.append(Spacer(1, 2))
    story.append(crear_caja_alerta_iso(
        "EXCLUSIVIDAD OPERACIONAL SoD (ISO/IEC 27001 §5.3)",
        "Por expresa disposición de control interno y segregación de funciones (SoD), el operario posee la facultad "
        "<b>exclusiva</b> de modificar bultos, transportes, clientes y fechas en pedidos preparados. "
        "Se prohíbe la alteración remota por parte de supervisores administrativos para evitar discordancias con la mercadería física paletizada.",
        "sod",
    ))

    # CAPÍTULO 2: FICHAS DE PROCEDIMIENTOS ESTANDARIZADOS (APA/UPEL + BPMN)
    story.append(Spacer(1, 4))
    story.append(Paragraph("2. Procedimientos Operativos Estandarizados (SOP / POE)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    # POE-OPE-01
    agregar_ficha_procedimiento_apa(
        story, est, 3,
        "POE-OPE-01", "Carga y Descuento de Remitos Mayoristas (PDF) y Canjes (Excel)",
        "Descontar existencias y asentar el pedido en la jornada de forma atómica en SQLite y Productos.xlsx.",
        "Área Comercial / Clientes", "Remito digital (.pdf) o Planilla de Canje (.xlsx)",
        "Pedido registrado, stock decrementado, hash SHA-256 asentado", "Transporte / Empaque",
        "R: Operario | A: Administrador | I: Chofer",
        ["El servidor web se encuentra activo en el puerto 8550.", "El catálogo maestro se encuentra plenamente sincronizado."],
        [
            "Se procede a pulsar el comando <b>'Seleccionar archivo'</b> para adjuntar el comprobante (.pdf o .xlsx).",
            "Se constata que el sistema haya extraído y separado con exactitud el código numérico de la razón social (ej. <code>00714 - DIETETICA SABORES</code>).",
            "Se gradúa la cantidad de bultos acondicionados mediante los pulsadores <code>[-]</code> y <code>[+]</code> (mínimo un bulto).",
            "Se selecciona con carácter obligatorio la empresa de transporte en el menú desplegable de logística.",
            "Se valida la fecha de retiro, la cual es pre-completada por el motor a partir de la fecha de despacho del documento.",
            "Se pulsa el botón <b>'Cargar y Descontar'</b>. El sistema emite una señal acústica en 880 Hz que certifica la transacción.",
        ],
        ["El pedido se asienta en la tabla `pedidos` con cierre_id = NULL.", "El archivo binario se almacena en `data/pedidos_archivos/`."],
        "El comprobante no debe registrar coincidencia previa de hash SHA-256 y el inventario resultante debe ser mayor o igual a cero.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 1,
        "Flujograma de Proceso BPMN 2.0: Carga y Descuento de Remitos (POE-OPE-01)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Muelle / Despacho"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Remito"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Adjuntar Remito", "Ajustar Bultos"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Validar SHA-256", "Descontar Stock"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Duplicado?"},
            {"tipo": "tarea", "x": 310, "y": 96, "w": 60, "h": 22, "texto": ["Imprimir Rótulo", "Paletizar Bulto"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Muelle OK"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 271, 58),
            (289, 58, 310, 96),
            (370, 96, 403, 19),
        ],
    )

    story.append(PageBreak())

    # POE-OPE-02
    agregar_ficha_procedimiento_apa(
        story, est, 4,
        "POE-OPE-02", "Descuento Masivo de Mercado Libre Full (Planilla Excel)",
        "Procesar planillas oficiales de despacho Full directamente desde el menú lateral de depósito.",
        "Mercado Libre / Depósito", "Planilla oficial de despacho Full (.xlsx / .xls)",
        "Descuento consolidado en bloque, actualización de Productos.xlsx", "Jefatura de Operaciones",
        "R: Operario | A: Administrador | I: Depósito Full",
        ["La planilla oficial de Mercado Libre Full ha sido descargada de la plataforma.", "Sesión de Operador autenticada."],
        [
            "En la barra de navegación lateral, se pulsa el botón <b>'Descontar Mercado Full'</b>.",
            "Se selecciona el archivo Excel oficial suministrado por Mercado Libre.",
            "El sistema procesa automáticamente las columnas y muestra la vista previa con el total de artículos a descontar.",
            "Se confirma la operación. El motor descuenta el inventario de forma consolidada en una sola transacción.",
            "Se verifica el mensaje de éxito en pantalla y se actualiza la copia de Productos.xlsx.",
        ],
        ["Existencias actualizadas en SQLite (`productos.sqlite3`) y en `Productos.xlsx`.", "Movimiento registrado en `stock_movements`."],
        "Concordancia entre los totales de la planilla y las unidades decrementadas sin errores de lectura.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 2,
        "Flujograma de Proceso BPMN 2.0: Descuento Masivo Mercado Libre Full (POE-OPE-02)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Mercado Libre Full"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Planilla"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Abrir Menú Full", "Adjuntar Excel"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Parsear Columnas", "Verificar Stock"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Stock OK?"},
            {"tipo": "tarea", "x": 310, "y": 58, "w": 62, "h": 22, "texto": ["Descuento Bloque", "Actualizar Excel"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Full Listo"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 271, 58),
            (289, 58, 310, 58),
            (372, 58, 403, 19),
        ],
    )

    # POE-OPE-03
    agregar_ficha_procedimiento_apa(
        story, est, 5,
        "POE-OPE-03", "Rotulación Térmica Continua y Validación de Códigos QR",
        "Generar e imprimir etiquetas adhesivas individuales por cada bulto acondicionado.",
        "Pedido descontado en POE-OPE-01", "Identificador de pedido (`pedido_id`) y cantidad de bultos",
        "Rótulos QR impresos (80 mm continuo), bultos identificados", "Transportista / Cliente",
        "R: Operario | I: Transporte",
        ["La impresora térmica de 80 mm se encuentra encendida y con papel continuo cargado."],
        [
            "En la vista de Pedidos Preparados, se ubica el comprobante y se pulsa el botón <b>'Ver Rótulos'</b>.",
            "El sistema genera una secuencia de etiquetas optimizada para rollo térmico continuo (ancho 80 mm).",
            "Cada etiqueta incluye código QR de alta resolución con el remito y el correlativo del bulto (ej. <code>Bulto 1 de 3</code>).",
            "Se adhiere cada rótulo sobre la cara superior visible del bulto correspondiente.",
            "Se efectúa un escaneo de prueba con la pistola óptica o celular para certificar legibilidad inmediata.",
        ],
        ["Código QR legible mediante pistola óptica o dispositivo móvil."],
        "Lectura satisfactoria del código QR constatando número de remito y correlativo de bulto.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 3,
        "Flujograma de Proceso BPMN 2.0: Rotulación Térmica y Validación QR (POE-OPE-03)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Paletizado Físico"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Bultos"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Ubicar Pedido", "Pulsar Ver QR"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Generar Vector QR", "Correlativo 1..N"]},
            {"tipo": "tarea", "x": 280, "y": 96, "w": 60, "h": 22, "texto": ["Impresión 80mm", "Validar Pistola"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Rotulado OK"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 280, 96),
            (340, 96, 403, 19),
        ],
    )

    story.append(PageBreak())

    # POE-OPE-04
    agregar_ficha_procedimiento_apa(
        story, est, 6,
        "POE-OPE-04", "Despacho en Lote, Notificación WhatsApp y Cierre de Jornada",
        "Controlar la entrega formal al transportista y consolidar los movimientos del turno de trabajo.",
        "Tarimas de empaque listas", "Pedidos preparados pendientes de retiro",
        "Informe Oficial de Cierre (PDF/Excel), Hojas de Ruta por transporte firmadas", "Gerencia / Administración",
        "R: Operario | A: Administrador | I: Chofer / Transportista",
        ["El turno operacional ha finalizado.", "La totalidad de pedidos preparados ha sido verificada en muelle."],
        [
            "En el Historial de Pedidos, se filtra la vista por 'Pendientes de Cierre'. Se marcan los pedidos entregados al chofer.",
            "Se pulsa el botón <b>'Despachar Seleccionados'</b> para transicionar los pedidos a estado DESPACHADO.",
            "Se ingresa el N° de guía del expreso y se pulsa el icono de WhatsApp para despachar el mensaje formal al cliente.",
            "Se acciona el comando <b>'Cierre de Jornada'</b>. El sistema consolida los descuentos evitando duplicidades.",
            "Se imprimen las Hojas de Ruta individuales por transporte y se recaba la firma de conformidad del chofer.",
            "Se verifica que los contadores del panel principal retornen a cero para la recepción del siguiente turno.",
        ],
        ["Los pedidos quedan vinculados al número único de cierre (`cierre_id`).", "Se genera el respaldo automático en `data/backups/`."],
        "Conformidad física del transportista estampada en la Hoja de Ruta con firma, aclaración y fecha legible.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 4,
        "Flujograma de Proceso BPMN 2.0: Despacho en Lote y Cierre de Jornada (POE-OPE-04)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Transportista / Chofer"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Fin Turno"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Marcar Salida", "Cierre Jornada"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Asignar CierreID", "Generar Hojas"]},
            {"tipo": "tarea", "x": 280, "y": 19, "w": 60, "h": 22, "texto": ["Recibir Carga", "Firmar Hoja Ruta"]},
            {"tipo": "fin", "x": 410, "y": 58, "label": "Backup OK"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 280, 19),
            (340, 19, 403, 58),
        ],
    )

    # CAPÍTULO 3: CONTROL DE REGISTROS DE CALIDAD (ISO 9001 §7.5.3)
    story.append(PageBreak())
    story.append(Paragraph("3. Control de Registros de Calidad y Evidencias (ISO 9001:2015 §7.5.3)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "A continuación se presenta la matriz de control de información documentada y registros de calidad "
        "generados durante la ejecución de los procedimientos de depósito, conforme a la Cláusula 7.5.3 de la Norma ISO 9001:2015:",
        est["body_sangria"],
    ))

    story.append(Paragraph("<b>Tabla 7</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Matriz de Control y Retención de Registros de Calidad Operacionales</i>", est["apa_tabla_titulo"]))

    headers_reg = [
        Paragraph("<b>Registro de Calidad</b>", est["th_apa"]),
        Paragraph("<b>Soporte</b>", est["th_apa"]),
        Paragraph("<b>Ubicación de Custodia</b>", est["th_apa"]),
        Paragraph("<b>Retención</b>", est["th_apa"]),
        Paragraph("<b>Responsable</b>", est["th_apa"]),
    ]
    filas_reg = [
        ("Transacción de Pedido y Descuento", "Digital (SQLite)", "data/pedidos.sqlite3 (tabla `pedidos`)", "5 Años", "Administrador / Master"),
        ("Comprobante Digitalizado (PDF/Excel)", "Archivo binario", "data/pedidos_archivos/", "5 Años", "Administrador"),
        ("Hoja de Ruta Firmada por Chofer", "Documento papel", "Archivador de Logística en Depósito", "2 Años", "Encargado de Despacho"),
        ("Informe Consolidado de Cierre", "PDF y XLS", "Descuentos/ y data/pedidos_archivos/", "5 Años", "Jefe de Depósito"),
        ("Copia de Seguridad Integral", "Archivo .zip", "data/backups/ y Mirror en Red", "1 Año (Rotación 30)", "Master"),
    ]
    t_reg_data = [headers_reg]
    for r1, r2, r3, r4, r5 in filas_reg:
        t_reg_data.append([Paragraph(f"<b>{r1}</b>", est["td_apa"]), Paragraph(r2, est["td_apa_center"]), Paragraph(r3, est["td_apa"]), Paragraph(r4, est["td_apa_center"]), Paragraph(r5, est["td_apa"])])
    t_reg = Table(t_reg_data, colWidths=[3.8 * cm, 2.2 * cm, 4.2 * cm, 2.0 * cm, 3.3 * cm])
    aplicar_estilo_tabla_apa(t_reg, len(t_reg_data))
    story.append(t_reg)
    story.append(Paragraph("<i>Nota.</i> Tiempos de retención fijados según requerimientos legales fiscales y de auditoría interna de calidad.", est["apa_tabla_nota"]))

    # CAPÍTULO 4: GESTIÓN DE NO CONFORMIDADES (ISO 9001 §10.2)
    story.append(Spacer(1, 4))
    story.append(Paragraph("4. Gestión de No Conformidades y Errores (ISO 9001:2015 §10.2)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "Ante la detección de desviaciones operacionales o errores del sistema, el personal de depósito "
        "debe aplicar las acciones correctivas descritas en la Tabla 8:",
        est["body_sangria"],
    ))

    story.append(Paragraph("<b>Tabla 8</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Matriz de Tratamiento de No Conformidades y Acciones Correctivas</i>", est["apa_tabla_titulo"]))

    headers_err = [
        Paragraph("<b>No Conformidad</b>", est["th_apa"]),
        Paragraph("<b>Causa Raíz</b>", est["th_apa"]),
        Paragraph("<b>Acción Inmediata (Corrección)</b>", est["th_apa"]),
        Paragraph("<b>Acción Preventiva</b>", est["th_apa"]),
    ]
    filas_err = [
        ("NC-OPE-01: Hash Duplicado", "Reingreso involuntario de comprobante.", "El sistema rechaza la carga informando fecha previa.", "Revisar Historial. La modificación de nombre no evade SHA-256."),
        ("NC-OPE-02: Quiebre de Stock", "Demanda superior al saldo en SQLite.", "El sistema abre advertencia previa de confirmación.", "Autorizar solo si hay ingreso pendiente o solicitar a Compras."),
        ("NC-OPE-03: Desarme por Rechazo", "Cancelación de pedido por cliente.", "Presionar botón ámbar 'Desarmar pedido'.", "El stock retorna al instante a SQLite y Productos.xlsx con log."),
        ("NC-OPE-04: Falla de Red Wi-Fi", "Microcorte o zona ciega en depósito.", "Continuar escaneando en 'Inventario en Vivo'.", "El búfer local (localStorage) transmite las lecturas al reconectar."),
    ]
    t_err_data = [headers_err]
    for e1, e2, e3, e4 in filas_err:
        t_err_data.append([Paragraph(f"<b>{e1}</b>", est["td_apa_bold_center"]), Paragraph(e2, est["td_apa"]), Paragraph(e3, est["td_apa"]), Paragraph(e4, est["td_apa"])])
    t_err = Table(t_err_data, colWidths=[3.0 * cm, 3.5 * cm, 4.5 * cm, 4.5 * cm])
    aplicar_estilo_tabla_apa(t_err, len(t_err_data))
    story.append(t_err)
    story.append(Paragraph("<i>Nota.</i> Procedimiento alineado con la Cláusula 10.2 (Acciones Correctivas) de la Norma ISO 9001:2015.", est["apa_tabla_nota"]))

    # CAPÍTULO 5: INDICADORES KPIS (ISO 9001 §9.1)
    story.append(Spacer(1, 4))
    story.append(Paragraph("5. Indicadores de Desempeño y Calidad Operacional (KPIs - ISO 9001 §9.1)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    story.append(Paragraph("<b>Tabla 9</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Indicadores Clave de Desempeño Operacional de Depósito</i>", est["apa_tabla_titulo"]))

    headers_kpi = [
        Paragraph("<b>Indicador (KPI)</b>", est["th_apa"]),
        Paragraph("<b>Objetivo</b>", est["th_apa"]),
        Paragraph("<b>Fórmula de Medición</b>", est["th_apa"]),
        Paragraph("<b>Meta</b>", est["th_apa"]),
        Paragraph("<b>Frecuencia</b>", est["th_apa"]),
    ]
    filas_kpi = [
        ("Tiempo de Carga", "Velocidad de procesamiento por remito.", "Minutos transcurridos desde subida a rotulación.", "< 45 seg.", "Continua"),
        ("Filtro SHA-256", "Efectividad anti-duplicados.", "(Duplicados interceptados / Total intentos) * 100", "100%", "Por Jornada"),
        ("Exactitud Empaque", "Concordancia bultos físicos vs remito.", "(Pedidos modificados / Total pedidos) * 100", "< 2%", "Mensual"),
    ]
    t_kpi_data = [headers_kpi]
    for k1, k2, k3, k4, k5 in filas_kpi:
        t_kpi_data.append([Paragraph(f"<b>{k1}</b>", est["td_apa_bold_center"]), Paragraph(k2, est["td_apa"]), Paragraph(k3, est["td_apa"]), Paragraph(k4, est["td_apa_center"]), Paragraph(k5, est["td_apa_center"])])
    t_kpi = Table(t_kpi_data, colWidths=[3.2 * cm, 3.5 * cm, 4.2 * cm, 2.3 * cm, 2.3 * cm])
    aplicar_estilo_tabla_apa(t_kpi, len(t_kpi_data))
    story.append(t_kpi)
    story.append(Paragraph("<i>Nota.</i> Medición evaluada mensualmente por la Jefatura de Calidad y Operaciones.", est["apa_tabla_nota"]))

    # SECCIONES FINALES NORMALIZADAS (INFRAESTRUCTURA, DISTRIBUCIÓN, FIRMAS, ACTA, CHEAT SHEET, GLOSARIO Y REFERENCIAS)
    story.append(PageBreak())
    story.append(Paragraph("6. Marco Técnico de Infraestructura y Control Institucional", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 10)
    agregar_formulario_firmas_autorizadas_iso(story, est, 11)

    story.append(PageBreak())
    story.append(Paragraph("7. Registros de Inducción, Referencia Rápida y Terminología", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_acta_capacitacion_personal(story, est, 12)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "v2.1.0"))
    return ruta_destino


# =============================================================================
# 2. MANUAL ROL ADMINISTRADOR (ISO 26514, ISO 9001, BPMN 2.0 & APA/UPEL)
# =============================================================================
def construir_manual_administrador(ruta_destino: Path) -> Path:
    """Compila el Manual del Rol Administrador bajo Normas ISO, BPMN y APA/UPEL."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(ruta_destino), pagesize=A4, leftMargin=MARGEN_IZQ, rightMargin=MARGEN_DER, topMargin=MARGEN_SUP, bottomMargin=MARGEN_INF)
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "SOP-STK-ADM-2026-v2.1"
    titulo_doc = "Manual de Supervisión y Logística (Rol Administrador)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Administrador (Jefatura de Depósito, Compras y Supervisión)",
        "Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015, ISO/IEC/IEEE 26514:2022,<br/>"
        "modelado BPMN 2.0 (Bizagi) y pautas metodológicas UPEL para catálogo maestro, entradas de fábrica, analítica y gestión IAM",
        version="2.1.0",
    )

    story.append(Paragraph("1. Marco Normativo, Alcance y Responsabilidades (ISO 9001 §4.3 & §5.3)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "El presente documento normaliza las atribuciones de supervisión analítica, administración del catálogo maestro "
        "de existencias (`Productos.xlsx`), gestión de compras sugeridas a proveedores, conciliación de inventarios físicos "
        "y administración de cuentas de operarios en StockAgent.",
        est["body_sangria"],
    ))
    story.append(Paragraph(
        "Aplica formalmente a la Jefatura de Depósito, Encargados de Compras y Gerencia de Operaciones, "
        "garantizando la integridad transaccional de los datos y el cumplimiento de las metas de abastecimiento.",
        est["body_sangria"],
    ))

    story.append(Spacer(1, 2))
    story.append(crear_caja_alerta_iso(
        "POLÍTICA SoD: DELEGACIÓN DE RESTAURACIÓN A MASTER (ISO 27001)",
        "Por normativa de inmutabilidad contable y segregación de funciones, la potestad de <b>Restauración de Documentos</b> "
        "ha sido delegada con exclusividad al perfil <b>Master</b>. El Administrador supervisa y gestiona, pero no puede revertir "
        "lotes históricos sin intervención técnica autorizada.",
        "sod",
    ))

    story.append(Spacer(1, 4))
    story.append(Paragraph("2. Procedimientos de Supervisión Estandarizados (SOP / POE)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    # POE-ADM-01
    agregar_ficha_procedimiento_apa(
        story, est, 3,
        "POE-ADM-01", "Gestión del Catálogo Maestro y Parámetros de Seguridad",
        "Mantener actualizadas las fichas técnicas de productos, códigos de barra, precios y niveles de stock de seguridad.",
        "Compras / Proveedores", "Ficha técnica de producto, alta de nuevos códigos",
        "Catálogo maestro actualizado en SQLite y respaldo en Productos.xlsx", "Depósito / Ventas",
        "R: Administrador | A: Gerencia | I: Operarios",
        ["Sesión de Administrador activa.", "Respaldo automático previo de Productos.xlsx en disco."],
        [
            "En la sección 'Gestionar productos', se procede a dar de alta artículos indicando SKU, descripción y barras.",
            "Se define el <b>Stock Mínimo</b> (disparador automático de alertas de compra) y el <b>Stock Máximo</b>.",
            "Se asigna la ubicación física en estantería (Rack A-D, Módulo 1-4, Nivel 1-3) para optimizar el picking.",
            "Se pulsa el botón <b>'Sincronizar con Excel'</b> para volcar todos los saldos atómicamente a Productos.xlsx.",
        ],
        ["Artículos activos en SQLite y Excel.", "Trazabilidad de alta asentada en auditoría forense."],
        "Correspondencia unívoca entre SKU y descripción sin solapamiento de registros.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 1,
        "Flujograma de Proceso BPMN 2.0: Gestión de Catálogo y Parámetros (POE-ADM-01)",
        lanes=["Administrador", "Sistema StockAgent", "Almacén Central"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Alta SKU"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Definir SKU/Barras", "Fijar Stock Mín."]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Validar Duplicidad", "Guardar SQLite"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Sincronizar?"},
            {"tipo": "tarea", "x": 310, "y": 58, "w": 62, "h": 22, "texto": ["Volcar a Excel", "Asentar Audit"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Catálogo OK"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 271, 58),
            (289, 58, 310, 58),
            (372, 58, 403, 19),
        ],
    )

    story.append(PageBreak())

    # POE-ADM-02
    agregar_ficha_procedimiento_apa(
        story, est, 4,
        "POE-ADM-02", "Recepción de Fábrica, Ajustes y Comparativa de Stock Físico",
        "Incorporar mercadería recibida y conciliar diferencias entre recuento físico y saldo digital.",
        "Fábrica / Proveedores", "Remito de fábrica (.xlsx, .xls o .pdf) o planilla de recuento",
        "Stock incrementado, reporte comparativo (COINCIDE/FALTANTE/SOBRANTE)", "Auditoría / Contabilidad",
        "R: Administrador | A: Gerencia",
        ["La mercadería física se encuentra en muelle de carga debidamente paletizada."],
        [
            "En 'Ajustar stock / Entrada Fábrica', se carga la planilla del proveedor para sumar existencias en lote.",
            "Para mermas o roturas, se ingresa el código y cantidad negativa adjuntando motivo justificatorio.",
            "Para inventarios masivos: se adjunta la planilla de recuento en 'Comparativa stock físico' y se presiona 'Comparar'.",
            "Se exporta el reporte comparativo oficial en PDF/Excel para sustento contable y auditoría de inventarios.",
        ],
        ["Existencias actualizadas en SQLite.", "Asiento de movimiento registrado en `stock_movements`."],
        "Ausencia de discrepancias no justificadas entre comprobante mayorista y stock digital.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 2,
        "Flujograma de Proceso BPMN 2.0: Entrada de Fábrica y Comparativa (POE-ADM-02)",
        lanes=["Administrador", "Sistema StockAgent", "Auditoría Contable"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Recepción"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Adjuntar Remito", "Ejecutar Entrada"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Incrementar Saldo", "Generar Asiento"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Discrepancia?"},
            {"tipo": "tarea", "x": 310, "y": 19, "w": 62, "h": 22, "texto": ["Emitir Comparativo", "Reportar Merma"]},
            {"tipo": "fin", "x": 410, "y": 58, "label": "Stock Ajustado"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 271, 58),
            (289, 58, 310, 19),
            (372, 19, 403, 58),
        ],
    )

    # POE-ADM-03
    agregar_ficha_procedimiento_apa(
        story, est, 5,
        "POE-ADM-03", "Generación Automática de Pedido a Fábrica (Planilla de Reposición)",
        "Calcular la reposición óptima de artículos en quiebre o cercanos al stock mínimo.",
        "Bases SQLite (saldos vigentes)", "Umbrales de stock mínimo/máximo configurados",
        "Planilla Excel oficial con formato corporativo de pedido a proveedores", "Proveedores / Compras",
        "R: Administrador | A: Gerencia Operaciones",
        ["Catálogo maestro debidamente parametrizado con niveles de stock de seguridad."],
        [
            "En el menú de navegación lateral, se pulsa <b>'Generar pedido fábrica (Excel)'</b>.",
            "El sistema filtra automáticamente los artículos en quiebre o con saldo inferior al stock mínimo.",
            "Se examinan las cantidades calculadas y se efectúan ajustes estacionales si correspondiere.",
            "Se presiona el comando <b>'Generar Pedido a Fábrica'</b> y se descarga la planilla oficial para compras.",
        ],
        ["Planilla formal exportada en la carpeta Descuentos/.", "Registro de la solicitud en el historial."],
        "Cantidad sugerida suficiente para cubrir el período de abastecimiento sin superar el stock máximo.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 3,
        "Flujograma de Proceso BPMN 2.0: Pedido Automático a Proveedores (POE-ADM-03)",
        lanes=["Administrador", "Sistema StockAgent", "Área de Compras"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Quiebre"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Filtrar Saldos", "Calcular Brechas"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Demanda OK?"},
            {"tipo": "tarea", "x": 230, "y": 96, "w": 62, "h": 22, "texto": ["Revisión Supervisor", "Ajuste Estacional"]},
            {"tipo": "tarea", "x": 315, "y": 19, "w": 62, "h": 22, "texto": ["Exportar Excel", "Despachar a Fab."]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Pedido Listo"},
        ],
        flujos=[
            (111.5, 96, 118, 58),
            (176, 58, 186, 58),
            (204, 58, 230, 96),
            (292, 96, 315, 19),
            (377, 19, 403, 19),
        ],
    )

    story.append(PageBreak())

    # POE-ADM-04
    agregar_ficha_procedimiento_apa(
        story, est, 6,
        "POE-ADM-04", "Analítica, Radar de Anomalías y Optimización de Picking (Slotting ABC)",
        "Supervisar desvíos de demanda y optimizar la disposición espacial ergonómica del depósito.",
        "Historial de movimientos (`stock_movements`)", "Historial de pedidos despachados",
        "Alertas tempranas de agotamiento, mapa de calor térmico, plan de reubicación", "Jefatura de Depósito",
        "R: Administrador | I: Operarios",
        ["Registro histórico mínimo de 14 días para análisis estadístico representativo."],
        [
            "En 'Radar de anomalías', se monitorean picos de demanda (> μ + 2σ) y coberturas críticas menores a tres días.",
            "En 'Heatmap y Picking', se inspecciona la matriz Pareto ABC (75% A, 15% B, 10% C).",
            "Se constata la ubicación de artículos Clase A. Se pulsa <b>'Reubicar'</b> hacia la <i>Golden Zone</i> ergonómica.",
        ],
        ["Ubicaciones físicas actualizadas en SQLite.", "Disminución comprobada en los tiempos de recorrido de operarios."],
        "Índice de eficiencia de slotting superior al 85% y reducción de fatiga en operarios.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 4,
        "Flujograma de Proceso BPMN 2.0: Radar de Anomalías y Slotting (POE-ADM-04)",
        lanes=["Administrador", "Sistema StockAgent", "Depósito Operativo"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Supervisión"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Evaluar Pareto ABC", "Detectar Desvíos"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Anomalía?"},
            {"tipo": "tarea", "x": 230, "y": 96, "w": 62, "h": 22, "texto": ["Ajustar Slotting", "Golden Zone"]},
            {"tipo": "tarea", "x": 315, "y": 19, "w": 62, "h": 22, "texto": ["Reubicar Racks", "Notificar Operador"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Picking OK"},
        ],
        flujos=[
            (111.5, 96, 118, 58),
            (176, 58, 186, 58),
            (204, 58, 230, 96),
            (292, 96, 315, 19),
            (377, 19, 403, 19),
        ],
    )

    # CAPÍTULO 3: REGISTROS Y NO CONFORMIDADES (APA/UPEL)
    story.append(PageBreak())
    story.append(Paragraph("3. Control de Registros y No Conformidades Administrativas (ISO 9001 §7.5.3 & §10.2)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    story.append(Paragraph("<b>Tabla 7</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Matriz de Control de Registros de Calidad para el Rol Administrador</i>", est["apa_tabla_titulo"]))

    headers_radm = [
        Paragraph("<b>Registro de Calidad</b>", est["th_apa"]),
        Paragraph("<b>Soporte</b>", est["th_apa"]),
        Paragraph("<b>Ubicación de Custodia</b>", est["th_apa"]),
        Paragraph("<b>Retención</b>", est["th_apa"]),
        Paragraph("<b>Responsable</b>", est["th_apa"]),
    ]
    filas_radm = [
        ("Planilla de Entrada de Fábrica", "Digital (.xlsx/.pdf)", "data/pedidos_archivos/", "5 Años", "Jefe de Depósito"),
        ("Planilla de Pedido a Fábrica", "Digital (.xlsx)", "Descuentos/", "3 Años", "Encargado de Compras"),
        ("Informe Comparativo Stock Físico", "PDF y XLS", "Descuentos/ y data/pedidos_archivos/", "5 Años", "Administrador"),
        ("Base de Datos Maestra de Productos", "SQLite (`productos.sqlite3`)", "data/productos.sqlite3", "Permanente", "Master / Admin"),
        ("Alertas de Demanda Anómala", "JSON (`admin_notifications`)", "data/pedidos.sqlite3", "1 Año", "Administrador"),
    ]
    t_radm_data = [headers_radm]
    for r1, r2, r3, r4, r5 in filas_radm:
        t_radm_data.append([Paragraph(f"<b>{r1}</b>", est["td_apa"]), Paragraph(r2, est["td_apa_center"]), Paragraph(r3, est["td_apa"]), Paragraph(r4, est["td_apa_center"]), Paragraph(r5, est["td_apa"])])
    t_radm = Table(t_radm_data, colWidths=[3.8 * cm, 2.2 * cm, 4.2 * cm, 2.0 * cm, 3.3 * cm])
    aplicar_estilo_tabla_apa(t_radm, len(t_radm_data))
    story.append(t_radm)
    story.append(Paragraph("<i>Nota.</i> Control documental bajo Cláusula 7.5.3 de la Norma ISO 9001:2015.", est["apa_tabla_nota"]))

    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Tabla 8</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Tratamiento de No Conformidades Administrativas y Acciones Correctivas</i>", est["apa_tabla_titulo"]))

    headers_err_adm = [
        Paragraph("<b>No Conformidad</b>", est["th_apa"]),
        Paragraph("<b>Causa Raíz</b>", est["th_apa"]),
        Paragraph("<b>Acción Inmediata (Corrección)</b>", est["th_apa"]),
        Paragraph("<b>Acción Preventiva</b>", est["th_apa"]),
    ]
    filas_err_adm = [
        ("NC-ADM-01: Discrepancia Físico", "Ajuste no registrado o merma.", "Aplicar ajuste justificado con remito interno.", "Capacitar en registro oportuno de mermas."),
        ("NC-ADM-02: Agotamiento Inesperado", "Pico extraordinario de ventas online.", "Emitir pedido urgente a fábrica con POE-ADM-03.", "Ajustar umbral de Stock Mínimo en catálogo."),
        ("NC-ADM-03: Bloqueo de Operario", "5 contraseñas erróneas consecutivas.", "En 'Gestionar usuarios', pulsar desbloqueo.", "Capacitar en uso de contraseñas seguras."),
    ]
    t_eadm_data = [headers_err_adm]
    for e1, e2, e3, e4 in filas_err_adm:
        t_eadm_data.append([Paragraph(f"<b>{e1}</b>", est["td_apa_bold_center"]), Paragraph(e2, est["td_apa"]), Paragraph(e3, est["td_apa"]), Paragraph(e4, est["td_apa"])])
    t_eadm = Table(t_eadm_data, colWidths=[3.0 * cm, 3.5 * cm, 4.5 * cm, 4.5 * cm])
    aplicar_estilo_tabla_apa(t_eadm, len(t_eadm_data))
    story.append(t_eadm)
    story.append(Paragraph("<i>Nota.</i> Acciones correctivas formalizadas según la Cláusula 10.2 de la Norma ISO 9001:2015.", est["apa_tabla_nota"]))

    # SECCIONES FINALES NORMALIZADAS
    story.append(PageBreak())
    story.append(Paragraph("4. Infraestructura de Supervisión y Control Institucional", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 9)
    agregar_formulario_firmas_autorizadas_iso(story, est, 10)

    story.append(PageBreak())
    story.append(Paragraph("5. Registros de Inducción, Referencia Rápida y Terminología", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_acta_capacitacion_personal(story, est, 11)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "v2.1.0"))
    return ruta_destino


# =============================================================================
# 3. MANUAL ROL MASTER (ISO 26514, ISO 9001, ISO 27001, BPMN 2.0 & APA/UPEL)
# =============================================================================
def construir_manual_master(ruta_destino: Path) -> Path:
    """Compila el Manual del Rol Master bajo Normas ISO, BPMN y APA/UPEL."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(ruta_destino), pagesize=A4, leftMargin=MARGEN_IZQ, rightMargin=MARGEN_DER, topMargin=MARGEN_SUP, bottomMargin=MARGEN_INF)
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "SOP-STK-MAS-2026-v2.1"
    titulo_doc = "Manual Técnico, IAM y Auditoría Forense (Rol Master)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Master (Desarrollo, Seguridad, Auditoría y Continuidad)",
        "Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015, ISO/IEC 27001 e ISO/IEC/IEEE 26514:2022,<br/>"
        "modelado BPMN 2.0 (Bizagi) y pautas metodológicas UPEL para administración de identidades, auditoría forense inmutable y disaster recovery",
        version="2.1.0",
    )

    story.append(Paragraph("1. Principios de Seguridad SoD y Menor Privilegio (ISO/IEC 27001)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "El perfil Master (`Desarrollo`) constituye la autoridad técnica y de seguridad de StockAgent. "
        "En estricto apego al Control 5.3 de la Norma ISO/IEC 27001 (Segregación de Funciones), este rol se encuentra "
        "totalmente desacoplado de la operativa diaria de depósito (no procesa pedidos ni consulta pedidos en preparación), "
        "garantizando la absoluta imparcialidad y ausencia de conflictos de interés en las auditorías forenses.",
        est["body_sangria"],
    ))
    story.append(Paragraph(
        "Asimismo, se establece el carácter inmutable de la cuenta Master: no puede ser eliminada, bloqueada "
        "ni degradada de rol bajo ninguna circunstancia del sistema.",
        est["body_sangria"],
    ))

    # CAPÍTULO 2: PROCEDIMIENTOS TÉCNICOS
    story.append(Spacer(1, 4))
    story.append(Paragraph("2. Procedimientos de Seguridad y Continuidad (SOP / POE)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    # POE-MAS-01
    agregar_ficha_procedimiento_apa(
        story, est, 3,
        "POE-MAS-01", "Gestión Global de Identidades y Accesos (IAM Supremo)",
        "Administrar el ciclo de vida de credenciales, roles privilegiados y desbloqueos administrativos.",
        "Dirección TI / RRHH", "Solicitud de alta o reseteo de cuenta Administrador",
        "Cuentas activas en tabla `users`, claves con hash criptográfico PBKDF2-SHA256", "Administradores de área",
        "R: Master | A: Dirección TI",
        ["Autenticación de dos factores o verificación de identidad de Master verificada."],
        [
            "En la sección 'Gestionar usuarios', se procede al alta de cuentas para los roles Administrador, Operador o Consulta.",
            "Para reseteo de claves: se genera contraseña temporal marcando con carácter forzoso `must_change_password = 1`.",
            "Se desbloquean de forma inmediata las cuentas bloqueadas por fuerza bruta (5 fallos) sin esperar la ventana de 15 min.",
        ],
        ["Registro inmutable en `logs_auditoria` con usuario, dirección IP y sello de tiempo."],
        "Las contraseñas deben cumplir longitud mínima de 10 caracteres con complejidad alfanumérica.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 1,
        "Flujograma de Proceso BPMN 2.0: Gestión de Identidades IAM (POE-MAS-01)",
        lanes=["Solicitante / RRHH", "Usuario Master", "Motor de Seguridad IAM"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Solicitud"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Validar Legajo", "Asignar Perfil"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Aprobado?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Generar PBKDF2", "Asentar Audit"]},
            {"tipo": "tarea", "x": 315, "y": 96, "w": 62, "h": 22, "texto": ["Entregar Clave", "Forzar Cambio"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Cuenta OK"},
        ],
        flujos=[
            (111.5, 96, 118, 58),
            (176, 58, 186, 58),
            (204, 58, 230, 19),
            (292, 19, 315, 96),
            (377, 96, 403, 96),
        ],
    )

    story.append(PageBreak())

    # POE-MAS-02
    agregar_ficha_procedimiento_apa(
        story, est, 4,
        "POE-MAS-02", "Restauración Documental y Rollback de Lotes (Exclusivo Master)",
        "Revertir operaciones erróneas o lotes históricos recomponiendo atómicamente el catálogo.",
        "Solicitud formal de Administrador", "Fecha de descuento y número de comprobante",
        "Catálogo Productos.xlsx y SQLite reconstituidos al estado previo exacto", "Contabilidad / Auditoría",
        "R: Master | A: Dirección Operaciones",
        ["Solicitud fundamentada por escrito y autorizada por la Gerencia de Operaciones."],
        [
            "En la barra lateral bajo <i>Resguardo y Continuidad</i>, se pulsa el comando <b>'Restaurar documentos'</b>.",
            "Se selecciona con precisión la fecha y el lote histórico que se requiere deshacer.",
            "Se presiona <b>'Previsualizar Rollback'</b> para constatar las unidades que retornarán al inventario.",
            "Se confirma la operación mediante <b>'Restaurar Catálogo'</b>: el motor recompone SQLite y Productos.xlsx.",
        ],
        ["Existencias físicas incrementadas en el inventario.", "Registro forense inmutable de rollback."],
        "Verificación de integridad estructural de base de datos ejecutando `PRAGMA integrity_check`.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 2,
        "Flujograma de Proceso BPMN 2.0: Restauración y Rollback SoD (POE-MAS-02)",
        lanes=["Administrador", "Usuario Master (SoD)", "Motor Criptográfico"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Petición"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Analizar Motivo", "Previsualizar"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Auditoría OK?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Eliminar Hash", "Reponer Stock"]},
            {"tipo": "tarea", "x": 315, "y": 58, "w": 62, "h": 22, "texto": ["Registrar Log", "Notificar Admin"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Rollback OK"},
        ],
        flujos=[
            (111.5, 96, 118, 58),
            (176, 58, 186, 58),
            (204, 58, 230, 19),
            (292, 19, 315, 58),
            (377, 58, 403, 96),
        ],
    )

    # POE-MAS-03
    agregar_ficha_procedimiento_apa(
        story, est, 5,
        "POE-MAS-03", "Continuidad del Negocio y Recuperación de Desastres (Disaster Recovery)",
        "Asegurar la alta disponibilidad del sistema mediante respaldos comprimidos y réplica espejo secundaria.",
        "Sistema StockAgent en producción", "Bases SQLite (`pedidos`, `usuarios`, `productos`) y catálogo Excel",
        "Archivo comprimido `.zip` en `data/backups/` y réplica en servidor NAS / Nube", "Toda la Organización",
        "R: Master | A: Gerencia TI",
        ["Ruta espejo secundaria configurada y con permisos de escritura activos (Regla de Respaldo 3-2-1)."],
        [
            "En 'Copia de Seguridad', se acciona el respaldo manual o se valida la ejecución automática del cierre.",
            "Se verifica la réplica atómica del archivo `.zip` hacia el almacenamiento externo secundario.",
            "Se audita la política de rotación que conserva las últimas 30 versiones suprimiendo las precedentes.",
        ],
        ["Respaldo íntegro resguardado en dos ubicaciones físicas independientes."],
        "Ejecución satisfactoria de prueba semestral de restauración en entorno de aislamiento (Sandbox).",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 3,
        "Flujograma de Proceso BPMN 2.0: Continuidad y Respaldo 3-2-1 (POE-MAS-03)",
        lanes=["Usuario Master", "Sistema StockAgent", "Almacenamiento Red NAS"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Disparador"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Comprimir Bases", "Verificar Integridad"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Check OK?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Replicar Espejo", "Rotar Versiones"]},
            {"tipo": "tarea", "x": 315, "y": 96, "w": 62, "h": 22, "texto": ["Auditar Sandbox", "Firmar Acta"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Backup OK"},
        ],
        flujos=[
            (111.5, 96, 118, 58),
            (176, 58, 186, 58),
            (204, 58, 230, 19),
            (292, 19, 315, 96),
            (377, 96, 403, 96),
        ],
    )

    # CAPÍTULO 3: REGISTROS FORENSES
    story.append(PageBreak())
    story.append(Paragraph("3. Registros de Auditoría y Trazabilidad Forense (ISO 27001 & ISO 9001)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    story.append(Paragraph("<b>Tabla 6</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Matriz de Registros Forenses e Información de Seguridad de Infraestructura</i>", est["apa_tabla_titulo"]))

    headers_rmas = [
        Paragraph("<b>Registro Forense</b>", est["th_apa"]),
        Paragraph("<b>Soporte</b>", est["th_apa"]),
        Paragraph("<b>Ubicación</b>", est["th_apa"]),
        Paragraph("<b>Retención</b>", est["th_apa"]),
        Paragraph("<b>Responsable</b>", est["th_apa"]),
    ]
    filas_rmas = [
        ("Registro de Auditoría Forense", "SQLite inmutable", "data/pedidos.sqlite3 (`logs_auditoria`)", "10 Años", "Master"),
        ("Intentos de Acceso / Ataques", "SQLite (`login_attempts`)", "data/usuarios.sqlite3", "2 Años", "Master"),
        ("Logs de Servidor Web y Conexiones", "Archivo rotativo", "data/logs/stockagent.log", "1 Año", "Master"),
        ("Certificados SSL/HTTPS X.509", "Criptográfico PEM", "data/certs/stockagent.crt / .key", "Permanente / Renovable", "Master"),
    ]
    t_rmas_data = [headers_rmas]
    for r1, r2, r3, r4, r5 in filas_rmas:
        t_rmas_data.append([Paragraph(f"<b>{r1}</b>", est["td_apa"]), Paragraph(r2, est["td_apa_center"]), Paragraph(r3, est["td_apa"]), Paragraph(r4, est["td_apa_center"]), Paragraph(r5, est["td_apa"])])
    t_rmas = Table(t_rmas_data, colWidths=[3.8 * cm, 2.2 * cm, 4.2 * cm, 2.0 * cm, 3.3 * cm])
    aplicar_estilo_tabla_apa(t_rmas, len(t_rmas_data))
    story.append(t_rmas)
    story.append(Paragraph("<i>Nota.</i> Custodia inmutable bajo la Cláusula 8.15 de la Norma ISO/IEC 27001:2022.", est["apa_tabla_nota"]))

    # SECCIONES FINALES NORMALIZADAS
    story.append(PageBreak())
    story.append(Paragraph("4. Infraestructura de Servidor y Control Institucional", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 7)
    agregar_formulario_firmas_autorizadas_iso(story, est, 8)

    story.append(PageBreak())
    story.append(Paragraph("5. Registros de Inducción, Referencia Rápida y Terminología Forense", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_acta_capacitacion_personal(story, est, 9)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "v2.1.0"))
    return ruta_destino


# =============================================================================
# 4. MANUAL ROL CONSULTA (ISO 26514, ISO 9001, BPMN 2.0 & APA/UPEL)
# =============================================================================
def construir_manual_consulta(ruta_destino: Path) -> Path:
    """Compila el Manual del Rol Consulta bajo Normas ISO, BPMN y APA/UPEL."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(ruta_destino), pagesize=A4, leftMargin=MARGEN_IZQ, rightMargin=MARGEN_DER, topMargin=MARGEN_SUP, bottomMargin=MARGEN_INF)
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "SOP-STK-CON-2026-v2.1"
    titulo_doc = "Manual de Procedimientos de Consulta Externa (Rol Consulta)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Rol Consulta (Vendedores, Auditorías Externas y Supervisión)",
        "Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015 e ISO/IEC/IEEE 26514:2022,<br/>"
        "modelado BPMN 2.0 (Bizagi) y pautas metodológicas UPEL para búsqueda de existencias en tiempo real e inspección de reportes",
        version="2.1.0",
    )

    story.append(Paragraph("1. Alcance y Restricciones de Solo Lectura (ISO 26514)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "El perfil de Consulta tiene por objeto proveer acceso seguro de solo lectura a vendedores, auditores "
        "y supervisores comerciales que precisan corroborar existencias y ubicaciones en estantería sin comprometer "
        "la integridad transaccional del catálogo maestro de inventario.",
        est["body_sangria"],
    ))
    story.append(Paragraph(
        "Se prohíbe de forma irrestricta la emisión de descuentos, modificaciones de bultos o ejecuciones de cierre de jornada "
        "a través de este nivel de acceso.",
        est["body_sangria"],
    ))

    # Procedimientos
    story.append(Spacer(1, 4))
    story.append(Paragraph("2. Procedimientos de Consulta Estandarizados (SOP / POE)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_procedimiento_apa(
        story, est, 3,
        "POE-CON-01", "Búsqueda de Existencias y Ubicación de Artículos en Tiempo Real",
        "Consultar saldos disponibles, descripción y posición física en estanterías.",
        "Vendedores / Clientes", "Código SKU, código de barras o descripción",
        "Información de stock disponible y ubicación física en estantería (Rack/Nivel)", "Cliente / Mostrador",
        "R: Vendedor / Auditor | I: Depósito",
        ["Sesión de Consulta debidamente autenticada."],
        [
            "Se acciona la combinación <code>Ctrl + K</code> o la tecla <code>F2</code> para abrir la Paleta de Búsqueda Rápida.",
            "Se ingresa el código o término de búsqueda. El motor de consulta filtra en vivo en menos de 0.05 segundos.",
            "Se verifica el saldo disponible y se visualiza la ubicación física en estantería (ej. <code>Rack B, Mod 2, Niv 1</code>).",
        ],
        ["Consulta registrada en logs sin alteración de datos contables."],
        "Concordancia exacta entre el saldo visualizado en pantalla y el registro activo en SQLite.",
    )

    agregar_diagrama_bpmn_apa(
        story, est, 1,
        "Flujograma de Proceso BPMN 2.0: Consulta Rápida de Inventario (POE-CON-01)",
        lanes=["Usuario Consulta", "Motor StockAgent", "Mostrador Comercial"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Consulta"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Presionar F2", "Ingresar SKU"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Búsqueda SQLite", "Localizar Rack"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Hay Saldo?"},
            {"tipo": "tarea", "x": 310, "y": 19, "w": 62, "h": 22, "texto": ["Mostrar Stock", "Informar Cliente"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Fin Consulta"},
        ],
        flujos=[
            (111.5, 96, 118, 96),
            (176, 96, 195, 58),
            (257, 58, 271, 58),
            (289, 58, 310, 19),
            (372, 19, 403, 19),
        ],
    )

    # SECCIONES FINALES NORMALIZADAS
    story.append(PageBreak())
    story.append(Paragraph("3. Infraestructura de Puesto, Distribución y Firmas Autorizadas", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 4)
    agregar_formulario_firmas_autorizadas_iso(story, est, 5)

    story.append(PageBreak())
    story.append(Paragraph("4. Registros de Inducción, Referencia Rápida y Glosario", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_acta_capacitacion_personal(story, est, 6)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "v2.1.0"))
    return ruta_destino


# =============================================================================
# 5. MANUAL MAESTRO INTEGRAL E IMPRIMIBLE (COMPENDIO TOTAL DEL SISTEMA)
# =============================================================================
def construir_manual_maestro_imprimible(ruta_destino: Path) -> Path:
    """Compila el Manual Maestro Integral Imprimible para entrega final al usuario o auditorías."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(ruta_destino), pagesize=A4, leftMargin=MARGEN_IZQ, rightMargin=MARGEN_DER, topMargin=MARGEN_SUP, bottomMargin=MARGEN_INF)
    est = obtener_estilos_iso_upel()
    story = []

    codigo_doc = "SOP-STK-MAE-2026-v2.1"
    titulo_doc = "Manual Maestro de Procedimientos del Sistema (Compendio Integral Imprimible)"

    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc,
        "Todos los Roles (Operador, Administrador, Master, Consulta y Auditoría)",
        "Compendio general exhaustivo de Procedimientos Operativos Estandarizados (POE / SOP) según Normas ISO 9001:2015,<br/>"
        "ISO/IEC/IEEE 26514:2022 e ISO/IEC 27001:2022 bajo modelado BPMN 2.0 (Bizagi), pautas UPEL (5ta ed.) y Gestión del Cambio",
        version="2.1.0",
    )

    # TABLA DE CONTENIDOS (SUMARIO GENERAL)
    story.append(Paragraph("Índice General de Contenidos del Manual Maestro", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    toc_data = [
        [Paragraph("<b>Capítulo / Sección Temática</b>", est["th_apa"]), Paragraph("<b>Alcance Operativo y Normativo</b>", est["th_apa"]), Paragraph("<b>Referencia</b>", est["th_apa"])],
        [Paragraph("1. Marco Estratégico, Objetivos y Alcance", est["td_apa"]), Paragraph("Gobernanza de calidad, principios y trazabilidad.", est["td_apa"]), Paragraph("ISO 9001 §4.3", est["td_apa_center"])],
        [Paragraph("2. Arquitectura y Matriz SoD Oficial", est["td_apa"]), Paragraph("Segregación de funciones (IAM) y mapa de roles.", est["td_apa"]), Paragraph("ISO 27001 §5.3", est["td_apa_center"])],
        [Paragraph("3. Procedimientos de Depósito (Rol Operador)", est["td_apa"]), Paragraph("Remitos, Mercado Libre Full, QR y Despacho.", est["td_apa"]), Paragraph("POE-OPE 01..04", est["td_apa_center"])],
        [Paragraph("4. Procedimientos de Supervisión (Rol Admin)", est["td_apa"]), Paragraph("Catálogo, Entrada Fábrica, Compras y Slotting.", est["td_apa"]), Paragraph("POE-ADM 01..04", est["td_apa_center"])],
        [Paragraph("5. Procedimientos Técnicos (Rol Master)", est["td_apa"]), Paragraph("IAM Supremo, Rollback SoD y Respaldo 3-2-1.", est["td_apa"]), Paragraph("POE-MAS 01..03", est["td_apa_center"])],
        [Paragraph("6. Procedimientos de Consulta (Rol Consulta)", est["td_apa"]), Paragraph("Búsqueda en tiempo real e inspección de reportes.", est["td_apa"]), Paragraph("POE-CON 01", est["td_apa_center"])],
        [Paragraph("7. Gestión del Cambio y Nuevos Módulos", est["td_apa"]), Paragraph("Procedimiento estándar de actualización de software.", est["td_apa"]), Paragraph("POE-SGC 01", est["td_apa_center"])],
        [Paragraph("8. Control de Registros y Evidencias", est["td_apa"]), Paragraph("Matriz unificada de retención y custodia.", est["td_apa"]), Paragraph("ISO 9001 §7.5.3", est["td_apa_center"])],
        [Paragraph("9. Gestión de No Conformidades y Errores", est["td_apa"]), Paragraph("Tratamiento de fallas, causa raíz y corrección.", est["td_apa"]), Paragraph("ISO 9001 §10.2", est["td_apa_center"])],
        [Paragraph("10. Indicadores Clave de Desempeño (KPIs)", est["td_apa"]), Paragraph("Medición de tiempos, precisión y efectividad.", est["td_apa"]), Paragraph("ISO 9001 §9.1", est["td_apa_center"])],
        [Paragraph("11. Infraestructura Técnica y Ergonomía", est["td_apa"]), Paragraph("Requisitos de terminales, red, lector e impresora.", est["td_apa"]), Paragraph("ISO 9001 §7.1.3", est["td_apa_center"])],
        [Paragraph("12. Distribución y Copias Controladas", est["td_apa"]), Paragraph("Asignación de ejemplares maestros y secundarios.", est["td_apa"]), Paragraph("ISO 9001 §7.5.3", est["td_apa_center"])],
        [Paragraph("13. Formulario de Firmas Autorizadas", est["td_apa"]), Paragraph("Suscripción de Elaboración, Revisión y Aprobación.", est["td_apa"]), Paragraph("ISO 9001 §7.5.2", est["td_apa_center"])],
        [Paragraph("14. Acta de Capacitación e Inducción", est["td_apa"]), Paragraph("Registro firmado de toma de conocimiento del personal.", est["td_apa"]), Paragraph("ISO 9001 §7.2", est["td_apa_center"])],
        [Paragraph("15. Tarjeta Plastificable de Referencia", est["td_apa"]), Paragraph("Cheat Sheet con atajos y alertas sonoras para muelle.", est["td_apa"]), Paragraph("Práctica Operativa", est["td_apa_center"])],
        [Paragraph("16. Glosario de Términos y Definiciones", est["td_apa"]), Paragraph("Definición reglamentaria de conceptos operativos.", est["td_apa"]), Paragraph("ISO 9000 & UPEL", est["td_apa_center"])],
        [Paragraph("17. Referencias Normativas y Bibliografía", est["td_apa"]), Paragraph("Citas formales bajo norma APA 7ma / UPEL 5ta.", est["td_apa"]), Paragraph("APA 7 / UPEL 5", est["td_apa_center"])],
    ]
    t_toc = Table(toc_data, colWidths=[5.5 * cm, 7.5 * cm, 2.5 * cm])
    aplicar_estilo_tabla_apa(t_toc, len(toc_data))
    story.append(t_toc)
    story.append(Spacer(1, 4))

    # CAPÍTULO 1: MARCO ESTRATÉGICO Y GOBERNANZA
    story.append(PageBreak())
    story.append(Paragraph("1. Marco Estratégico, Objetivos y Alcance (ISO 9001 §4.3 & §5.3)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "StockAgent constituye la plataforma informática troncal para la administración de inventario, "
        "despacho mayorista y trazabilidad física en depósitos logísticos. "
        "Su desarrollo y operación se rigen de conformidad con las directrices de la Norma ISO 9001:2015 "
        "para el aseguramiento de la calidad, ISO/IEC 27001:2022 para la seguridad de la información y "
        "las pautas metodológicas de la UPEL en materia de formalidad documental.",
        est["body_sangria"],
    ))

    # CAPÍTULO 2: ARQUITECTURA Y MATRIZ SOD OFICIAL
    story.append(Spacer(1, 4))
    story.append(Paragraph("2. Arquitectura de Plataforma y Segregación de Funciones (SoD - ISO 27001)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    story.append(Paragraph(
        "A continuación se presenta la Matriz Oficial de Segregación de Funciones (SoD) completa que delimita "
        "con precisión matemática los permisos concedidos a cada perfil de usuario en el sistema:",
        est["body_sangria"],
    ))

    headers_sod = [
        Paragraph("<b>Funcionalidad / Módulo</b>", est["th_apa"]),
        Paragraph("<b>Master</b>", est["th_apa"]),
        Paragraph("<b>Admin</b>", est["th_apa"]),
        Paragraph("<b>Operador</b>", est["th_apa"]),
        Paragraph("<b>Consulta</b>", est["th_apa"]),
        Paragraph("<b>Regla de Seguridad SoD</b>", est["th_apa"]),
    ]
    matriz_data = [headers_sod]
    filas_permisos = [
        ("Carga Pedidos (Remitos / Canjes)", "❌ No", "✅ Sí", "✅ Sí", "❌ No", "Master desacoplado; operarios procesan comprobantes."),
        ("Descuento Mercado Libre (DOCX)", "❌ No", "✅ Sí", "✅ Sí", "❌ No", "Procesamiento ágil de ventas online en depósito."),
        ("Descuento Mercado Full (Excel)", "❌ No", "✅ Sí", "✅ Sí", "❌ No", "Habilitado para agilizar despachos masivos Full."),
        ("Modificar Pedidos Preparados", "❌ No", "❌ Lectura", "✅ Exclusivo", "❌ No", "Exclusivo de depósito para evitar colisión de empaque."),
        ("Desarmar Pedido (Devolver Stock)", "❌ No", "✅ Sí", "✅ Sí", "❌ No", "Reincorporación atómica de unidades ante cancelaciones."),
        ("Rótulos QR (A4 y Rollo Térmico)", "❌ No", "✅ Sí", "✅ Sí", "❌ No", "Etiquetado sin desperdicio por bulto preparado."),
        ("Cierre de Jornada y Hojas de Ruta", "❌ No", "✅ Sí", "✅ Sí", "❌ No", "Consolidación de turno y control de transportistas."),
        ("Inventario en Vivo (Escáner)", "❌ No", "✅ Sí", "✅ Sí", "❌ No", "Relevamiento físico de estanterías en tiempo real."),
        ("Ajuste Stock / Entrada Fábrica", "❌ No", "✅ Sí", "❌ No", "❌ No", "Modificación de existencias reservada a supervisión."),
        ("Gestión de Catálogo (Productos.xlsx)", "❌ No", "✅ Sí", "❌ No", "❌ No", "Altas, descripciones, precios y umbrales mínimos."),
        ("Comparativa de Stock Físico", "❌ No", "✅ Sí", "❌ No", "❌ No", "Conciliación de inventarios y detección de desvíos."),
        ("Generar Pedido a Fábrica", "❌ No", "✅ Sí", "❌ No", "❌ No", "Planilla sugerida de reposición para proveedores."),
        ("Analítica, Radar y Heatmap Slotting", "❌ No", "✅ Sí", "❌ No", "❌ No", "Inteligencia de depósito y optimización de picking."),
        ("Gestión Usuarios (Operador/Consulta)", "✅ Sí", "✅ Sí", "❌ No", "❌ No", "Altas, bajas y reseteo de claves de personal."),
        ("Gestión Usuarios (Administradores)", "✅ Exclusivo", "❌ No", "❌ No", "❌ No", "Solo Master puede promover o degradar administradores."),
        ("Auditoría Forense y Salud Servidor", "✅ Exclusivo", "❌ No", "❌ No", "❌ No", "SoD estricto: el auditado no puede auditarse."),
        ("Copias de Seguridad (.zip)", "✅ Sí", "✅ Sí", "❌ No", "❌ No", "Respaldos íntegros de SQLite y catálogo."),
        ("Restaurar Documentos (Rollback)", "✅ Exclusivo", "❌ No", "❌ No", "❌ No", "Reversión de lotes delegada exclusivamente a Master."),
    ]
    for f_nom, m_st, a_st, o_st, c_st, regla in filas_permisos:
        matriz_data.append([
            Paragraph(f"<b>{escape(f_nom)}</b>", est["td_apa"]),
            Paragraph(m_st, est["td_apa_bold_center"] if "Exclusivo" in m_st else est["td_apa_center"]),
            Paragraph(a_st, est["td_apa_bold_center"] if "Exclusivo" in a_st else est["td_apa_center"]),
            Paragraph(o_st, est["td_apa_bold_center"] if "Exclusivo" in o_st else est["td_apa_center"]),
            Paragraph(c_st, est["td_apa_center"]),
            Paragraph(escape(regla), est["td_apa"]),
        ])
    t_sod = Table(matriz_data, colWidths=[4.2 * cm, 1.6 * cm, 1.6 * cm, 1.8 * cm, 1.6 * cm, 4.7 * cm], repeatRows=1)
    aplicar_estilo_tabla_apa(t_sod, len(matriz_data))
    story.append(t_sod)
    story.append(Paragraph("<i>Nota.</i> Control de segregación estructurado conforme al Control 5.3 de la Norma ISO/IEC 27001:2022.", est["apa_tabla_nota"]))

    # CAPÍTULO 3: PROCEDIMIENTOS DE DEPÓSITO (ROL OPERADOR)
    story.append(PageBreak())
    story.append(Paragraph("3. Procedimientos Operativos de Depósito (Rol Operador)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    # POE-OPE-01
    agregar_ficha_procedimiento_apa(
        story, est, 4, "POE-OPE-01", "Carga y Descuento de Remitos Mayoristas (PDF) y Canjes (Excel)",
        "Descontar existencias y asentar el pedido en la jornada de forma atómica en SQLite y Productos.xlsx.",
        "Área Comercial / Clientes", "Remito digital (.pdf) o Planilla de Canje (.xlsx)",
        "Pedido registrado, stock decrementado, hash SHA-256 asentado", "Transporte / Empaque",
        "R: Operario | A: Administrador | I: Chofer",
        ["El servidor web se encuentra activo en el puerto 8550.", "El catálogo maestro se encuentra plenamente sincronizado."],
        [
            "Se procede a pulsar el comando <b>'Seleccionar archivo'</b> para adjuntar el comprobante (.pdf o .xlsx).",
            "Se constata que el sistema haya extraído y separado con exactitud el código numérico de la razón social (ej. <code>00714 - DIETETICA SABORES</code>).",
            "Se gradúa la cantidad de bultos acondicionados mediante los pulsadores <code>[-]</code> y <code>[+]</code> (mínimo un bulto).",
            "Se selecciona con carácter obligatorio la empresa de transporte en el menú desplegable de logística.",
            "Se valida la fecha de retiro pre-completada por el motor a partir de la fecha de despacho del documento.",
            "Se pulsa el botón <b>'Cargar y Descontar'</b>. El sistema emite una señal acústica en 880 Hz que certifica la transacción.",
        ],
        ["El pedido se asienta en la tabla `pedidos` con cierre_id = NULL.", "El archivo binario se almacena en `data/pedidos_archivos/`."],
        "El comprobante no debe registrar coincidencia previa de hash SHA-256 y el inventario resultante debe ser mayor o igual a cero.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 1, "Flujograma BPMN 2.0: Carga y Descuento de Remitos (POE-OPE-01)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Muelle / Despacho"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Remito"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Adjuntar Remito", "Ajustar Bultos"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Validar SHA-256", "Descontar Stock"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Duplicado?"},
            {"tipo": "tarea", "x": 310, "y": 96, "w": 60, "h": 22, "texto": ["Imprimir Rótulo", "Paletizar Bulto"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Muelle OK"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 96), (370, 96, 403, 19)],
    )

    story.append(PageBreak())

    # POE-OPE-02
    agregar_ficha_procedimiento_apa(
        story, est, 5, "POE-OPE-02", "Descuento Masivo de Mercado Libre Full (Planilla Excel)",
        "Procesar planillas oficiales de despacho Full directamente desde el menú lateral de depósito.",
        "Mercado Libre / Depósito", "Planilla oficial de despacho Full (.xlsx / .xls)",
        "Descuento consolidado en bloque, actualización de Productos.xlsx", "Jefatura de Operaciones",
        "R: Operario | A: Administrador | I: Depósito Full",
        ["La planilla oficial de Mercado Libre Full ha sido descargada de la plataforma.", "Sesión de Operador autenticada."],
        [
            "En la barra de navegación lateral, se pulsa el botón <b>'Descontar Mercado Full'</b>.",
            "Se selecciona el archivo Excel oficial suministrado por Mercado Libre.",
            "El sistema procesa automáticamente las columnas y muestra la vista previa con el total de artículos a descontar.",
            "Se confirma la operación. El motor descuenta el inventario de forma consolidada en una sola transacción.",
            "Se verifica el mensaje de éxito en pantalla y se actualiza la copia de Productos.xlsx.",
        ],
        ["Existencias actualizadas en SQLite (`productos.sqlite3`) y en `Productos.xlsx`.", "Movimiento registrado en `stock_movements`."],
        "Concordancia entre los totales de la planilla y las unidades decrementadas sin errores de lectura.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 2, "Flujograma BPMN 2.0: Descuento Masivo Mercado Libre Full (POE-OPE-02)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Mercado Libre Full"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Planilla"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Abrir Menú Full", "Adjuntar Excel"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Parsear Columnas", "Verificar Stock"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Stock OK?"},
            {"tipo": "tarea", "x": 310, "y": 58, "w": 62, "h": 22, "texto": ["Descuento Bloque", "Actualizar Excel"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Full Listo"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 58), (372, 58, 403, 19)],
    )

    # POE-OPE-03
    agregar_ficha_procedimiento_apa(
        story, est, 6, "POE-OPE-03", "Rotulación Térmica Continua y Validación de Códigos QR",
        "Generar e imprimir etiquetas adhesivas individuales por cada bulto acondicionado.",
        "Pedido descontado en POE-OPE-01", "Identificador de pedido (`pedido_id`) y cantidad de bultos",
        "Rótulos QR impresos (80 mm continuo), bultos identificados", "Transportista / Cliente",
        "R: Operario | I: Transporte",
        ["La impresora térmica de 80 mm se encuentra encendida y con papel continuo cargado."],
        [
            "En la vista de Pedidos Preparados, se ubica el comprobante y se pulsa el botón <b>'Ver Rótulos'</b>.",
            "El sistema genera una secuencia de etiquetas optimizada para rollo térmico continuo (ancho 80 mm).",
            "Cada etiqueta incluye código QR de alta resolución con el remito y el correlativo del bulto (ej. <code>Bulto 1 de 3</code>).",
            "Se adhiere cada rótulo sobre la cara superior visible del bulto correspondiente.",
            "Se efectúa un escaneo de prueba con la pistola óptica o celular para certificar legibilidad inmediata.",
        ],
        ["Código QR legible mediante pistola óptica o dispositivo móvil."],
        "Lectura satisfactoria del código QR constatando número de remito y correlativo de bulto.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 3, "Flujograma BPMN 2.0: Rotulación Térmica y Validación QR (POE-OPE-03)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Paletizado Físico"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Bultos"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Ubicar Pedido", "Pulsar Ver QR"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Generar Vector QR", "Correlativo 1..N"]},
            {"tipo": "tarea", "x": 280, "y": 96, "w": 60, "h": 22, "texto": ["Impresión 80mm", "Validar Pistola"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Rotulado OK"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 280, 96), (340, 96, 403, 19)],
    )

    story.append(PageBreak())

    # POE-OPE-04
    agregar_ficha_procedimiento_apa(
        story, est, 7, "POE-OPE-04", "Despacho en Lote, Notificación WhatsApp y Cierre de Jornada",
        "Controlar la entrega formal al transportista y consolidar los movimientos del turno de trabajo.",
        "Tarimas de empaque listas", "Pedidos preparados pendientes de retiro",
        "Informe Oficial de Cierre (PDF/Excel), Hojas de Ruta por transporte firmadas", "Gerencia / Administración",
        "R: Operario | A: Administrador | I: Chofer / Transportista",
        ["El turno operacional ha finalizado.", "La totalidad de pedidos preparados ha sido verificada en muelle."],
        [
            "En el Historial de Pedidos, se filtra la vista por 'Pendientes de Cierre'. Se marcan los pedidos entregados al chofer.",
            "Se pulsa el botón <b>'Despachar Seleccionados'</b> para transicionar los pedidos a estado DESPACHADO.",
            "Se ingresa el N° de guía del expreso y se pulsa el icono de WhatsApp para despachar el mensaje formal al cliente.",
            "Se acciona el comando <b>'Cierre de Jornada'</b>. El sistema consolida los descuentos evitando duplicidades.",
            "Se imprimen las Hojas de Ruta individuales por transporte y se recaba la firma de conformidad del chofer.",
            "Se verifica que los contadores del panel principal retornen a cero para la recepción del siguiente turno.",
        ],
        ["Los pedidos quedan vinculados al número único de cierre (`cierre_id`).", "Se genera el respaldo automático en `data/backups/`."],
        "Conformidad física del transportista estampada en la Hoja de Ruta con firma, aclaración y fecha legible.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 4, "Flujograma BPMN 2.0: Despacho en Lote y Cierre de Jornada (POE-OPE-04)",
        lanes=["Operario Depósito", "Sistema StockAgent", "Transportista / Chofer"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Fin Turno"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Marcar Salida", "Cierre Jornada"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Asignar CierreID", "Generar Hojas"]},
            {"tipo": "tarea", "x": 280, "y": 19, "w": 60, "h": 22, "texto": ["Recibir Carga", "Firmar Hoja Ruta"]},
            {"tipo": "fin", "x": 410, "y": 58, "label": "Backup OK"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 280, 19), (340, 19, 403, 58)],
    )

    # CAPÍTULO 4: PROCEDIMIENTOS DE SUPERVISIÓN (ROL ADMINISTRADOR)
    story.append(PageBreak())
    story.append(Paragraph("4. Procedimientos de Supervisión Logística y Compras (Rol Administrador)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    # POE-ADM-01
    agregar_ficha_procedimiento_apa(
        story, est, 8, "POE-ADM-01", "Gestión del Catálogo Maestro y Parámetros de Seguridad",
        "Mantener actualizadas las fichas técnicas de productos, códigos de barra, precios y niveles de stock de seguridad.",
        "Compras / Proveedores", "Ficha técnica de producto, alta de nuevos códigos",
        "Catálogo maestro actualizado en SQLite y respaldo en Productos.xlsx", "Depósito / Ventas",
        "R: Administrador | A: Gerencia | I: Operarios",
        ["Sesión de Administrador activa.", "Respaldo automático previo de Productos.xlsx en disco."],
        [
            "En la sección 'Gestionar productos', se procede a dar de alta artículos indicando SKU, descripción y barras.",
            "Se define el <b>Stock Mínimo</b> (disparador automático de alertas de compra) y el <b>Stock Máximo</b>.",
            "Se asigna la ubicación física en estantería (Rack A-D, Módulo 1-4, Nivel 1-3) para optimizar el picking.",
            "Se pulsa el botón <b>'Sincronizar con Excel'</b> para volcar todos los saldos atómicamente a Productos.xlsx.",
        ],
        ["Artículos activos en SQLite y Excel.", "Trazabilidad de alta asentada en auditoría forense."],
        "Correspondencia unívoca entre SKU y descripción sin solapamiento de registros.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 5, "Flujograma BPMN 2.0: Gestión de Catálogo y Parámetros (POE-ADM-01)",
        lanes=["Administrador", "Sistema StockAgent", "Almacén Central"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Alta SKU"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Definir SKU/Barras", "Fijar Stock Mín."]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Validar Duplicidad", "Guardar SQLite"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Sincronizar?"},
            {"tipo": "tarea", "x": 310, "y": 58, "w": 62, "h": 22, "texto": ["Volcar a Excel", "Asentar Audit"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Catálogo OK"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 58), (372, 58, 403, 19)],
    )

    story.append(PageBreak())

    # POE-ADM-02
    agregar_ficha_procedimiento_apa(
        story, est, 9, "POE-ADM-02", "Recepción de Fábrica, Ajustes y Comparativa de Stock Físico",
        "Incorporar mercadería recibida y conciliar diferencias entre recuento físico y saldo digital.",
        "Fábrica / Proveedores", "Remito de fábrica (.xlsx, .xls o .pdf) o planilla de recuento",
        "Stock incrementado, reporte comparativo (COINCIDE/FALTANTE/SOBRANTE)", "Auditoría / Contabilidad",
        "R: Administrador | A: Gerencia",
        ["La mercadería física se encuentra en muelle de carga debidamente paletizada."],
        [
            "En 'Ajustar stock / Entrada Fábrica', se carga la planilla del proveedor para sumar existencias en lote.",
            "Para mermas o roturas, se ingresa el código y cantidad negativa adjuntando motivo justificatorio.",
            "Para inventarios masivos: se adjunta la planilla de recuento en 'Comparativa stock físico' y se presiona 'Comparar'.",
            "Se exporta el reporte comparativo oficial en PDF/Excel para sustento contable y auditoría de inventarios.",
        ],
        ["Existencias actualizadas en SQLite.", "Asiento de movimiento registrado en `stock_movements`."],
        "Ausencia de discrepancias no justificadas entre comprobante mayorista y stock digital.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 6, "Flujograma BPMN 2.0: Entrada de Fábrica y Comparativa (POE-ADM-02)",
        lanes=["Administrador", "Sistema StockAgent", "Auditoría Contable"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Recepción"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Adjuntar Remito", "Ejecutar Entrada"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Incrementar Saldo", "Generar Asiento"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Discrepancia?"},
            {"tipo": "tarea", "x": 310, "y": 19, "w": 62, "h": 22, "texto": ["Emitir Comparativo", "Reportar Merma"]},
            {"tipo": "fin", "x": 410, "y": 58, "label": "Stock Ajustado"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 19), (372, 19, 403, 58)],
    )

    # POE-ADM-03
    agregar_ficha_procedimiento_apa(
        story, est, 10, "POE-ADM-03", "Generación Automática de Pedido a Fábrica (Planilla de Reposición)",
        "Calcular la reposición óptima de artículos en quiebre o cercanos al stock mínimo.",
        "Bases SQLite (saldos vigentes)", "Umbrales de stock mínimo/máximo configurados",
        "Planilla Excel oficial con formato corporativo de pedido a proveedores", "Proveedores / Compras",
        "R: Administrador | A: Gerencia Operaciones",
        ["Catálogo maestro debidamente parametrizado con niveles de stock de seguridad."],
        [
            "En el menú de navegación lateral, se pulsa <b>'Generar pedido fábrica (Excel)'</b>.",
            "El sistema filtra automáticamente los artículos en quiebre o con saldo inferior al stock mínimo.",
            "Se examinan las cantidades calculadas y se efectúan ajustes estacionales si correspondiere.",
            "Se presiona el comando <b>'Generar Pedido a Fábrica'</b> y se descarga la planilla oficial para compras.",
        ],
        ["Planilla formal exportada en la carpeta Descuentos/.", "Registro de la solicitud en el historial."],
        "Cantidad sugerida suficiente para cubrir el período de abastecimiento sin superar el stock máximo.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 7, "Flujograma BPMN 2.0: Pedido Automático a Proveedores (POE-ADM-03)",
        lanes=["Administrador", "Sistema StockAgent", "Área de Compras"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Quiebre"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Filtrar Saldos", "Calcular Brechas"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Demanda OK?"},
            {"tipo": "tarea", "x": 230, "y": 96, "w": 62, "h": 22, "texto": ["Revisión Supervisor", "Ajuste Estacional"]},
            {"tipo": "tarea", "x": 315, "y": 19, "w": 62, "h": 22, "texto": ["Exportar Excel", "Despachar a Fab."]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Pedido Listo"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 96), (292, 96, 315, 19), (377, 19, 403, 19)],
    )

    story.append(PageBreak())

    # POE-ADM-04
    agregar_ficha_procedimiento_apa(
        story, est, 11, "POE-ADM-04", "Analítica, Radar de Anomalías y Optimización de Picking (Slotting ABC)",
        "Supervisar desvíos de demanda y optimizar la disposición espacial ergonómica del depósito.",
        "Historial de movimientos (`stock_movements`)", "Historial de pedidos despachados",
        "Alertas tempranas de agotamiento, mapa de calor térmico, plan de reubicación", "Jefatura de Depósito",
        "R: Administrador | I: Operarios",
        ["Registro histórico mínimo de 14 días para análisis estadístico representativo."],
        [
            "En 'Radar de anomalías', se monitorean picos de demanda (> μ + 2σ) y coberturas críticas menores a tres días.",
            "En 'Heatmap y Picking', se inspecciona la matriz Pareto ABC (75% A, 15% B, 10% C).",
            "Se constata la ubicación de artículos Clase A. Se pulsa <b>'Reubicar'</b> hacia la <i>Golden Zone</i> ergonómica.",
        ],
        ["Ubicaciones físicas actualizadas en SQLite.", "Disminución comprobada en los tiempos de recorrido de operarios."],
        "Índice de eficiencia de slotting superior al 85% y reducción de fatiga en operarios.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 8, "Flujograma BPMN 2.0: Radar de Anomalías y Slotting (POE-ADM-04)",
        lanes=["Administrador", "Sistema StockAgent", "Depósito Operativo"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Supervisión"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Evaluar Pareto ABC", "Detectar Desvíos"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Anomalía?"},
            {"tipo": "tarea", "x": 230, "y": 96, "w": 62, "h": 22, "texto": ["Ajustar Slotting", "Golden Zone"]},
            {"tipo": "tarea", "x": 315, "y": 19, "w": 62, "h": 22, "texto": ["Reubicar Racks", "Notificar Operador"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Picking OK"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 96), (292, 96, 315, 19), (377, 19, 403, 19)],
    )

    # CAPÍTULO 5: PROCEDIMIENTOS TÉCNICOS (ROL MASTER)
    story.append(PageBreak())
    story.append(Paragraph("5. Procedimientos Técnicos, IAM y Auditoría Forense (Rol Master)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    # POE-MAS-01
    agregar_ficha_procedimiento_apa(
        story, est, 12, "POE-MAS-01", "Gestión Global de Identidades y Accesos (IAM Supremo)",
        "Administrar el ciclo de vida de credenciales, roles privilegiados y desbloqueos administrativos.",
        "Dirección TI / RRHH", "Solicitud de alta o reseteo de cuenta Administrador",
        "Cuentas activas en tabla `users`, claves con hash criptográfico PBKDF2-SHA256", "Administradores de área",
        "R: Master | A: Dirección TI",
        ["Autenticación de dos factores o verificación de identidad de Master verificada."],
        [
            "En la sección 'Gestionar usuarios', se procede al alta de cuentas para los roles Administrador, Operador o Consulta.",
            "Para reseteo de claves: se genera contraseña temporal marcando con carácter forzoso `must_change_password = 1`.",
            "Se desbloquean de forma inmediata las cuentas bloqueadas por fuerza bruta (5 fallos) sin esperar la ventana de 15 min.",
        ],
        ["Registro inmutable en `logs_auditoria` con usuario, dirección IP y sello de tiempo."],
        "Las contraseñas deben cumplir longitud mínima de 10 caracteres con complejidad alfanumérica.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 9, "Flujograma BPMN 2.0: Gestión de Identidades IAM (POE-MAS-01)",
        lanes=["Solicitante / RRHH", "Usuario Master", "Motor de Seguridad IAM"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Solicitud"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Validar Legajo", "Asignar Perfil"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Aprobado?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Generar PBKDF2", "Asentar Audit"]},
            {"tipo": "tarea", "x": 315, "y": 96, "w": 62, "h": 22, "texto": ["Entregar Clave", "Forzar Cambio"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Cuenta OK"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 19), (292, 19, 315, 96), (377, 96, 403, 96)],
    )

    story.append(PageBreak())

    # POE-MAS-02
    agregar_ficha_procedimiento_apa(
        story, est, 13, "POE-MAS-02", "Restauración Documental y Rollback de Lotes (Exclusivo Master)",
        "Revertir operaciones erróneas o lotes históricos recomponiendo atómicamente el catálogo.",
        "Solicitud formal de Administrador", "Fecha de descuento y número de comprobante",
        "Catálogo Productos.xlsx y SQLite reconstituidos al estado previo exacto", "Contabilidad / Auditoría",
        "R: Master | A: Dirección Operaciones",
        ["Solicitud fundamentada por escrito y autorizada por la Gerencia de Operaciones."],
        [
            "En la barra lateral bajo <i>Resguardo y Continuidad</i>, se pulsa el comando <b>'Restaurar documentos'</b>.",
            "Se selecciona con precisión la fecha y el lote histórico que se requiere deshacer.",
            "Se presiona <b>'Previsualizar Rollback'</b> para constatar las unidades que retornarán al inventario.",
            "Se confirma la operación mediante <b>'Restaurar Catálogo'</b>: el motor recompone SQLite y Productos.xlsx.",
        ],
        ["Existencias físicas incrementadas en el inventario.", "Registro forense inmutable de rollback."],
        "Verificación de integridad estructural de base de datos ejecutando `PRAGMA integrity_check`.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 10, "Flujograma BPMN 2.0: Restauración y Rollback SoD (POE-MAS-02)",
        lanes=["Administrador", "Usuario Master (SoD)", "Motor Criptográfico"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Petición"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Analizar Motivo", "Previsualizar"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Auditoría OK?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Eliminar Hash", "Reponer Stock"]},
            {"tipo": "tarea", "x": 315, "y": 58, "w": 62, "h": 22, "texto": ["Registrar Log", "Notificar Admin"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Rollback OK"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 19), (292, 19, 315, 58), (377, 58, 403, 96)],
    )

    # POE-MAS-03
    agregar_ficha_procedimiento_apa(
        story, est, 14, "POE-MAS-03", "Continuidad del Negocio y Recuperación de Desastres (Disaster Recovery)",
        "Asegurar la alta disponibilidad del sistema mediante respaldos comprimidos y réplica espejo secundaria.",
        "Sistema StockAgent en producción", "Bases SQLite (`pedidos`, `usuarios`, `productos`) y catálogo Excel",
        "Archivo comprimido `.zip` en `data/backups/` y réplica en servidor NAS / Nube", "Toda la Organización",
        "R: Master | A: Gerencia TI",
        ["Ruta espejo secundaria configurada y con permisos de escritura activos (Regla de Respaldo 3-2-1)."],
        [
            "En 'Copia de Seguridad', se acciona el respaldo manual o se valida la ejecución automática del cierre.",
            "Se verifica la réplica atómica del archivo `.zip` hacia el almacenamiento externo secundario.",
            "Se audita la política de rotación que conserva las últimas 30 versiones suprimiendo las precedentes.",
        ],
        ["Respaldo íntegro resguardado en dos ubicaciones físicas independientes."],
        "Ejecución satisfactoria de prueba semestral de restauración en entorno de aislamiento (Sandbox).",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 11, "Flujograma BPMN 2.0: Continuidad y Respaldo 3-2-1 (POE-MAS-03)",
        lanes=["Usuario Master", "Sistema StockAgent", "Almacenamiento Red NAS"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Disparador"},
            {"tipo": "tarea", "x": 118, "y": 58, "w": 58, "h": 22, "texto": ["Comprimir Bases", "Verificar Integridad"]},
            {"tipo": "decision", "x": 195, "y": 58, "label": "¿Check OK?"},
            {"tipo": "tarea", "x": 230, "y": 19, "w": 62, "h": 22, "texto": ["Replicar Espejo", "Rotar Versiones"]},
            {"tipo": "tarea", "x": 315, "y": 96, "w": 62, "h": 22, "texto": ["Auditar Sandbox", "Firmar Acta"]},
            {"tipo": "fin", "x": 410, "y": 96, "label": "Backup OK"},
        ],
        flujos=[(111.5, 96, 118, 58), (176, 58, 186, 58), (204, 58, 230, 19), (292, 19, 315, 96), (377, 96, 403, 96)],
    )

    # CAPÍTULO 6: PROCEDIMIENTOS DE CONSULTA (ROL CONSULTA)
    story.append(PageBreak())
    story.append(Paragraph("6. Procedimientos de Consulta Externa (Rol Consulta)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_ficha_procedimiento_apa(
        story, est, 15, "POE-CON-01", "Búsqueda de Existencias y Ubicación de Artículos en Tiempo Real",
        "Consultar saldos disponibles, descripción y posición física en estanterías.",
        "Vendedores / Clientes", "Código SKU, código de barras o descripción",
        "Información de stock disponible y ubicación física en estantería (Rack/Nivel)", "Cliente / Mostrador",
        "R: Vendedor / Auditor | I: Depósito",
        ["Sesión de Consulta debidamente autenticada."],
        [
            "Se acciona la combinación <code>Ctrl + K</code> o la tecla <code>F2</code> para abrir la Paleta de Búsqueda Rápida.",
            "Se ingresa el código o término de búsqueda. El motor de consulta filtra en vivo en menos de 0.05 segundos.",
            "Se verifica el saldo disponible y se visualiza la ubicación física en estantería (ej. <code>Rack B, Mod 2, Niv 1</code>).",
        ],
        ["Consulta registrada en logs sin alteración de datos contables."],
        "Concordancia exacta entre el saldo visualizado en pantalla y el registro activo en SQLite.",
    )
    agregar_diagrama_bpmn_apa(
        story, est, 12, "Flujograma BPMN 2.0: Consulta Rápida de Inventario (POE-CON-01)",
        lanes=["Usuario Consulta", "Motor StockAgent", "Mostrador Comercial"],
        nodos=[
            {"tipo": "inicio", "x": 105, "y": 96, "label": "Consulta"},
            {"tipo": "tarea", "x": 118, "y": 96, "w": 58, "h": 22, "texto": ["Presionar F2", "Ingresar SKU"]},
            {"tipo": "tarea", "x": 195, "y": 58, "w": 62, "h": 22, "texto": ["Búsqueda SQLite", "Localizar Rack"]},
            {"tipo": "decision", "x": 280, "y": 58, "label": "¿Hay Saldo?"},
            {"tipo": "tarea", "x": 310, "y": 19, "w": 62, "h": 22, "texto": ["Mostrar Stock", "Informar Cliente"]},
            {"tipo": "fin", "x": 410, "y": 19, "label": "Fin Consulta"},
        ],
        flujos=[(111.5, 96, 118, 96), (176, 96, 195, 58), (257, 58, 271, 58), (289, 58, 310, 19), (372, 19, 403, 19)],
    )

    # CAPÍTULO 7: GESTIÓN DEL CAMBIO Y NUEVOS MÓDULOS (POE-SGC-01)
    story.append(PageBreak())
    story.append(Paragraph("7. Gestión del Cambio, Nuevos Módulos y Actualización Documental (ISO 9001 §8.5.6)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_procedimiento_gestion_cambio_sgc(story, est, 16, 13)

    # CAPÍTULO 8: MATRIZ CONSOLIDADA DE REGISTROS DE CALIDAD (ISO 9001 §7.5.3)
    story.append(PageBreak())
    story.append(Paragraph("8. Matriz Consolidada de Control de Registros de Calidad (ISO 9001 §7.5.3)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    story.append(Paragraph("<b>Tabla 17</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Matriz Consolidada de Información Documentada y Tiempos de Retención Legal</i>", est["apa_tabla_titulo"]))

    headers_reg_mae = [
        Paragraph("<b>Registro de Calidad</b>", est["th_apa"]),
        Paragraph("<b>Soporte</b>", est["th_apa"]),
        Paragraph("<b>Ubicación de Custodia</b>", est["th_apa"]),
        Paragraph("<b>Retención</b>", est["th_apa"]),
        Paragraph("<b>Responsable</b>", est["th_apa"]),
    ]
    filas_reg_mae = [
        ("Transacción de Pedido y Descuento", "Digital (SQLite)", "data/pedidos.sqlite3 (tabla `pedidos`)", "5 Años", "Administrador / Master"),
        ("Comprobante Digitalizado (PDF/Excel)", "Archivo binario", "data/pedidos_archivos/", "5 Años", "Administrador"),
        ("Hoja de Ruta Firmada por Chofer", "Documento papel", "Archivador de Logística en Depósito", "2 Años", "Encargado de Despacho"),
        ("Informe Consolidado de Cierre", "PDF y XLS", "Descuentos/ y data/pedidos_archivos/", "5 Años", "Jefe de Depósito"),
        ("Base de Datos Maestra de Productos", "SQLite (`productos.sqlite3`)", "data/productos.sqlite3", "Permanente", "Master / Admin"),
        ("Auditoría Forense y Logs de Seguridad", "SQLite inmutable", "data/pedidos.sqlite3 (`logs_auditoria`)", "10 Años", "Master"),
        ("Copia de Seguridad Integral", "Archivo .zip", "data/backups/ y Mirror en Red", "1 Año (Rotación 30)", "Master"),
    ]
    t_reg_mdata = [headers_reg_mae]
    for r1, r2, r3, r4, r5 in filas_reg_mae:
        t_reg_mdata.append([Paragraph(f"<b>{r1}</b>", est["td_apa"]), Paragraph(r2, est["td_apa_center"]), Paragraph(r3, est["td_apa"]), Paragraph(r4, est["td_apa_center"]), Paragraph(r5, est["td_apa"])])
    t_reg_m = Table(t_reg_mdata, colWidths=[3.8 * cm, 2.2 * cm, 4.2 * cm, 2.0 * cm, 3.3 * cm])
    aplicar_estilo_tabla_apa(t_reg_m, len(t_reg_mdata))
    story.append(t_reg_m)
    story.append(Paragraph("<i>Nota.</i> Control documental bajo Cláusula 7.5.3 de la Norma ISO 9001:2015 y 8.15 de ISO/IEC 27001.", est["apa_tabla_nota"]))

    # CAPÍTULO 9: GESTIÓN DE NO CONFORMIDADES (ISO 9001 §10.2)
    story.append(Spacer(1, 4))
    story.append(Paragraph("9. Gestión de No Conformidades y Acciones Correctivas (ISO 9001 §10.2)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    story.append(Paragraph("<b>Tabla 18</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Matriz Maestra de Contingencias, Causa Raíz y Acciones Correctivas</i>", est["apa_tabla_titulo"]))

    headers_err_mae = [
        Paragraph("<b>No Conformidad</b>", est["th_apa"]),
        Paragraph("<b>Causa Raíz</b>", est["th_apa"]),
        Paragraph("<b>Acción Inmediata (Corrección)</b>", est["th_apa"]),
        Paragraph("<b>Acción Preventiva</b>", est["th_apa"]),
    ]
    filas_err_mae = [
        ("NC-OPE-01: Hash Duplicado", "Reingreso involuntario de comprobante.", "El sistema rechaza la carga informando fecha previa.", "Revisar Historial. La modificación de nombre no evade SHA-256."),
        ("NC-OPE-02: Quiebre de Stock", "Demanda superior al saldo en SQLite.", "El sistema abre advertencia previa de confirmación.", "Autorizar solo si hay ingreso pendiente o solicitar a Compras."),
        ("NC-OPE-03: Desarme por Rechazo", "Cancelación de pedido por cliente.", "Presionar botón ámbar 'Desarmar pedido'.", "El stock retorna al instante a SQLite y Productos.xlsx con log."),
        ("NC-ADM-01: Discrepancia Físico", "Ajuste no registrado o merma.", "Aplicar ajuste justificado con remito interno.", "Capacitar en registro oportuno de mermas."),
        ("NC-ADM-02: Agotamiento Inesperado", "Pico extraordinario de ventas online.", "Emitir pedido urgente a fábrica con POE-ADM-03.", "Ajustar umbral de Stock Mínimo en catálogo."),
    ]
    t_err_mdata = [headers_err_mae]
    for e1, e2, e3, e4 in filas_err_mae:
        t_err_mdata.append([Paragraph(f"<b>{e1}</b>", est["td_apa_bold_center"]), Paragraph(e2, est["td_apa"]), Paragraph(e3, est["td_apa"]), Paragraph(e4, est["td_apa"])])
    t_err_m = Table(t_err_mdata, colWidths=[3.0 * cm, 3.5 * cm, 4.5 * cm, 4.5 * cm])
    aplicar_estilo_tabla_apa(t_err_m, len(t_err_mdata))
    story.append(t_err_m)
    story.append(Paragraph("<i>Nota.</i> Acciones correctivas formalizadas según la Cláusula 10.2 de la Norma ISO 9001:2015.", est["apa_tabla_nota"]))

    # CAPÍTULO 10: INDICADORES KPIS (ISO 9001 §9.1)
    story.append(Spacer(1, 4))
    story.append(Paragraph("10. Indicadores Clave de Desempeño Operacional (KPIs - ISO 9001 §9.1)", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    story.append(Paragraph("<b>Tabla 19</b>", est["apa_tabla_num"]))
    story.append(Paragraph("<i>Indicadores Clave de Desempeño de Calidad y Logística Integral</i>", est["apa_tabla_titulo"]))

    headers_kpi_m = [
        Paragraph("<b>Indicador (KPI)</b>", est["th_apa"]),
        Paragraph("<b>Objetivo</b>", est["th_apa"]),
        Paragraph("<b>Fórmula de Medición</b>", est["th_apa"]),
        Paragraph("<b>Meta</b>", est["th_apa"]),
        Paragraph("<b>Frecuencia</b>", est["th_apa"]),
    ]
    filas_kpi_m = [
        ("Tiempo de Carga Remito", "Velocidad de procesamiento.", "Minutos transcurridos desde subida a rotulación.", "< 45 seg.", "Continua"),
        ("Filtro SHA-256", "Efectividad anti-duplicados.", "(Duplicados interceptados / Total intentos) * 100", "100%", "Por Jornada"),
        ("Exactitud Empaque", "Concordancia bultos físicos vs remito.", "(Pedidos modificados / Total pedidos) * 100", "< 2%", "Mensual"),
        ("Disponibilidad Servidor", "Continuidad de servicio LAN.", "(Horas activas / Horas totales de operación) * 100", "> 99.8%", "Mensual"),
    ]
    t_kpi_mdata = [headers_kpi_m]
    for k1, k2, k3, k4, k5 in filas_kpi_m:
        t_kpi_mdata.append([Paragraph(f"<b>{k1}</b>", est["td_apa_bold_center"]), Paragraph(k2, est["td_apa"]), Paragraph(k3, est["td_apa"]), Paragraph(k4, est["td_apa_center"]), Paragraph(k5, est["td_apa_center"])])
    t_kpi_m = Table(t_kpi_mdata, colWidths=[3.2 * cm, 3.5 * cm, 4.2 * cm, 2.3 * cm, 2.3 * cm])
    aplicar_estilo_tabla_apa(t_kpi_m, len(t_kpi_mdata))
    story.append(t_kpi_m)
    story.append(Paragraph("<i>Nota.</i> Medición evaluada mensualmente por la Jefatura de Calidad y Dirección de Operaciones.", est["apa_tabla_nota"]))

    # SECCIONES FINALES NORMALIZADAS (INFRAESTRUCTURA, DISTRIBUCIÓN, FIRMAS, ACTA, CHEAT SHEET, GLOSARIO Y REFERENCIAS)
    story.append(PageBreak())
    story.append(Paragraph("11. Infraestructura, Control de Distribución y Firmas Autorizadas", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_requisitos_infraestructura_iso(story, est)
    agregar_matriz_distribucion_copias(story, est, 20)
    agregar_formulario_firmas_autorizadas_iso(story, est, 21)

    story.append(PageBreak())
    story.append(Paragraph("12. Registros de Inducción, Tarjeta de Referencia y Anexos Finales", est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))

    agregar_acta_capacitacion_personal(story, est, 22)
    agregar_tarjeta_referencia_rapida(story, est)
    agregar_glosario_terminos_iso_upel(story, est)
    agregar_referencias_bibliograficas_apa_upel(story, est)

    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, "v2.1.0"))
    return ruta_destino


def construir_manual_general(ruta_destino: Path) -> Path:
    """Función para compilar el Manual General Consolidado (invoca el compendio maestro)."""
    return construir_manual_maestro_imprimible(ruta_destino)


def construir_pdf(ruta_destino: Path) -> Path:
    """Función de enlace para compilar el manual general consolidado."""
    return construir_manual_maestro_imprimible(ruta_destino)


def generar_todos_los_manuales(directorio_destino: Path | str | None = None) -> dict[str, Path]:
    """Genera todos los manuales normalizados bajo ISO 9001:2015, ISO/IEC/IEEE 26514, ISO 27001, BPMN 2.0 y APA/UPEL."""
    base_dir = Path(directorio_destino) if directorio_destino else Path("Documentacion")
    base_dir.mkdir(parents=True, exist_ok=True)

    rutas = {
        "operador": base_dir / "Manual_Operador.pdf",
        "administrador": base_dir / "Manual_Administrador.pdf",
        "master": base_dir / "Manual_Master.pdf",
        "consulta": base_dir / "Manual_Consulta.pdf",
        "general": base_dir / "Manual_General.pdf",
        "maestro": base_dir / "Manual_Maestro_Imprimible.pdf",
    }

    construir_manual_operador(rutas["operador"])
    construir_manual_administrador(rutas["administrador"])
    construir_manual_master(rutas["master"])
    construir_manual_consulta(rutas["consulta"])
    construir_manual_maestro_imprimible(rutas["general"])
    construir_manual_maestro_imprimible(rutas["maestro"])

    # Enlace adicional por retrocompatibilidad
    ruta_legacy = base_dir / "Manual_de_Uso_StockAgent.pdf"
    construir_manual_maestro_imprimible(ruta_legacy)

    return rutas


if __name__ == "__main__":
    print("Compilando todos los manuales bajo normas ISO 9001, ISO 26514, BPMN 2.0 y APA / UPEL...")
    res = generar_todos_los_manuales()
    print("=== MANUALES GENERADOS EXITOSAMENTE BAJO NORMAS ISO, BPMN Y APA / UPEL ===")
    for k, v in res.items():
        print(f"[{k.upper():13}] -> {v.name:28} ({v.stat().st_size} bytes)")
