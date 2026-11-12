"""Módulo para gestión de ventanas, ergonomía responsiva y soporte móvil de StockAgent."""

import asyncio
from typing import Any
import flet as ft

ANCHO_MAXIMO_MOVIL = 768


def es_pantalla_movil(page: ft.Page | Any) -> bool:
    """Determina si la pantalla actual corresponde a un viewport móvil o estrecho."""
    ancho = getattr(page, "width", None)
    if isinstance(ancho, (int, float)) and ancho > 0:
        return ancho <= ANCHO_MAXIMO_MOVIL
    return False


def ancho_adaptable(page: ft.Page | Any, deseado: int, margen: int = 24) -> int:
    """Calcula el ancho máximo aplicable para modales respetando los márgenes del dispositivo."""
    w = getattr(page, "width", None)
    if es_pantalla_movil(page):
        if isinstance(w, (int, float)) and w > 0:
            return max(280, int(w - margen))
        return min(deseado, 340)
    if isinstance(w, (int, float)) and w > 0:
        return min(deseado, max(320, int(w - margen)))
    return deseado


def alto_adaptable(page: ft.Page | Any, deseado: int, margen: int = 60) -> int:
    """Calcula el alto máximo seguro para modales evitando desbordes verticales."""
    h = getattr(page, "height", None)
    if es_pantalla_movil(page):
        if isinstance(h, (int, float)) and h > 0:
            return max(260, int(h - margen))
        return min(deseado, 560)
    if isinstance(h, (int, float)) and h > 0:
        return min(deseado, max(300, int(h - margen)))
    return deseado


def cerrar_drawer_si_movil(page: ft.Page | Any) -> None:
    """Cierra el NavigationDrawer en pantallas móviles al abrir modales o navegar."""
    if es_pantalla_movil(page) and hasattr(page, "close_drawer"):
        try:
            res = page.close_drawer()
            if asyncio.iscoroutine(res):
                async def _cerrar_seguro(coro: Any) -> None:
                    try:
                        await coro
                    except Exception:
                        pass
                asyncio.create_task(_cerrar_seguro(res))
        except Exception:
            pass


def asegurar_drawer_movil(interfaz: Any) -> None:
    """Garantiza que el NavigationDrawer esté inicializado en dispositivos móviles."""
    page = getattr(interfaz, "page", None)
    if page is None:
        return
    if hasattr(page, "drawer") and getattr(page, "drawer", None) is None and getattr(interfaz, "usuario_actual", None) is not None:
        from .sidebar import construir_sidebar_controls
        page.drawer = ft.NavigationDrawer(
            bgcolor=interfaz.superficie,
            controls=[
                ft.Container(
                    padding=16,
                    content=ft.Column(
                        construir_sidebar_controls(interfaz),
                        spacing=8,
                        tight=True,
                    ),
                )
            ],
        )
        try:
            page.update()
        except Exception:
            pass


def mostrar_menu_movil_fallback(interfaz: Any) -> None:
    """Muestra el menú lateral en un diálogo modal si el NavigationDrawer falla por timeout."""
    if getattr(interfaz, "usuario_actual", None) is None or getattr(interfaz, "page", None) is None:
        return
    from .sidebar import construir_sidebar_controls
    dlg_menu = ft.AlertDialog(
        modal=False,
        bgcolor=interfaz.superficie,
        content=ft.Container(
            width=ancho_adaptable(interfaz.page, 300),
            content=ft.Column(
                construir_sidebar_controls(interfaz),
                spacing=8,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
        actions=[
            ft.TextButton("Cerrar menú", on_click=lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    try:
        interfaz.page.show_dialog(dlg_menu)
    except Exception:
        pass


def configurar_ventana_principal(interfaz: Any) -> None:
    """Configura las propiedades iniciales de tamaño y título de la ventana nativa desktop."""
    page = getattr(interfaz, "page", None)
    if not page or getattr(page, "web", False):
        return
    page.title = "StockAgent · Gestión Inteligente de Stock"
    try:
        page.window.min_width = 850
        page.window.min_height = 600
        page.window.width = 1180
        page.window.height = 760
    except Exception:
        pass
