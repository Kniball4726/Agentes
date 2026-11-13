"""Panel de Control Interactivo CLI del Agente de Stock y Remitos."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .cli import ArchiveOpsMixin, InteractiveFlowsMixin
from .paths import application_root
from .remito_parser import normalizar_codigo

__all__ = ["MenuAgente", "normalizar_codigo"]

load_dotenv(application_root() / ".env")
_ADMIN_USUARIO = os.getenv("_ADMIN_USUARIO")
_ADMIN_CLAVE = os.getenv("_ADMIN_CLAVE")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class MenuAgente(ArchiveOpsMixin, InteractiveFlowsMixin):
    """Panel interactivo de consola compuesto por las capacidades de archivo y flujos."""

    def __init__(self) -> None:
        self.base_dir = application_root()
        self.ruta_excel_base = self.base_dir / "Descuentos" / "Productos.xlsx"
        self.carpeta_mayoristas = self.base_dir / "Descuentos" / "Mayoristas"
        self.carpeta_canjes = self.base_dir / "Descuentos" / "Canjes"
        self.carpeta_mercado_libre = self.base_dir / "Descuentos" / "MercadoLibre"
        self.carpeta_fabrica = self.base_dir / "Descuentos" / "Fabrica"
        self.carpeta_mercado_full = self.base_dir / "Descuentos" / "MercadoFull"
        self.carpeta_stock_fisico = self.base_dir / "Descuentos" / "StockFisico"
        self.carpeta_descuentos = self.base_dir / "Descuentos" / "descuentos"
        self.carpeta_descontados = self.base_dir / "Descuentos" / "descontados"

        for carpeta in (
            self.carpeta_mayoristas,
            self.carpeta_canjes,
            self.carpeta_mercado_libre,
            self.carpeta_fabrica,
            self.carpeta_mercado_full,
            self.carpeta_stock_fisico,
            self.carpeta_descuentos,
            self.carpeta_descontados,
        ):
            carpeta.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    MenuAgente().iniciar()
