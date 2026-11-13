# -*- coding: utf-8 -*-
"""Componentes reutilizables APA 7 / UPEL y motor vectorial BPMN 2.0."""

from __future__ import annotations

from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from .constants import (
    ANCHO_UTIL,
    COLOR_ACENTO_ROJO,
    COLOR_BG_ALERT,
    COLOR_BG_NOTE,
    COLOR_BORDE_APA,
    COLOR_FONDO_TABLA,
    COLOR_PRIMARIO,
    COLOR_SECUNDARIO,
    COLOR_TEXTO,
)


def crear_caja_alerta_iso(titulo: str, texto: str, tipo: str = "nota") -> Table:
    """Genera una caja técnica destacada para notas normativas o de seguridad SoD."""
    color_borde = (
        COLOR_ACENTO_ROJO
        if tipo == "sod"
        else (COLOR_SECUNDARIO if tipo == "nota" else colors.HexColor("#16A34A"))
    )
    color_bg = (
        COLOR_BG_ALERT
        if tipo == "sod"
        else (COLOR_BG_NOTE if tipo == "nota" else colors.HexColor("#F0FDF4"))
    )

    estilo_caja = ParagraphStyle(
        name=f"CajaISOUPEL_{tipo}_{hash(titulo + texto)}",
        fontName="Helvetica",
        fontSize=8.0,
        leading=11.2,
        textColor=COLOR_TEXTO,
    )

    html = f"<font color='{color_borde.hexval()}'><b>{escape(titulo)}</b></font><br/>{texto}"
    t = Table([[Paragraph(html, estilo_caja)]], colWidths=[ANCHO_UTIL])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), color_bg),
            ("LINEBEFORE", (0, 0), (0, -1), 3.0, color_borde),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    return t


def aplicar_estilo_tabla_apa(tabla: Table, filas_totales: int) -> Table:
    """Aplica rigurosamente las pautas de presentación de tablas APA 7ma / UPEL."""
    estilos = [
        ("INNERGRID", (0, 0), (-1, -1), 0, colors.transparent),
        ("BOX", (0, 0), (-1, -1), 0, colors.transparent),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, COLOR_BORDE_APA),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, COLOR_BORDE_APA),
        ("LINEBELOW", (0, filas_totales - 1), (-1, filas_totales - 1), 1.0, COLOR_BORDE_APA),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.2),
    ]
    for i in range(1, filas_totales):
        if i % 2 == 1:
            estilos.append(("BACKGROUND", (0, i), (-1, i), COLOR_FONDO_TABLA))
    tabla.setStyle(TableStyle(estilos))
    return tabla


def agregar_tabla_apa_completa(
    story: list,
    est: dict,
    num_tabla: int,
    titulo_tabla: str,
    data: list[list],
    col_widths: list[float],
    nota: str,
    repeat_rows: int = 0,
) -> None:
    """Inserta título APA, tabla estilizada y nota al pie en un único bloque coherente."""
    story.append(Paragraph(f"<b>Tabla {num_tabla}</b>", est["apa_tabla_num"]))
    story.append(Paragraph(f"<i>{titulo_tabla}</i>", est["apa_tabla_titulo"]))
    kwargs = {"repeatRows": repeat_rows} if repeat_rows else {}
    tabla = Table(data, colWidths=col_widths, **kwargs)
    aplicar_estilo_tabla_apa(tabla, len(data))
    story.append(tabla)
    story.append(Paragraph(f"<i>Nota.</i> {nota}", est["apa_tabla_nota"]))


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
    d.add(Rect(0, 0, ancho, alto, fillColor=colors.HexColor("#FFFFFF"), strokeColor=COLOR_PRIMARIO, strokeWidth=1.0))

    lane_h = alto / len(lanes)
    ancho_pool_header = 16
    ancho_lane_header = 78

    d.add(Rect(0, 0, ancho_pool_header, alto, fillColor=COLOR_PRIMARIO, strokeColor=COLOR_PRIMARIO))
    d.add(String(ancho_pool_header / 2 + 1, alto / 2, "POOL", textAnchor="middle", fontName="Helvetica-Bold", fontSize=6.0, fillColor=colors.HexColor("#FFFFFF")))
    d.add(Rect(ancho_pool_header, 0, ancho_lane_header, alto, fillColor=colors.HexColor("#F1F5F9"), strokeColor=colors.HexColor("#64748B"), strokeWidth=0.8))

    for i, lane_name in enumerate(reversed(lanes)):
        y = i * lane_h
        if i > 0:
            d.add(Line(ancho_pool_header, y, ancho, y, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=0.7, strokeDashArray=[3, 2]))
        d.add(String(ancho_pool_header + 4, y + lane_h / 2 - 2.5, lane_name, fontName="Helvetica-Bold", fontSize=6.2, fillColor=COLOR_SECUNDARIO))

    for x1, y1, x2, y2 in flujos:
        d.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#475569"), strokeWidth=0.9))
        if x2 > x1 and abs(y1 - y2) < 2:
            pts = [x2, y2, x2 - 4.5, y2 + 2.5, x2 - 4.5, y2 - 2.5]
        elif x2 == x1 and y2 < y1:
            pts = [x2, y2, x2 - 2.5, y2 + 4.5, x2 + 2.5, y2 + 4.5]
        elif x2 == x1 and y2 > y1:
            pts = [x2, y2, x2 - 2.5, y2 - 4.5, x2 + 2.5, y2 - 4.5]
        elif x2 > x1 and y2 < y1:
            pts = [x2, y2, x2 - 4.5, y2 + 3.0, x2 - 3.0, y2 - 3.5]
        elif x2 > x1 and y2 > y1:
            pts = [x2, y2, x2 - 4.5, y2 - 3.0, x2 - 3.0, y2 + 3.5]
        else:
            pts = [x2, y2, x2 - 4.5, y2 + 2.5, x2 - 4.5, y2 - 2.5]
        d.add(Polygon(pts, fillColor=colors.HexColor("#475569"), strokeColor=None))

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
) -> None:
    """Inserta formalmente un diagrama de flujo BPMN 2.0 en el cuerpo del manual bajo formato APA 7 / UPEL."""
    story.append(Paragraph(f"<b>Figura {num_figura}</b>", est["apa_figura_num"]))
    story.append(Paragraph(f"<i>{escape(titulo_figura)}</i>", est["apa_figura_titulo"]))
    dibujo = crear_dibujo_bpmn_swimlanes(titulo_figura, lanes, nodos, flujos, ancho=ANCHO_UTIL, alto=alto)
    story.append(dibujo)
    story.append(Paragraph(f"<i>Nota.</i> {escape(nota)}", est["apa_tabla_nota"]))
    story.append(Spacer(1, 3))


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
) -> None:
    """Inserta un Procedimiento Operativo Estandarizado (SOP) formal con tabla SIPOC reglamentaria APA/UPEL."""
    story.append(Paragraph(f"<b>{escape(codigo_proc)}: {escape(nombre_proc)}</b>", est["h2"]))
    story.append(Paragraph(f"<b>Objetivo Operativo:</b> {escape(objetivo)}", est["body_sangria"]))

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
    story.append(Paragraph("<i>Nota.</i> R: Responsable de ejecución, A: Autoridad de aprobación, C: Consultado, I: Informado.", est["apa_tabla_nota"]))

    if precondiciones:
        story.append(Paragraph("<b>Condiciones Previas del Entorno Operativo:</b>", est["h3"]))
        for pre in precondiciones:
            story.append(Paragraph(f"• {pre}", est["bullet"]))

    story.append(Paragraph("<b>Secuencia Operativa Estandarizada (Paso a Paso):</b>", est["h3"]))
    for p in pasos:
        story.append(Paragraph(f"• {p}", est["bullet"]))

    if postcondiciones:
        story.append(Paragraph("<b>Resultados y Postcondiciones del Sistema:</b>", est["h3"]))
        for post in postcondiciones:
            story.append(Paragraph(f"• {post}", est["bullet"]))

    story.append(Paragraph(f"<b>Criterio de Aceptación y Validación de Calidad:</b> {escape(control_calidad)}", est["body_sangria"]))
    story.append(Spacer(1, 3))
