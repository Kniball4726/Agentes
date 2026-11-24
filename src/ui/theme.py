"""Constantes y configuración de estilos visuales para la interfaz Flet."""
from typing import Any

import flet as ft

# Tipografía principal con soporte completo UTF-8 (tildes y eñes)
FUENTE_PRINCIPAL = "Roboto"

# Colores primarios de marca
ROJO = ft.Colors.RED_700
ACENTO_ROJO = ft.Colors.RED_700

# Tipografía dedicada para menús de navegación (cargada desde assets/fonts/)
FUENTE_MENU = "Inter"
FUENTE_MENU_MEDIUM = "InterMedium"
FUENTE_MENU_SEMIBOLD = "InterSemiBold"
FUENTE_MENU_BOLD = "InterBold"

FUENTES_APP: dict[str, str] = {
    FUENTE_MENU: "fonts/Inter-Regular.ttf",
    FUENTE_MENU_MEDIUM: "fonts/Inter-Medium.ttf",
    FUENTE_MENU_SEMIBOLD: "fonts/Inter-SemiBold.ttf",
    FUENTE_MENU_BOLD: "fonts/Inter-Bold.ttf",
}

_FAMILIAS_PESO_MENU: dict[str, str] = {
    "regular": FUENTE_MENU,
    "medium": FUENTE_MENU_MEDIUM,
    "semibold": FUENTE_MENU_SEMIBOLD,
    "bold": FUENTE_MENU_BOLD,
}


def fuente_menu(peso: str = "regular") -> str:
    """Devuelve el nombre de familia Inter correspondiente al peso solicitado."""
    return _FAMILIAS_PESO_MENU.get(peso.strip().lower(), FUENTE_MENU)


def estilo_texto_menu(
    peso: str = "regular",
    size: int | float | None = None,
    color: Any = None,
) -> ft.TextStyle:
    """Construye un TextStyle con la tipografía de menús (Inter)."""
    return ft.TextStyle(
        font_family=fuente_menu(peso),
        size=size,
        color=color,
    )


def estilo_boton_menu_sidebar(texto_color: Any, peso: str = "medium") -> ft.ButtonStyle:
    """Estilo compartido para los botones de ítems dentro del menú lateral."""
    return ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=6),
        overlay_color=ft.Colors.with_opacity(0.08, texto_color),
        alignment=ft.Alignment.CENTER_LEFT,
        padding=ft.Padding.only(left=16, right=8),
        text_style=estilo_texto_menu(peso),
    )


def crear_tema_menus(color_seed: Any = ROJO) -> ft.Theme:
    """Crea el tema base conservando la tipografía global y aplicando Inter a los menús nativos."""
    return ft.Theme(
        color_scheme_seed=color_seed,
        font_family=FUENTE_PRINCIPAL,
        popup_menu_theme=ft.PopupMenuTheme(
            label_text_style=estilo_texto_menu("regular"),
        ),
        navigation_bar_theme=ft.NavigationBarTheme(
            label_text_style=estilo_texto_menu("medium"),
        ),
        navigation_drawer_theme=ft.NavigationDrawerTheme(
            label_text_style=estilo_texto_menu("medium"),
        ),
    )


# Paleta Modo Claro
FONDO_CLARO = ft.Colors.GREY_100
SUPERFICIE_CLARO = ft.Colors.WHITE
TEXTO_CLARO = ft.Colors.BLUE_GREY_900
SECUNDARIO_CLARO = ft.Colors.BLUE_GREY_600
BORDE_CLARO = ft.Colors.BLUE_GREY_200

# Paleta Modo Oscuro
FONDO_OSCURO = ft.Colors.BLACK
SUPERFICIE_OSCURO = ft.Colors.BLUE_GREY_900
TEXTO_OSCURO = ft.Colors.WHITE
SECUNDARIO_OSCURO = ft.Colors.BLUE_GREY_300
BORDE_OSCURO = ft.Colors.BLUE_GREY_700

# Compatibilidad directa
FONDO = FONDO_CLARO
SUPERFICIE = SUPERFICIE_CLARO
TEXTO = TEXTO_CLARO
SECUNDARIO = SECUNDARIO_CLARO
BORDE = BORDE_CLARO
