"""Lanzador directo del Ambiente de Pruebas y QA Manual (StockAgent QA)."""

import sys
from pathlib import Path

# Inyectar raíz del repositorio y argumento --qa
_ROOT_DIR = str(Path(__file__).resolve().parent.parent)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)
if "--qa" not in sys.argv:
    sys.argv.append("--qa")

from main import main

if __name__ == "__main__":
    main()
