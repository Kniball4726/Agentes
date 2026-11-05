"""Módulo de gestión del acoplamiento dinámico de la barra lateral (Multi-Docking Sidebar)."""

from __future__ import annotations
from typing import Any
import flet as ft


def aplicar_posicion_sidebar_ui(interfaz: Any, dashboard: ft.Control, sidebar: ft.Control) -> None:
    """Reorganiza los contenedores raíz del dashboard según la orientación de docking seleccionada."""
    pos = getattr(interfaz, "posicion_sidebar", "izquierda")
    if pos == "izquierda" or not interfaz.page.controls:
        return

    superficie = getattr(interfaz, "superficie", ft.Colors.BLUE_GREY_900)
    borde = getattr(interfaz, "borde", ft.Colors.BLUE_GREY_700)

    if pos == "oculto":
        interfaz.page.controls[-1] = ft.Container(
            expand=True,
            padding=22,
            content=dashboard,
        )
    elif pos == "derecha":
        interfaz.page.controls[-1] = ft.Row(
            [
                ft.Container(
                    expand=True,
                    padding=22,
                    content=dashboard,
                ),
                sidebar,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    elif pos == "arriba":
        barra_h = ft.Container(
            bgcolor=superficie,
            border=ft.Border(bottom=ft.BorderSide(1, borde)),
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            content=ft.Row(
                interfaz._sidebar_horizontal_controls(),
                scroll=ft.ScrollMode.AUTO,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        interfaz.page.controls[-1] = ft.Column(
            [
                barra_h,
                ft.Container(
                    expand=True,
                    padding=22,
                    content=dashboard,
                ),
            ],
            expand=True,
            spacing=0,
        )
    elif pos == "abajo":
        barra_h = ft.Container(
            bgcolor=superficie,
            border=ft.Border(top=ft.BorderSide(1, borde)),
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            content=ft.Row(
                interfaz._sidebar_horizontal_controls(),
                scroll=ft.ScrollMode.AUTO,
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        interfaz.page.controls[-1] = ft.Column(
            [
                ft.Container(
                    expand=True,
                    padding=22,
                    content=dashboard,
                ),
                barra_h,
            ],
            expand=True,
            spacing=0,
        )


def cambiar_posicion_sidebar_ui(interfaz: Any, e: Any) -> None:
    """Cambia la posición guardada de la barra lateral y reconstruye la interfaz de usuario."""
    nueva_pos = getattr(e, "control", None).data if getattr(e, "control", None) else None
    if nueva_pos and nueva_pos in ("izquierda", "derecha", "arriba", "abajo", "oculto"):
        interfaz.posicion_sidebar = nueva_pos
        interfaz.construir()
        try:
            nombres = {
                "izquierda": "Izquierda",
                "derecha": "Derecha",
                "arriba": "Arriba (Barra Superior)",
                "abajo": "Abajo (Barra Inferior)",
                "oculto": "Oculto (Modo Limpio / F2)",
            }
            snack = ft.SnackBar(
                content=ft.Text(f"Menú lateral fijado en: {nombres.get(nueva_pos, nueva_pos)}", size=12),
                duration=2500,
            )
            interfaz.page.show_dialog(snack)
            interfaz.page.update()
        except Exception:
            pass
