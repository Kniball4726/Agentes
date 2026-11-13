# -*- coding: utf-8 -*-
"""Orquestador de generación masiva de todos los manuales oficiales PDF."""

from __future__ import annotations

from pathlib import Path

from Documentacion.pdf_engine.manuals_master import (
    construir_manual_maestro_imprimible as _construir_compendio_maestro,
)

from .rol_administrador import construir_manual_administrador
from .rol_consulta import construir_manual_consulta
from .rol_master import construir_manual_master
from .rol_operador import construir_manual_operador
from .rol_picker import construir_manual_picker


def construir_manual_general(ruta_destino: Path) -> Path:
    """Genera el manual general consolidado con los 5 roles y compendio ISO/BPMN."""
    return _construir_compendio_maestro(ruta_destino)


def construir_manual_maestro_imprimible(ruta_destino: Path) -> Path:
    """Genera el manual maestro imprimible consolidado."""
    return _construir_compendio_maestro(ruta_destino)


def generar_todos_los_manuales(directorio_destino: Path | str | None = None) -> dict[str, Path]:
    """Genera todos los manuales de procedimiento y uso botón por botón en formato PDF."""
    base_dir = Path(directorio_destino) if directorio_destino else Path("Documentacion")
    base_dir.mkdir(parents=True, exist_ok=True)

    rutas = {
        "operador": base_dir / "Manual_Operador.pdf",
        "picker": base_dir / "Manual_Picker.pdf",
        "administrador": base_dir / "Manual_Administrador.pdf",
        "master": base_dir / "Manual_Master.pdf",
        "consulta": base_dir / "Manual_Consulta.pdf",
        "general": base_dir / "Manual_General.pdf",
        "maestro": base_dir / "Manual_Maestro_Imprimible.pdf",
    }

    construir_manual_operador(rutas["operador"])
    construir_manual_picker(rutas["picker"])
    construir_manual_administrador(rutas["administrador"])
    construir_manual_master(rutas["master"])
    construir_manual_consulta(rutas["consulta"])
    construir_manual_general(rutas["general"])
    construir_manual_maestro_imprimible(rutas["maestro"])

    ruta_legacy = base_dir / "Manual_de_Uso_StockAgent.pdf"
    construir_manual_general(ruta_legacy)

    return rutas
