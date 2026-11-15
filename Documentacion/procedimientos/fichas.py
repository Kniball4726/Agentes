# -*- coding: utf-8 -*-
"""Plantilla común de fichas botón-por-botón y armado de manuales procedimentales."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

_doc_dir = Path(__file__).resolve().parent.parent
_root_dir = _doc_dir.parent
for _p in (str(_root_dir), str(_doc_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from reportlab.lib import colors
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from Documentacion.pdf_engine.canvas_iso import crear_canvas_iso_upel
from Documentacion.pdf_engine.constants import (
    COLOR_PRIMARIO,
    COLOR_SECUNDARIO,
    crear_documento_iso,
)
from Documentacion.pdf_engine.forms_sgc import (
    agregar_acta_capacitacion_personal,
    agregar_formulario_firmas_autorizadas_iso,
    agregar_matriz_distribucion_copias,
    agregar_portada_iso_upel,
    agregar_tarjeta_referencia_rapida,
)

VERSION_PROC_ACTUAL = "3.2.0"


def agregar_ficha_boton(
    story: list,
    est: dict,
    nombre_boton: str,
    icono_str: str,
    modulo: str,
    proposito_funcional: str,
    datos_modificados: str,
    pasos_procedimiento: list[str],
    resultado_obtenido: str,
    validaciones_advertencias: str = "",
) -> None:
    """Inserta una ficha estandarizada de procedimiento y uso por botón."""
    celda_titulo = Paragraph(
        f"<b>{escape(icono_str)} BOTÓN: <font color='#D32F2F'>{escape(nombre_boton.upper())}</font></b>",
        est["h2"],
    )
    celda_modulo = Paragraph(
        f"<b>Sección / Módulo:</b><br/><i>{escape(modulo)}</i>",
        est["meta_bold"],
    )
    celda_proposito = Paragraph(
        f"<b>1. ¿Qué hace y funcionalidad?</b><br/>{proposito_funcional}",
        est["body"],
    )
    celda_modifica = Paragraph(
        f"<b>2. Registros y archivos que modifica:</b><br/>{datos_modificados}",
        est["body"],
    )

    pasos_html = "<b>3. Procedimiento operativo paso a paso:</b><br/>" + "<br/>".join(
        f"<b>{i}.</b> {p}" for i, p in enumerate(pasos_procedimiento, 1)
    )
    celda_pasos = Paragraph(pasos_html, est["body"])

    res_html = f"<b>4. Resultado obtenido / Comprobante:</b><br/>{resultado_obtenido}"
    if validaciones_advertencias:
        res_html += f"<br/><br/><b>5. Reglas y Advertencias:</b><br/>{validaciones_advertencias}"
    celda_resultado = Paragraph(res_html, est["body"])

    tabla_datos = [
        [celda_titulo, celda_modulo],
        [celda_proposito, celda_modifica],
        [celda_pasos, celda_resultado],
    ]
    t = Table(tabla_datos, colWidths=[9.0 * 28.3465, 6.5 * 28.3465])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("LINEBELOW", (0, 0), (-1, 0), 1.2, COLOR_SECUNDARIO),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(KeepTogether([t]))
    story.append(Spacer(1, 6))


def agregar_fichas_modulo(
    story: list,
    est: dict,
    titulo_modulo: str,
    fichas: Iterable[dict],
    intro_texto: str | None = None,
    page_break: bool = False,
) -> None:
    """Agrega un capítulo con filete horizontal, introducción opcional y lote de fichas."""
    if page_break:
        story.append(PageBreak())
    story.append(Paragraph(titulo_modulo, est["h1"]))
    story.append(HRFlowable(width="100%", thickness=1.0, color=COLOR_PRIMARIO, spaceBefore=2, spaceAfter=4))
    if intro_texto:
        story.append(Paragraph(intro_texto, est["body_sangria"]))
        story.append(Spacer(1, 4))
    for f in fichas:
        agregar_ficha_boton(story, est, **f)


def construir_cierre_manual_rol(
    doc,
    story: list,
    est: dict,
    codigo_doc: str,
    titulo_doc: str,
    ruta_destino: Path,
    *,
    incluir_distribucion: bool = True,
    incluir_acta: bool = False,
    version: str = VERSION_PROC_ACTUAL,
) -> Path:
    """Añade anexos finales normalizados (Cheat Sheet, Firmas, Distribución, Acta) y compila el PDF."""
    story.append(Spacer(1, 6))
    agregar_tarjeta_referencia_rapida(story, est)
    story.append(PageBreak())
    agregar_formulario_firmas_autorizadas_iso(story, est, 2)
    if incluir_distribucion:
        agregar_matriz_distribucion_copias(story, est, 3)
    if incluir_acta:
        agregar_acta_capacitacion_personal(story, est, 4)
    doc.build(story, canvasmaker=crear_canvas_iso_upel(codigo_doc, titulo_doc, version))
    return ruta_destino


def iniciar_manual_rol(
    ruta_destino: Path,
    codigo_doc: str,
    titulo_doc: str,
    rol_destinatario: str,
    descripcion_alcance: str,
    version: str = VERSION_PROC_ACTUAL,
):
    """Inicializa documento A4 UPEL y añade portada formal ISO para un manual de rol."""
    doc, est, story = crear_documento_iso(ruta_destino)
    agregar_portada_iso_upel(
        story, est, codigo_doc, titulo_doc, rol_destinatario, descripcion_alcance, version=version
    )
    return doc, est, story


__all__ = [
    "VERSION_PROC_ACTUAL",
    "agregar_ficha_boton",
    "agregar_fichas_modulo",
    "construir_cierre_manual_rol",
    "iniciar_manual_rol",
]
