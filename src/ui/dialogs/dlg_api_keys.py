"""Fachada de compatibilidad para la gestión de Claves de API Externas (Exclusivo Master).

Unifica la gestión de claves API con el panel maestro de integraciones (`dlg_api.py`),
evitando duplicación de formularios, validaciones y flujos de revocación/auditoría.
"""

from __future__ import annotations

from typing import Any
import flet as ft

from .dlg_api import mostrar_dialogo_api_master


def mostrar_dialogo_api_keys(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre el diálogo unificado de API REST posicionado en la pestaña de Claves API (Keys)."""
    mostrar_dialogo_api_master(interfaz, tab_inicial=0)


__all__ = ["mostrar_dialogo_api_keys"]
