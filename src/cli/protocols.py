"""Contratos estructurales (Protocols) para composición de servicios CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ArchiveOpsHostProtocol(Protocol):
    """Contrato mínimo de carpetas para operaciones de bandeja e historial CLI."""

    base_dir: Path
    carpeta_mayoristas: Path
    carpeta_canjes: Path
    carpeta_mercado_libre: Path
    carpeta_fabrica: Path
    carpeta_mercado_full: Path
    carpeta_stock_fisico: Path
    carpeta_descuentos: Path
    carpeta_descontados: Path


@runtime_checkable
class InteractiveFlowsHostProtocol(ArchiveOpsHostProtocol, Protocol):
    """Contrato mínimo que los flujos interactivos CLI requieren del host."""

    ruta_excel_base: Path

    def _obtener_pendientes(self) -> tuple[list[Path], list[Path], list[Path]]: ...
    def _obtener_pendientes_fabrica(self) -> list[Path]: ...
    def _obtener_pendientes_mercado_full(self) -> list[Path]: ...
    def _obtener_pendientes_stock_fisico(self) -> list[Path]: ...
    def _obtener_archivados(self) -> tuple[list[Path], list[Path], list[Path]]: ...
    def _obtener_generados(self) -> list[Path]: ...
    def ver_historial(self) -> None: ...
    def restaurar_para_pruebas(self, fecha_descuento: str | None = None) -> int: ...
