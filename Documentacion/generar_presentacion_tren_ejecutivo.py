# -*- coding: utf-8 -*-
"""Generador CLI de la Presentación al Tren Ejecutivo de StockAgent (PDF 16:9)."""

from __future__ import annotations

import sys
from pathlib import Path

_doc_dir = Path(__file__).resolve().parent
_root_dir = _doc_dir.parent
for _p in (str(_root_dir), str(_doc_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from .pdf_engine.presentacion_tren_ejecutivo import construir_presentacion_tren_ejecutivo
except ImportError:
    from pdf_engine.presentacion_tren_ejecutivo import construir_presentacion_tren_ejecutivo


def generar_presentacion_tren_ejecutivo(ruta_destino: Path | str | None = None) -> Path:
    """Genera ``Documentacion/Presentacion_Tren_Ejecutivo_StockAgent.pdf`` o en ruta indicada."""
    destino = (
        Path(ruta_destino)
        if ruta_destino
        else (_doc_dir / "Presentacion_Tren_Ejecutivo_StockAgent.pdf")
    )
    return construir_presentacion_tren_ejecutivo(destino)


if __name__ == "__main__":
    salida = generar_presentacion_tren_ejecutivo()
    print(f"[TREN EJECUTIVO] -> {salida} ({salida.stat().st_size} bytes)")
