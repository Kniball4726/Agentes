"""Controlador independiente para diseño responsivo y adaptación móvil en Flet."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import flet as ft

logger = logging.getLogger(__name__)


class ResponsiveController:
    """Encapsula detección móvil, cálculo de dimensiones y manejo del NavigationDrawer."""

    def __init__(
        self,
        host: Any,
        get_sidebar_controls: Callable[[], list[ft.Control]] | None = None,
        on_rebuild: Callable[[], None] | None = None,
        on_show_login: Callable[[], None] | None = None,
        on_show_setup: Callable[[], None] | None = None,
    ) -> None:
        self._host = host
        self._get_sidebar_controls = get_sidebar_controls
        self._on_rebuild = on_rebuild
        self._on_show_login = on_show_login
        self._on_show_setup = on_show_setup

    def _sidebar_items(self) -> list[ft.Control]:
        fn = self._get_sidebar_controls or getattr(self._host, "_sidebar_controls", None)
        return fn() if callable(fn) else []

    @property
    def es_tablet(self) -> bool:
        """Determina si el viewport corresponde a una tablet (768–1199px o iPad)."""
        page = getattr(self._host, "page", None)
        ua = str(getattr(page, "client_user_agent", "") or "").lower()
        w = getattr(page, "width", None)
        if "ipad" in ua:
            return True
        if isinstance(w, (int, float)) and 768 <= w < 1200:
            if not any(tok in ua for tok in ("iphone", "ipod", "mobile", "; wv")):
                return True
        return False

    @property
    def es_pantalla_movil(self) -> bool:
        """Determina si la pantalla actual corresponde a un dispositivo o viewport móvil."""
        page = getattr(self._host, "page", None)
        ua = str(getattr(page, "client_user_agent", "") or "").lower()
        w = getattr(page, "width", None)
        if "ipad" in ua and isinstance(w, (int, float)) and w >= 768:
            return False
        if any(tok in ua for tok in ("android", "iphone", "ipad", "ipod", "mobile", "; wv")):
            return True
        plat = str(getattr(page, "platform", "") or "").lower()
        if any(tok in plat for tok in ("android", "ios")):
            return True
        if isinstance(w, (int, float)) and w > 0:
            return bool(w < 768)
        return False

    def ancho_adaptable(self, deseado: int, margen: int = 24) -> int:
        """Calcula el ancho óptimo respetando el viewport móvil/tablet si está disponible."""
        page = getattr(self._host, "page", None)
        w = getattr(page, "width", None)
        if self.es_pantalla_movil:
            if isinstance(w, (int, float)) and 0 < w < 768:
                return min(deseado, max(260, int(w - margen)))
            ua = str(getattr(page, "client_user_agent", "") or "").lower()
            if "ipad" in ua and isinstance(w, (int, float)) and w >= 768:
                return min(deseado, max(280, int(w - margen)))
            return min(deseado, max(260, 360 - margen))
        if isinstance(w, (int, float)) and w > 0:
            return min(deseado, max(280, int(w - margen)))
        return deseado

    def alto_adaptable(self, deseado: int, margen: int = 60) -> int:
        """Calcula el alto óptimo respetando el viewport móvil si está disponible."""
        page = getattr(self._host, "page", None)
        h = getattr(page, "height", None)
        if self.es_pantalla_movil:
            if isinstance(h, (int, float)) and 0 < h < 1024:
                return min(deseado, max(300, int(h - margen)))
            return min(deseado, 560)
        if isinstance(h, (int, float)) and h > 0:
            return min(deseado, max(300, int(h - margen)))
        return deseado

    def cerrar_drawer_si_movil(self) -> None:
        """Cierra el NavigationDrawer en pantallas móviles al abrir modales o navegar."""
        page = getattr(self._host, "page", None)
        if self.es_pantalla_movil and hasattr(page, "close_drawer"):
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

    def asegurar_drawer_movil(self) -> None:
        """Garantiza que el NavigationDrawer esté inicializado cuando se solicita en móvil."""
        page = getattr(self._host, "page", None)
        usuario = getattr(self._host, "usuario_actual", None)
        if hasattr(page, "drawer") and getattr(page, "drawer", None) is None and usuario is not None:
            page.drawer = ft.NavigationDrawer(
                bgcolor=getattr(self._host, "superficie", None),
                controls=[
                    ft.Container(
                        padding=16,
                        content=ft.Column(
                            self._sidebar_items(),
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

    def mostrar_menu_movil_fallback(self) -> None:
        """Muestra el menú lateral en un diálogo modal si el NavigationDrawer falla por timeout."""
        if getattr(self._host, "usuario_actual", None) is None:
            return
        page = self._host.page
        dlg_menu = ft.AlertDialog(
            modal=False,
            bgcolor=getattr(self._host, "superficie", None),
            content=ft.Container(
                width=self.ancho_adaptable(300),
                content=ft.Column(
                    self._sidebar_items(),
                    spacing=8,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.TextButton("Cerrar menú", on_click=lambda _e: page.pop_dialog()),
            ],
        )
        try:
            page.show_dialog(dlg_menu)
        except Exception:
            pass

    async def abrir_drawer_click(self, _e: ft.Event | None = None) -> None:
        """Abre el panel de navegación drawer en dispositivos móviles."""
        page = self._host.page
        self.asegurar_drawer_movil()
        if hasattr(page, "show_drawer"):
            try:
                res = page.show_drawer()
                if asyncio.iscoroutine(res):
                    await res
                return
            except Exception as exc:
                logger.warning("Fallo al abrir NavigationDrawer con show_drawer (%s), usando menú alternativo.", exc)
        if hasattr(page, "drawer") and page.drawer is not None and hasattr(page.drawer, "open"):
            try:
                page.drawer.open = True
                page.update()
                return
            except Exception:
                pass
        self.mostrar_menu_movil_fallback()

    def al_redimensionar(self, _evento: ft.Event | None = None) -> None:
        """Manejador de redimensionamiento de pantalla para alternar layouts desktop/mobile."""
        page = self._host.page
        usuario_actual = getattr(self._host, "usuario_actual", None)
        es_movil = self.es_pantalla_movil
        modo_previo = getattr(self._host, "_modo_movil_previo", None)
        w_actual = getattr(page, "width", None)
        ancho_previo = getattr(self._host, "_ancho_previo", None)
        cambio_ancho_auth = (
            usuario_actual is None
            and isinstance(w_actual, (int, float))
            and w_actual > 0
            and isinstance(ancho_previo, (int, float))
            and ((float(w_actual) < 768) != (float(ancho_previo) < 768))
        )
        if modo_previo is None or modo_previo != es_movil or cambio_ancho_auth:
            self._host._modo_movil_previo = es_movil
            if isinstance(w_actual, (int, float)) and w_actual > 0:
                self._host._ancho_previo = float(w_actual)
            if usuario_actual is not None:
                rebuild = self._on_rebuild or getattr(self._host, "construir", None)
                if callable(rebuild):
                    rebuild()
            elif not self._host.user_store.has_users:
                setup = self._on_show_setup or getattr(self._host, "mostrar_configuracion_inicial", None)
                if callable(setup):
                    setup()
            else:
                login = self._on_show_login or getattr(self._host, "mostrar_inicio_sesion", None)
                if callable(login):
                    login()
        else:
            if isinstance(w_actual, (int, float)) and w_actual > 0:
                self._host._ancho_previo = float(w_actual)
            ventana = getattr(self._host, "ventana_chat_flotante", None)
            if ventana is not None and getattr(ventana, "visible", False):
                if es_movil:
                    ventana.width = None
                    ventana.left = 8
                    ventana.right = 8
                else:
                    ventana.width = 420
                    ventana.left = None
                    ventana.right = 24
                page.update()
