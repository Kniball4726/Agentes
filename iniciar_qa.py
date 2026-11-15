"""Lanzador directo del Ambiente de Pruebas y QA Manual (StockAgent QA)."""

import sys
from pathlib import Path

# Inyectar argumento --qa
if "--qa" not in sys.argv:
    sys.argv.append("--qa")

from main import main

if __name__ == "__main__":
    main()
