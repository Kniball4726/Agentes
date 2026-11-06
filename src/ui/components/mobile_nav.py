"""Componente de navegación móvil optimizado para la 'Zona del Pulgar' (Thumb Zone)."""

from __future__ import annotations
from typing import Any
import flet as ft


def construir_navigation_bar_movil(interfaz: Any) -> ft.NavigationBar:
    """Crea la barra inferior anclada para operación con una sola mano en depósitos."""
    modo_oscuro = getattr(interfaz, "modo_oscuro", True)
    superficie = getattr(interfaz, "superficie", ft.Colors.BLUE_GREY_900)

    def _al_cambiar(e: Any) -> None:
        manejar_cambio_navegacion_movil(interfaz, e)

    return ft.NavigationBar(
        bgcolor=superficie,
        indicator_color=ft.Colors.RED_900 if modo_oscuro else ft.Colors.RED_100,
        destinations=[
            getattr(ft, 'NavigationBarDestination', getattr(ft, 'NavigationDestination', None))(
                icon=ft.Icons.RECEIPT_LONG_OUTLINED,
                selected_icon=ft.Icons.RECEIPT_LONG,
                label="Pedidos",
            ),
            getattr(ft, 'NavigationBarDestination', getattr(ft, 'NavigationDestination', None))(
                icon=ft.Icons.QR_CODE_SCANNER,
                selected_icon=ft.Icons.QR_CODE_SCANNER,
                label="Escanear ML",
            ),
            getattr(ft, 'NavigationBarDestination', getattr(ft, 'NavigationDestination', None))(
                icon=ft.Icons.INVENTORY_2_OUTLINED,
                selected_icon=ft.Icons.INVENTORY_2,
                label="Fábrica",
            ),
            getattr(ft, 'NavigationBarDestination', getattr(ft, 'NavigationDestination', None))(
                icon=ft.Icons.TASK_ALT_OUTLINED,
                selected_icon=ft.Icons.TASK_ALT,
                label="Cierre",
            ),
            getattr(ft, 'NavigationBarDestination', getattr(ft, 'NavigationDestination', None))(
                icon=ft.Icons.SMART_TOY_OUTLINED,
                selected_icon=ft.Icons.SMART_TOY,
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
