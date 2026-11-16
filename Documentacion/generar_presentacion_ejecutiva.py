# -*- coding: utf-8 -*-
"""Generador CLI de la Presentación Ejecutiva mejorada de StockAgent en PDF."""

from __future__ import annotations

import sys
from pathlib import Path

_doc_dir = Path(__file__).resolve().parent
_root_dir = _doc_dir.parent
for _p in (str(_root_dir), str(_doc_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from .pdf_engine.presentacion_ejecutiva import construir_presentacion_ejecutiva
except ImportError:
    from pdf_engine.presentacion_ejecutiva import construir_presentacion_ejecutiva


def generar_presentacion_ejecutiva(ruta_destino: Path | str | None = None) -> Path:
    """Genera ``Documentacion/Presentacion_Ejecutiva_StockAgent.pdf`` o en ruta indicada."""
    destino = Path(ruta_destino) if ruta_destino else (_doc_dir / "Presentacion_Ejecutiva_StockAgent.pdf")
    return construir_presentacion_ejecutiva(destino)


if __name__ == "__main__":
    salida = generar_presentacion_ejecutiva()
    print(f"[PRESENTACION] -> {salida} ({salida.stat().st_size} bytes)")
