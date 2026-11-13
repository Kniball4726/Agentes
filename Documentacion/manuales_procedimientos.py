# -*- coding: utf-8 -*-
"""Fachada retrocompatible de los manuales procedimentales botón por botón.

Delega en los submódulos de ``Documentacion.procedimientos`` manteniendo intactas todas
las firmas públicas y el punto de entrada ``python -m Documentacion.manuales_procedimientos``.
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
    from .procedimientos import (
        VERSION_PROC_ACTUAL,
        agregar_ficha_boton,
        construir_manual_administrador,
        construir_manual_consulta,
        construir_manual_general,
        construir_manual_maestro_imprimible,
        construir_manual_master,
        construir_manual_operador,
        construir_manual_picker,
        generar_todos_los_manuales,
    )
except ImportError:
    from procedimientos import (
        VERSION_PROC_ACTUAL,
        agregar_ficha_boton,
        construir_manual_administrador,
        construir_manual_consulta,
        construir_manual_general,
        construir_manual_maestro_imprimible,
        construir_manual_master,
        construir_manual_operador,
        construir_manual_picker,
        generar_todos_los_manuales,
    )

__all__ = [
    "VERSION_PROC_ACTUAL",
    "agregar_ficha_boton",
    "construir_manual_operador",
    "construir_manual_picker",
    "construir_manual_administrador",
    "construir_manual_master",
    "construir_manual_consulta",
    "construir_manual_general",
    "construir_manual_maestro_imprimible",
    "generar_todos_los_manuales",
]


if __name__ == "__main__":
    print("Compilando todos los manuales de procedimiento y uso botón por botón en PDF...")
    res = generar_todos_los_manuales()
    print("=== MANUALES GENERADOS EXITOSAMENTE ===")
    for k, v in res.items():
        print(f"[{k.upper():13}] -> {v.name:28} ({v.stat().st_size} bytes)")
