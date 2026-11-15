"""Controlador de tema visual (modo oscuro / claro) mediante composición."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import flet as ft

from ..theme import BORDE, FONDO, SECUNDARIO, SUPERFICIE, TEXTO
from ..user_preferences import obtener_preferencias_usuario


@dataclass(frozen=True)
class ThemePalette:
    """Paleta de colores aplicada a la vista principal."""

    fondo: Any
    superficie: Any
    texto: Any
    secundario: Any
    borde: Any
    fondo_acento: Any


_PALETA_INTERACTIVA = {
    True: ThemePalette(
        fondo=ft.Colors.BLACK,
        superficie=ft.Colors.BLUE_GREY_900,
        texto=ft.Colors.WHITE,
        secundario=ft.Colors.BLUE_GREY_300,
        borde=ft.Colors.BLUE_GREY_700,
        fondo_acento=ft.Colors.RED_700,
    ),
    False: ThemePalette(
        fondo=ft.Colors.GREY_100,
        superficie=ft.Colors.WHITE,
        texto=ft.Colors.BLUE_GREY_900,
        secundario=ft.Colors.BLUE_GREY_600,
        borde=ft.Colors.GREY_300,
        fondo_acento=ft.Colors.RED_50,
    ),
}

_PALETA_PREFERENCIA = {
    True: ThemePalette(
        fondo=FONDO,
        superficie=SUPERFICIE,
        texto=TEXTO,
        secundario=SECUNDARIO,
        borde=BORDE,
        fondo_acento=ft.Colors.GREY_900,
    ),
    False: ThemePalette(
        fondo=ft.Colors.WHITE,
        superficie=ft.Colors.GREY_50,
        texto=ft.Colors.BLACK,
        secundario=ft.Colors.GREY_700,
        borde=ft.Colors.GREY_300,
        fondo_acento=ft.Colors.GREY_100,
    ),
}

POSICIONES_SIDEBAR_VALIDAS = ("izquierda", "derecha", "arriba", "abajo", "oculto")


class ThemeController:
    """Administra las paletas de color y sincroniza las preferencias visuales del usuario."""

    def __init__(
        self,
        host: Any,
        on_rebuild: Callable[[], None] | None = None,
        prefs_loader: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self._host = host
        self._on_rebuild = on_rebuild
        self._prefs_loader = prefs_loader or obtener_preferencias_usuario

    def aplicar_paleta(self, modo_oscuro: bool, usar_paleta_preferencia: bool = False) -> None:
        """Asigna la paleta correspondiente en los atributos visuales del host."""
        tabla = _PALETA_PREFERENCIA if usar_paleta_preferencia else _PALETA_INTERACTIVA
        paleta = tabla[bool(modo_oscuro)]
        self._host.modo_oscuro = bool(modo_oscuro)
        self._host.fondo = paleta.fondo
        self._host.superficie = paleta.superficie
        self._host.texto = paleta.texto
        self._host.secundario = paleta.secundario
        self._host.borde = paleta.borde
        self._host.fondo_acento = paleta.fondo_acento

    def alternar_tema(self, _evento: ft.Event | None = None) -> None:
        """Invierte el modo claro/oscuro actual y reconstruye la interfaz."""
        nuevo_oscuro = not bool(getattr(self._host, "modo_oscuro", True))
        self.aplicar_paleta(nuevo_oscuro, usar_paleta_preferencia=False)
        rebuild = self._on_rebuild or getattr(self._host, "construir", None)
        if callable(rebuild):
            rebuild()

    def aplicar_preferencias_usuario(self, usuario: Any) -> None:
        """Carga una única vez posición de sidebar y tema oscuro guardados para el usuario."""
        if getattr(self._host, "_prefs_cargadas_usuario", False) or not usuario:
            return
        try:
            prefs = self._prefs_loader(usuario.username)
            pos = prefs.get("posicion_sidebar")
            if pos in POSICIONES_SIDEBAR_VALIDAS:
                self._host.posicion_sidebar = pos
            if "modo_oscuro" in prefs:
                deseado_oscuro = bool(prefs["modo_oscuro"])
                if deseado_oscuro != bool(getattr(self._host, "modo_oscuro", True)):
                    self.aplicar_paleta(deseado_oscuro, usar_paleta_preferencia=True)
            self._host._prefs_cargadas_usuario = True
        except Exception:
            pass
