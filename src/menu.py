"""Panel de Control Interactivo CLI del Agente de Stock y Remitos."""

from __future__ import annotations

import os
import sys

from pathlib import Path

from dotenv import load_dotenv

from .cli import ArchiveOpsService, InteractiveFlowsService
from .parsers.remito_parser import normalizar_codigo
from .paths import application_root, get_descuentos_dir

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


class MenuAgente:
    """Panel interactivo de consola basado en composición explícita de servicios CLI."""

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

        self._archive_ops = ArchiveOpsService(self)
        self._flows = InteractiveFlowsService(self)

    @property
    def archive_ops(self) -> ArchiveOpsService:
        servicio = getattr(self, "_archive_ops", None)
        if servicio is None:
            servicio = ArchiveOpsService(self)
            self._archive_ops = servicio
        return servicio

    @property
    def flows(self) -> InteractiveFlowsService:
        servicio = getattr(self, "_flows", None)
        if servicio is None:
            servicio = InteractiveFlowsService(self)
            self._flows = servicio
        return servicio

    def _obtener_pendientes(self) -> tuple[list[Path], list[Path], list[Path]]:
        return self.archive_ops.obtener_pendientes()

    def _obtener_pendientes_fabrica(self) -> list[Path]:
        return self.archive_ops.obtener_pendientes_fabrica()

    def _obtener_pendientes_mercado_full(self) -> list[Path]:
        return self.archive_ops.obtener_pendientes_mercado_full()

    def _obtener_pendientes_stock_fisico(self) -> list[Path]:
        return self.archive_ops.obtener_pendientes_stock_fisico()

    def _obtener_archivados(self) -> tuple[list[Path], list[Path], list[Path]]:
        return self.archive_ops.obtener_archivados()

    def _obtener_generados(self) -> list[Path]:
        return self.archive_ops.obtener_generados()

    @staticmethod
    def _leer_referencias_informe(ruta_informe: Path) -> list[tuple[str, str]]:
        return ArchiveOpsService.leer_referencias_informe(ruta_informe)

    @staticmethod
    def _normalizar_referencia(texto: str) -> str:
        return ArchiveOpsService.normalizar_referencia(texto)

    def _buscar_archivado(self, categoria: str, referencia: str, archivados: list[Path]) -> Path | None:
        return self.archive_ops.buscar_archivado(categoria, referencia, archivados)

    def _restauraciones_por_fecha(self) -> dict[str, list[tuple[Path, Path]]]:
        return self.archive_ops.restauraciones_por_fecha()

    def fechas_descuento_disponibles(self) -> list[str]:
        return self.archive_ops.fechas_descuento_disponibles()

    def ver_historial(self) -> None:
        self.archive_ops.ver_historial()

    def restaurar_para_pruebas(self, fecha_descuento: str | None = None) -> int:
        return self.archive_ops.restaurar_para_pruebas(fecha_descuento=fecha_descuento)

    def mostrar_banner(self) -> None:
        self.flows.mostrar_banner()

    def procesar(
        self,
        incluir_mayoristas: bool = True,
        incluir_canjes: bool = True,
        simulacion: bool = False,
        incluir_mercado_libre: bool = True,
        usuario: str = "sistema",
    ) -> None:
        self.flows.procesar(
            incluir_mayoristas=incluir_mayoristas,
            incluir_canjes=incluir_canjes,
            simulacion=simulacion,
            incluir_mercado_libre=incluir_mercado_libre,
            usuario=usuario,
        )

    def _autenticar(self) -> bool:
        return self.flows.autenticar()

    def agregar_producto_admin(self) -> None:
        self.flows.agregar_producto_admin()

    def cargar_pedido_fabrica(self) -> None:
        self.flows.cargar_pedido_fabrica()

    def _cargar_fabrica_archivos(self) -> None:
        self.flows.cargar_fabrica_archivos()

    def _cargar_fabrica_manual(self) -> None:
        self.flows.cargar_fabrica_manual()

    def generar_pedido_fabrica_cli(self) -> None:
        self.flows.generar_pedido_fabrica_cli()

    def descontar_mercado_full_cli(self) -> None:
        self.flows.descontar_mercado_full_cli()

    def hacer_stock_fisico_cli(self, usuario: str = "operario") -> None:
        self.flows.hacer_stock_fisico_cli(usuario=usuario)

    def iniciar(self) -> None:
        self.flows.iniciar()


if __name__ == "__main__":
    MenuAgente().iniciar()
