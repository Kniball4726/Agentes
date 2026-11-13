"""Estilos y helpers visuales efecto espejo/cristal (Glassmorphism) para autenticación."""

from __future__ import annotations

from typing import Any

import flet as ft

from ..theme import ROJO


def _borde_espejo(modo_oscuro: bool) -> ft.Border:
    """Borde biselado con brillo especular superior-izquierdo tipo espejo/cristal."""
    brillo_alto = ft.Colors.with_opacity(0.38 if modo_oscuro else 0.85, ft.Colors.WHITE)
    brillo_bajo = ft.Colors.with_opacity(0.12 if modo_oscuro else 0.35, ft.Colors.WHITE)
    return ft.Border(
        top=ft.BorderSide(1.5, brillo_alto),
        left=ft.BorderSide(1.5, brillo_alto),
        right=ft.BorderSide(1, brillo_bajo),
        bottom=ft.BorderSide(1, brillo_bajo),
    )


def _sombra_espejo(modo_oscuro: bool) -> list[ft.BoxShadow]:
    """Sombra profunda multicapa con resplandor especular sutil."""
    return [
        ft.BoxShadow(
            spread_radius=1,
            blur_radius=38,
            color=ft.Colors.with_opacity(0.55 if modo_oscuro else 0.18, ft.Colors.BLACK),
            offset=ft.Offset(0, 16),
        ),
        ft.BoxShadow(
            spread_radius=0,
            blur_radius=24,
            color=ft.Colors.with_opacity(0.16 if modo_oscuro else 0.10, ROJO),
            offset=ft.Offset(0, 4),
        ),
    ]


def _gradiente_fondo_espejo(modo_oscuro: bool) -> ft.LinearGradient:
    """Fondo ambiental para potenciar el desenfoque y reflejo del cristal."""
    if modo_oscuro:
        return ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=["#080B11", "#151C28", "#241118", "#0B0F17"],
            stops=[0.0, 0.4, 0.75, 1.0],
        )
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=["#ECEFF4", "#F8FAFC", "#FCE8E8", "#E2E8F0"],
        stops=[0.0, 0.45, 0.78, 1.0],
    )


def _gradiente_tarjeta_espejo(modo_oscuro: bool) -> ft.LinearGradient:
    """Gradiente diagonal con franja de reflejo de luz sobre cristal."""
    if modo_oscuro:
        return ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[
                ft.Colors.with_opacity(0.84, "#1E293B"),
                ft.Colors.with_opacity(0.76, "#162032"),
                ft.Colors.with_opacity(0.88, "#283548"),
                ft.Colors.with_opacity(0.78, "#0F172A"),
            ],
            stops=[0.0, 0.38, 0.54, 1.0],
        )
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=[
            ft.Colors.with_opacity(0.88, ft.Colors.WHITE),
            ft.Colors.with_opacity(0.75, "#F8FAFC"),
            ft.Colors.with_opacity(0.94, ft.Colors.WHITE),
            ft.Colors.with_opacity(0.82, "#F1F5F9"),
        ],
        stops=[0.0, 0.4, 0.56, 1.0],
    )


def _estilizar_campo_espejo(campo: ft.TextField, modo_oscuro: bool) -> None:
    """Aplica acabado translúcido y borde brillante a un campo de texto."""
    campo.bgcolor = (
        ft.Colors.with_opacity(0.07, ft.Colors.WHITE)
        if modo_oscuro
        else ft.Colors.with_opacity(0.65, ft.Colors.WHITE)
    )
    campo.border_radius = 12
    campo.border_color = (
        ft.Colors.with_opacity(0.24, ft.Colors.WHITE)
        if modo_oscuro
        else ft.Colors.with_opacity(0.22, ft.Colors.BLUE_GREY_400)
    )
    campo.focused_border_color = ROJO


def limpiar_chrome_auth(interfaz: Any) -> None:
    """Limpia botones flotantes, drawers y overlays antes de mostrar una pantalla de acceso."""
    interfaz.chat_visible = False
    interfaz.page.floating_action_button = None
    if hasattr(interfaz.page, "drawer"):
        interfaz.page.drawer = None
    if hasattr(interfaz.page, "overlay") and interfaz.page.overlay is not None:
        interfaz.page.overlay.clear()
    interfaz.page.controls.clear()


def renderizar_en_fondo_espejo(interfaz: Any, content: ft.Control, es_movil: bool, modo_oscuro: bool) -> None:
    """Envuelve una vista de autenticación en el contenedor de fondo degradado y actualiza la página."""
    interfaz.page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=interfaz.fondo,
            gradient=_gradiente_fondo_espejo(modo_oscuro),
            padding=12 if es_movil else 24,
            content=content,
        )
    )
    interfaz.page.update()
