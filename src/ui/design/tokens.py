"""Tokens semánticos de color con contraste WCAG 2.1 AA para modo claro y oscuro.

Centraliza la elección de tonos para que ningún componente use colores fijos
(``GREY_100``, ``#18181b``, ``AMBER_400`` sobre blanco, etc.) que se vuelvan
ilegibles al alternar de tema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import flet as ft

from ..theme import (
    BORDE_CLARO,
    BORDE_OSCURO,
    FONDO_CLARO,
    FONDO_OSCURO,
    ROJO,
    SECUNDARIO_CLARO,
    SECUNDARIO_OSCURO,
    SUPERFICIE_CLARO,
    SUPERFICIE_OSCURO,
    TEXTO_CLARO,
    TEXTO_OSCURO,
)

# Nivel de tono legible como texto/ícono sobre superficies claras (≥ 4.5:1 salvo
# familias cálidas, que se llevan al tono más oscuro disponible).
_NIVEL_CLARO_POR_FAMILIA: dict[str, int] = {
    "AMBER": 900,
    "YELLOW": 900,
    "ORANGE": 900,
    "DEEP_ORANGE": 800,
    "LIME": 900,
    "LIGHT_GREEN": 900,
    "GREEN": 800,
    "TEAL": 800,
    "CYAN": 800,
    "LIGHT_BLUE": 800,
}
_NIVEL_CLARO_DEFECTO = 700
# Sobre superficies oscuras los tonos 200/300 superan 4.5:1 con holgura.
_NIVEL_OSCURO_POR_FAMILIA: dict[str, int] = {"RED": 300, "BLUE_GREY": 300}
_NIVEL_OSCURO_DEFECTO = 300


def tono_legible(familia: str, modo_oscuro: bool) -> str:
    """Devuelve el tono de una familia Material legible sobre la superficie del tema.

    ``tono_legible("AMBER", False)`` → ``AMBER_900``; ``tono_legible("AMBER", True)`` → ``AMBER_300``.
    """
    fam = str(familia or "").strip().upper()
    if modo_oscuro:
        nivel = _NIVEL_OSCURO_POR_FAMILIA.get(fam, _NIVEL_OSCURO_DEFECTO)
    else:
        nivel = _NIVEL_CLARO_POR_FAMILIA.get(fam, _NIVEL_CLARO_DEFECTO)
    color = getattr(ft.Colors, f"{fam}_{nivel}", None)
    if color is None:
        return TEXTO_OSCURO if modo_oscuro else TEXTO_CLARO
    return color


def fondo_tenue(color: Any, opacidad: float = 0.14) -> str:
    """Fondo translúcido derivado de un color de acento (válido en ambos temas)."""
    return ft.Colors.with_opacity(max(0.0, min(1.0, float(opacidad))), color)


@dataclass(frozen=True)
class ColoresSemanticos:
    """Paleta semántica resuelta para el tema activo."""

    modo_oscuro: bool
    fondo: Any
    superficie: Any
    superficie_suave: Any
    texto: Any
    secundario: Any
    borde: Any
    marca: Any
    exito: Any
    error: Any
    advertencia: Any
    info: Any
    neutro: Any
    fondo_exito: Any
    fondo_error: Any
    fondo_advertencia: Any
    fondo_info: Any
    texto_sobre_color: Any
    etiqueta_emisor: Any


def colores_semanticos(modo_oscuro: bool) -> ColoresSemanticos:
    """Construye la paleta semántica para el modo indicado."""
    oscuro = bool(modo_oscuro)
    exito = tono_legible("GREEN", oscuro)
    error = tono_legible("RED", oscuro)
    advertencia = tono_legible("AMBER", oscuro)
    info = tono_legible("BLUE", oscuro)
    return ColoresSemanticos(
        modo_oscuro=oscuro,
        fondo=FONDO_OSCURO if oscuro else FONDO_CLARO,
        superficie=SUPERFICIE_OSCURO if oscuro else SUPERFICIE_CLARO,
        superficie_suave=(
            ft.Colors.with_opacity(0.06, ft.Colors.WHITE)
            if oscuro
            else ft.Colors.with_opacity(0.04, ft.Colors.BLACK)
        ),
        texto=TEXTO_OSCURO if oscuro else TEXTO_CLARO,
        secundario=SECUNDARIO_OSCURO if oscuro else SECUNDARIO_CLARO,
        borde=BORDE_OSCURO if oscuro else BORDE_CLARO,
        marca=ROJO,
        exito=exito,
        error=error,
        advertencia=advertencia,
        info=info,
        neutro=SECUNDARIO_OSCURO if oscuro else SECUNDARIO_CLARO,
        fondo_exito=fondo_tenue(ft.Colors.GREEN_500, 0.16 if oscuro else 0.10),
        fondo_error=fondo_tenue(ft.Colors.RED_500, 0.16 if oscuro else 0.10),
        fondo_advertencia=fondo_tenue(ft.Colors.AMBER_500, 0.16 if oscuro else 0.12),
        fondo_info=fondo_tenue(ft.Colors.BLUE_500, 0.16 if oscuro else 0.10),
        texto_sobre_color=ft.Colors.WHITE,
        # Etiqueta de emisor en burbujas de chat: legible sobre RED_900 (oscuro) y sobre blanco (claro).
        etiqueta_emisor=ft.Colors.RED_200 if oscuro else ft.Colors.RED_800,
    )


def colores_de(interfaz: Any) -> ColoresSemanticos:
    """Resuelve la paleta semántica a partir del ``modo_oscuro`` del host de UI."""
    modo = getattr(interfaz, "modo_oscuro", True)
    return colores_semanticos(modo if isinstance(modo, bool) else True)
