"""Controlador de tema visual (modo oscuro / claro) mediante composición."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import flet as ft

from ..theme import (
    BORDE_CLARO,
    BORDE_OSCURO,
    FONDO_CLARO,
    FONDO_OSCURO,
    SECUNDARIO_CLARO,
    SECUNDARIO_OSCURO,
    SUPERFICIE_CLARO,
    SUPERFICIE_OSCURO,
    TEXTO_CLARO,
    TEXTO_OSCURO,
)
from ..user_preferences import guardar_preferencia_usuario, obtener_preferencias_usuario


@dataclass(frozen=True)
class ThemePalette:
    """Paleta de colores aplicada a la vista principal."""

    fondo: Any
    superficie: Any
    texto: Any
    secundario: Any
    borde: Any
    fondo_acento: Any


_PALETA_TEMA = {
    True: ThemePalette(
        fondo=FONDO_OSCURO,
        superficie=SUPERFICIE_OSCURO,
        texto=TEXTO_OSCURO,
        secundario=SECUNDARIO_OSCURO,
        borde=BORDE_OSCURO,
        fondo_acento=ft.Colors.BLUE_GREY_800,
    ),
    False: ThemePalette(
        fondo=FONDO_CLARO,
        superficie=SUPERFICIE_CLARO,
        texto=TEXTO_CLARO,
        secundario=SECUNDARIO_CLARO,
        borde=BORDE_CLARO,
        fondo_acento=ft.Colors.RED_50,
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
        prefs_saver: Callable[[str, str, Any], None] | None = None,
    ) -> None:
        self._host = host
        self._on_rebuild = on_rebuild
        self._prefs_loader = prefs_loader or obtener_preferencias_usuario
        self._prefs_saver = prefs_saver or guardar_preferencia_usuario

    def aplicar_paleta(self, modo_oscuro: bool, usar_paleta_preferencia: bool = False) -> None:
        """Asigna la paleta unificada claro/oscuro en los atributos visuales del host."""
        _ = usar_paleta_preferencia
        paleta = _PALETA_TEMA[bool(modo_oscuro)]
        self._host.modo_oscuro = bool(modo_oscuro)
        self._host.fondo = paleta.fondo
        self._host.superficie = paleta.superficie
        self._host.texto = paleta.texto
        self._host.secundario = paleta.secundario
        self._host.borde = paleta.borde
        self._host.fondo_acento = paleta.fondo_acento

    def alternar_tema(self, _evento: ft.Event | None = None) -> None:
        """Invierte el modo claro/oscuro actual, persiste la preferencia y reconstruye la interfaz."""
        nuevo_oscuro = not bool(getattr(self._host, "modo_oscuro", True))
        self.aplicar_paleta(nuevo_oscuro, usar_paleta_preferencia=False)
        usuario = getattr(self._host, "usuario_actual", None)
        username = getattr(usuario, "username", None)
        if isinstance(username, str) and username.strip():
            try:
                self._prefs_saver(username, "modo_oscuro", nuevo_oscuro)
            except Exception:
                pass
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
            if "sonido_chat_activo" in prefs:
                self._host.sonido_chat_activo = bool(prefs["sonido_chat_activo"])
            self._host._prefs_cargadas_usuario = True
        except Exception:
            pass
