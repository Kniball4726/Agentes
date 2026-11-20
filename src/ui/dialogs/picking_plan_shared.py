"""Componentes y utilidades compartidas para los diálogos de Planificación y Picking Guiado
(Mercado Envíos Full e Ingreso de Mercadería de Fábrica).
"""

from __future__ import annotations

import inspect
import sys
from typing import Any

import flet as ft

from ...inventory import StockManager as _DefaultStockManager
from ..audio_feedback import emitir_tono_error, emitir_tono_exito


def resolver_stock_manager_ui() -> type:
    """Obtiene la clase StockManager activa (respetando dobles de prueba inyectados en flet_gui)."""
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def safe_focus(interfaz: Any, ctrl: Any) -> None:
    """Solicita foco en un control Flet soportando tanto métodos síncronos como corrutinas (Flet 1.0.x)."""
    try:
        res = ctrl.focus()
        if inspect.iscoroutine(res):
            if (
                hasattr(interfaz, "page")
                and hasattr(interfaz.page, "run_task")
                and callable(interfaz.page.run_task)
                and not getattr(interfaz.page, "_is_mock", False)
                and not hasattr(interfaz.page, "mock_calls")
            ):
                async def _f() -> None:
                    await res

                interfaz.page.run_task(_f)
            else:
                res.close()
    except Exception:
        pass


def construir_banner_escaneo_inicial(mensaje: str, es_oscuro: bool) -> ft.Container:
    """Construye el banner informativo inicial para lectores de códigos de barras."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.INFO_OUTLINE, size=18, color=ft.Colors.BLUE_400),
                ft.Text(mensaje, size=12, expand=True),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )


def actualizar_banner_resultado_escaneo(
    banner: ft.Container,
    exito: bool,
    mensaje: str,
    es_oscuro: bool,
) -> None:
    """Actualiza el banner de feedback visual y emite la señal acústica correspondiente."""
    if exito:
        emitir_tono_exito()
        banner.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_400)
        banner.content = ft.Row(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE, size=18, color=ft.Colors.GREEN_400),
                ft.Text(
                    mensaje,
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_800,
                    expand=True,
                ),
            ],
            spacing=8,
        )
    else:
        emitir_tono_error()
        banner.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED_400)
        banner.content = ft.Row(
            [
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=18, color=ft.Colors.RED_400),
                ft.Text(
                    mensaje,
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.RED_400 if es_oscuro else ft.Colors.RED_800,
                    expand=True,
                ),
            ],
            spacing=8,
        )


def construir_fila_preview_plan(
    codigo: str,
    descripcion: str,
    cantidad: int,
    color_cantidad: Any,
    es_oscuro: bool,
) -> ft.Container:
    """Construye una fila de previsualización de artículo al cargar un plan Excel/PDF."""
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=6,
        bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
        content=ft.Row(
            [
                ft.Text(f"[{codigo}]", weight=ft.FontWeight.BOLD, size=11, width=90),
                ft.Text(descripcion, size=11, expand=True, no_wrap=True),
                ft.Text(
                    f"{cantidad} un.",
                    weight=ft.FontWeight.BOLD,
                    color=color_cantidad,
                    size=11,
                    width=60,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )


def construir_fila_monitor_plan(
    codigo: str,
    descripcion: str,
    txt_badge: str,
    completado: bool,
    en_progreso: bool,
    es_oscuro: bool,
) -> ft.Container:
    """Construye una fila de monitoreo de avance en tiempo real para el administrador."""
    color_badge = (
        ft.Colors.GREEN_400
        if completado
        else (ft.Colors.AMBER_400 if en_progreso else ft.Colors.GREY_400)
    )
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=6,
        bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.CHECK_CIRCLE if completado else ft.Icons.RADIO_BUTTON_UNCHECKED,
                    color=color_badge,
                    size=16,
                ),
                ft.Text(f"[{codigo}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                ft.Text(descripcion, size=11, expand=True, no_wrap=True),
                ft.Container(
                    content=ft.Text(
                        txt_badge,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    bgcolor=color_badge,
                    border_radius=4,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )


def construir_fila_picking_guiado(
    codigo: str,
    descripcion: str,
    cant_txt: str,
    completado: bool,
    en_progreso: bool,
    color_texto_base: Any,
    es_oscuro: bool,
    ancho_cant: int | None = None,
) -> ft.Container:
    """Construye una fila de artículo en las ventanas de picking/control guiado por escáner."""
    color_item = (
        ft.Colors.GREEN_400
        if completado
        else (ft.Colors.AMBER_400 if en_progreso else color_texto_base)
    )
    icono = (
        ft.Icons.CHECK_CIRCLE
        if completado
        else (ft.Icons.PENDING_ACTIONS if en_progreso else ft.Icons.RADIO_BUTTON_UNCHECKED)
    )
    icono_color = (
        ft.Colors.GREEN_400
        if completado
        else (ft.Colors.AMBER_400 if en_progreso else ft.Colors.GREY_400)
    )
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=6,
        bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
        content=ft.Row(
            [
                ft.Icon(icono, color=icono_color, size=18),
                ft.Text(f"[{codigo}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                ft.Text(descripcion, size=11, expand=True, no_wrap=True),
                ft.Text(
                    cant_txt,
                    weight=ft.FontWeight.BOLD,
                    size=11,
                    color=color_item,
                    width=ancho_cant,
                    text_align=ft.TextAlign.RIGHT,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )
