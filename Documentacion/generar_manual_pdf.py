# -*- coding: utf-8 -*-
"""Fachada retrocompatible del generador de manuales ISO 9001, ISO 26514, BPMN 2.0 y APA/UPEL.

Delegado en los submódulos de ``Documentacion.pdf_engine`` manteniendo el mismo espacio
de nombres público para compilaciones CLI, backend web y pruebas automatizadas.
"""

from __future__ import annotations

import sys
from pathlib import Path

_doc_dir = Path(__file__).resolve().parent
_root_dir = _doc_dir.parent
for _p in (str(_root_dir), str(_doc_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from .pdf_engine import (
        ALTO_PAGINA,
        ANCHO_PAGINA,
        ANCHO_UTIL,
        COLOR_ACENTO_ROJO,
        COLOR_BG_ALERT,
        COLOR_BG_NOTE,
        COLOR_BORDE_APA,
        COLOR_FONDO_TABLA,
        COLOR_PRIMARIO,
        COLOR_SECUNDARIO,
        COLOR_TEXTO,
        COLOR_TEXTO_MUTED,
        MARGEN_DER,
        MARGEN_INF,
        MARGEN_IZQ,
        MARGEN_SUP,
        agregar_acta_capacitacion_personal,
        agregar_diagrama_bpmn_apa,
        agregar_ficha_procedimiento_apa,
        agregar_formulario_firmas_autorizadas_iso,
        agregar_glosario_terminos_iso_upel,
        agregar_matriz_distribucion_copias,
        agregar_portada_iso_upel,
        agregar_procedimiento_gestion_cambio_sgc,
        agregar_referencias_bibliograficas_apa_upel,
        agregar_requisitos_infraestructura_iso,
        agregar_tarjeta_referencia_rapida,
        aplicar_estilo_tabla_apa,
        construir_manual_administrador,
        construir_manual_consulta,
        construir_manual_general,
        construir_manual_maestro_imprimible,
        construir_manual_master,
        construir_manual_operador,
        construir_pdf,
        crear_caja_alerta_iso,
        crear_canvas_iso_upel,
        crear_dibujo_bpmn_swimlanes,
        obtener_estilos_iso_upel,
    )
except ImportError:
    from pdf_engine import (
        ALTO_PAGINA,
        ANCHO_PAGINA,
        ANCHO_UTIL,
        COLOR_ACENTO_ROJO,
        COLOR_BG_ALERT,
        COLOR_BG_NOTE,
        COLOR_BORDE_APA,
        COLOR_FONDO_TABLA,
        COLOR_PRIMARIO,
        COLOR_SECUNDARIO,
        COLOR_TEXTO,
        COLOR_TEXTO_MUTED,
        MARGEN_DER,
        MARGEN_INF,
        MARGEN_IZQ,
        MARGEN_SUP,
        agregar_acta_capacitacion_personal,
        agregar_diagrama_bpmn_apa,
        agregar_ficha_procedimiento_apa,
        agregar_formulario_firmas_autorizadas_iso,
        agregar_glosario_terminos_iso_upel,
        agregar_matriz_distribucion_copias,
        agregar_portada_iso_upel,
        agregar_procedimiento_gestion_cambio_sgc,
        agregar_referencias_bibliograficas_apa_upel,
        agregar_requisitos_infraestructura_iso,
        agregar_tarjeta_referencia_rapida,
        aplicar_estilo_tabla_apa,
        construir_manual_administrador,
        construir_manual_consulta,
        construir_manual_general,
        construir_manual_maestro_imprimible,
        construir_manual_master,
        construir_manual_operador,
        construir_pdf,
        crear_caja_alerta_iso,
        crear_canvas_iso_upel,
        crear_dibujo_bpmn_swimlanes,
        obtener_estilos_iso_upel,
    )


def generar_todos_los_manuales(directorio_destino: Path | str | None = None) -> dict[str, Path]:
    """Genera todos los manuales de procedimiento y uso botón por botón en formato PDF."""
    try:
        from .manuales_procedimientos import generar_todos_los_manuales as _generar_proc
    except (ImportError, ValueError):
        from manuales_procedimientos import generar_todos_los_manuales as _generar_proc
    return _generar_proc(directorio_destino)


__all__ = [
    "ANCHO_PAGINA",
    "ALTO_PAGINA",
    "MARGEN_IZQ",
    "MARGEN_DER",
    "MARGEN_SUP",
    "MARGEN_INF",
    "ANCHO_UTIL",
    "COLOR_PRIMARIO",
    "COLOR_SECUNDARIO",
    "COLOR_ACENTO_ROJO",
    "COLOR_TEXTO",
    "COLOR_TEXTO_MUTED",
    "COLOR_BORDE_APA",
    "COLOR_FONDO_TABLA",
    "COLOR_BG_ALERT",
    "COLOR_BG_NOTE",
    "crear_canvas_iso_upel",
    "obtener_estilos_iso_upel",
    "crear_caja_alerta_iso",
    "aplicar_estilo_tabla_apa",
    "crear_dibujo_bpmn_swimlanes",
    "agregar_diagrama_bpmn_apa",
    "agregar_portada_iso_upel",
    "agregar_ficha_procedimiento_apa",
    "agregar_formulario_firmas_autorizadas_iso",
    "agregar_matriz_distribucion_copias",
    "agregar_acta_capacitacion_personal",
    "agregar_tarjeta_referencia_rapida",
    "agregar_requisitos_infraestructura_iso",
    "agregar_glosario_terminos_iso_upel",
    "agregar_referencias_bibliograficas_apa_upel",
    "agregar_procedimiento_gestion_cambio_sgc",
    "construir_manual_operador",
    "construir_manual_administrador",
    "construir_manual_master",
    "construir_manual_consulta",
    "construir_manual_maestro_imprimible",
    "construir_manual_general",
    "construir_pdf",
    "generar_todos_los_manuales",
]


if __name__ == "__main__":
    print("Compilando todos los manuales bajo normas ISO 9001, ISO 26514, BPMN 2.0 y APA / UPEL...")
    res = generar_todos_los_manuales()
    print("=== MANUALES GENERADOS EXITOSAMENTE BAJO NORMAS ISO, BPMN Y APA / UPEL ===")
    for k, v in res.items():
        print(f"[{k.upper():13}] -> {v.name:28} ({v.stat().st_size} bytes)")
