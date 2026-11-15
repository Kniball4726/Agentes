"""Panel de Control Interactivo CLI del Agente de Stock y Remitos."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from .cli import ArchiveOpsMixin, InteractiveFlowsMixin
from .paths import application_root, get_descuentos_dir
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
        dir_descuentos = get_descuentos_dir()
        self.ruta_excel_base = dir_descuentos / "Productos.xlsx"
        self.carpeta_mayoristas = dir_descuentos / "Mayoristas"
        self.carpeta_canjes = dir_descuentos / "Canjes"
        self.carpeta_mercado_libre = dir_descuentos / "MercadoLibre"
        self.carpeta_fabrica = dir_descuentos / "Fabrica"
        self.carpeta_mercado_full = dir_descuentos / "MercadoFull"
        self.carpeta_stock_fisico = dir_descuentos / "StockFisico"
        self.carpeta_descuentos = dir_descuentos / "descuentos"
        self.carpeta_descontados = dir_descuentos / "descontados"

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
