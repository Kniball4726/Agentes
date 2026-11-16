"""Componente de navegación móvil optimizado para la 'Zona del Pulgar' (Thumb Zone)."""

from __future__ import annotations
from typing import Any
import flet as ft


def _crear_punto_chat_movil() -> ft.Container:
    return ft.Container(
        width=9,
        height=9,
        border_radius=4.5,
        bgcolor=ft.Colors.RED_500,
        border=ft.Border.all(1.5, ft.Colors.WHITE),
        right=-3,
        top=-3,
        visible=False,
    )


def construir_navigation_bar_movil(interfaz: Any) -> ft.NavigationBar:
    """Crea la barra inferior anclada para operación con una sola mano en depósitos."""
    modo_oscuro = getattr(interfaz, "modo_oscuro", True)
    superficie = getattr(interfaz, "superficie", ft.Colors.BLUE_GREY_900)
    interfaz.punto_nuevo_chat_movil = _crear_punto_chat_movil()
    interfaz.punto_nuevo_chat_movil_sel = _crear_punto_chat_movil()

    def _al_cambiar(e: Any) -> None:
        manejar_cambio_navegacion_movil(interfaz, e)

    dest_cls = getattr(ft, "NavigationBarDestination", getattr(ft, "NavigationDestination", None))

    return ft.NavigationBar(
        bgcolor=superficie,
        indicator_color=ft.Colors.RED_900 if modo_oscuro else ft.Colors.RED_100,
        destinations=[
            dest_cls(
                icon=ft.Icons.RECEIPT_LONG_OUTLINED,
                selected_icon=ft.Icons.RECEIPT_LONG,
                label="Pedidos",
            ),
            dest_cls(
                icon=ft.Icons.QR_CODE_SCANNER,
                selected_icon=ft.Icons.QR_CODE_SCANNER,
                label="Escanear ML",
            ),
            dest_cls(
                icon=ft.Icons.INVENTORY_2_OUTLINED,
                selected_icon=ft.Icons.INVENTORY_2,
                label="Fábrica",
            ),
            dest_cls(
                icon=ft.Icons.TASK_ALT_OUTLINED,
                selected_icon=ft.Icons.TASK_ALT,
                label="Cierre",
            ),
            dest_cls(
                icon=ft.Stack(
                    [
                        ft.Icon(ft.Icons.SMART_TOY_OUTLINED),
                        interfaz.punto_nuevo_chat_movil,
                    ],
                    width=26,
                    height=24,
                    clip_behavior=ft.ClipBehavior.NONE,
                ),
                selected_icon=ft.Stack(
                    [
                        ft.Icon(ft.Icons.SMART_TOY),
                        interfaz.punto_nuevo_chat_movil_sel,
                    ],
                    width=26,
                    height=24,
                    clip_behavior=ft.ClipBehavior.NONE,
                ),
                label="Chat",
            ),
        ],
        on_change=_al_cambiar,
    )


def manejar_cambio_navegacion_movil(interfaz: Any, e: Any) -> None:
    """Enruta la acción seleccionada en la barra Thumb Zone inferior."""
    ctrl = getattr(e, "control", None)
    idx = getattr(ctrl, "selected_index", None)
    if idx == 0:
        interfaz.mostrar_historial_pedidos()
    elif idx == 1:
        interfaz.mostrar_descuento_mercado_libre()
    elif idx == 2:
        interfaz.mostrar_ingreso_fabrica()
    elif idx == 3:
        interfaz.mostrar_cierre_jornada()
    elif idx == 4:
        interfaz.alternar_chat_flotante()
