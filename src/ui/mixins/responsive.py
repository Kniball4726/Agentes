"""Mixin para diseño responsivo y adaptación móvil en Flet."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import flet as ft

logger = logging.getLogger(__name__)


class ResponsiveLayoutMixin:
    """Provee utilidades de detección y adaptación para pantallas móviles y redimensionamiento."""

    page: ft.Page
    usuario_actual: Any
    superficie: str

    @property
    def es_pantalla_movil(self) -> bool:
        """Determina si la pantalla actual corresponde a un dispositivo o viewport móvil."""
        ua = str(getattr(self.page, "client_user_agent", "") or "").lower()
        if any(tok in ua for tok in ("android", "iphone", "ipad", "ipod", "mobile", "; wv")):
            return True
        plat = str(getattr(self.page, "platform", "") or "").lower()
        if any(tok in plat for tok in ("android", "ios")):
            return True
        w = getattr(self.page, "width", None)
        if isinstance(w, (int, float)) and w > 0:
            return bool(w < 768)
        return False

    def ancho_adaptable(self, deseado: int, margen: int = 24) -> int:
        """Calcula el ancho óptimo respetando el viewport móvil si está disponible."""
        w = getattr(self.page, "width", None)
        if self.es_pantalla_movil:
            if isinstance(w, (int, float)) and 0 < w < 768:
                return min(deseado, max(260, int(w - margen)))
            return min(deseado, max(260, 360 - margen))
        if isinstance(w, (int, float)) and w > 0:
            return min(deseado, max(280, int(w - margen)))
        return deseado

    def alto_adaptable(self, deseado: int, margen: int = 60) -> int:
        """Calcula el alto óptimo respetando el viewport móvil si está disponible."""
        h = getattr(self.page, "height", None)
        if self.es_pantalla_movil:
            if isinstance(h, (int, float)) and 0 < h < 1024:
                return min(deseado, max(300, int(h - margen)))
            return min(deseado, 560)
        if isinstance(h, (int, float)) and h > 0:
            return min(deseado, max(300, int(h - margen)))
        return deseado

    def cerrar_drawer_si_movil(self) -> None:
        """Cierra el NavigationDrawer en pantallas móviles al abrir modales o navegar."""
        if self.es_pantalla_movil and hasattr(self.page, "close_drawer"):
            try:
                res = self.page.close_drawer()
                if asyncio.iscoroutine(res):
                    async def _cerrar_seguro(coro: Any) -> None:
                        try:
                            await coro
                        except Exception:
                            pass

                    asyncio.create_task(_cerrar_seguro(res))
            except Exception:
                pass

    def _asegurar_drawer_movil(self) -> None:
        """Garantiza que el NavigationDrawer esté inicializado cuando se solicita en móvil."""
        if hasattr(self.page, "drawer") and getattr(self.page, "drawer", None) is None and self.usuario_actual is not None:
            self.page.drawer = ft.NavigationDrawer(
                bgcolor=self.superficie,
                controls=[
                    ft.Container(
                        padding=16,
                        content=ft.Column(
                            self._sidebar_controls(),
                            spacing=8,
                            tight=True,
                        ),
                    )
                ],
            )
            try:
                self.page.update()
            except Exception:
                pass

    def _mostrar_menu_movil_fallback(self) -> None:
        """Muestra el menú lateral en un diálogo modal si el NavigationDrawer falla por timeout."""
        if self.usuario_actual is None:
            return
        dlg_menu = ft.AlertDialog(
            modal=False,
            bgcolor=self.superficie,
            content=ft.Container(
                width=self.ancho_adaptable(300),
                content=ft.Column(
                    self._sidebar_controls(),
                    spacing=8,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
            actions=[
                ft.TextButton("Cerrar menú", on_click=lambda _e: self.page.pop_dialog()),
            ],
        )
        try:
            self.page.show_dialog(dlg_menu)
        except Exception:
            pass

    async def _abrir_drawer_click(self, _e: ft.Event | None = None) -> None:
        """Abre el panel de navegación drawer en dispositivos móviles."""
        self._asegurar_drawer_movil()
        if hasattr(self.page, "show_drawer"):
            try:
                res = self.page.show_drawer()
                if asyncio.iscoroutine(res):
                    await res
                return
            except Exception as exc:
                logger.warning("Fallo al abrir NavigationDrawer con show_drawer (%s), usando menú alternativo.", exc)
        if hasattr(self.page, "drawer") and self.page.drawer is not None:
            if hasattr(self.page.drawer, "open"):
                try:
                    self.page.drawer.open = True
                    self.page.update()
                    return
                except Exception:
                    pass
        self._mostrar_menu_movil_fallback()

    def _al_redimensionar(self, _evento: ft.Event | None = None) -> None:
        """Manejador de redimensionamiento de pantalla para alternar layouts desktop/mobile."""
        es_movil = self.es_pantalla_movil
        modo_previo = getattr(self, "_modo_movil_previo", None)
        w_actual = getattr(self.page, "width", None)
        ancho_previo = getattr(self, "_ancho_previo", None)
        cambio_ancho_auth = (
            self.usuario_actual is None
            and isinstance(w_actual, (int, float))
            and w_actual > 0
            and (ancho_previo is None or abs(float(w_actual) - float(ancho_previo)) >= 16)
        )
        if modo_previo is None or modo_previo != es_movil or cambio_ancho_auth:
            self._modo_movil_previo = es_movil
            if isinstance(w_actual, (int, float)) and w_actual > 0:
                self._ancho_previo = float(w_actual)
            if self.usuario_actual is not None:
                self.construir()
            else:
                if not self.user_store.has_users:
                    self.mostrar_configuracion_inicial()
                else:
                    self.mostrar_inicio_sesion()
        else:
            if isinstance(w_actual, (int, float)) and w_actual > 0:
                self._ancho_previo = float(w_actual)
            if getattr(self, "ventana_chat_flotante", None) is not None and getattr(self.ventana_chat_flotante, "visible", False):
                if es_movil:
                    self.ventana_chat_flotante.width = None
                    self.ventana_chat_flotante.left = 8
                    self.ventana_chat_flotante.right = 8
                else:
                    self.ventana_chat_flotante.width = 420
                    self.ventana_chat_flotante.left = None
                    self.ventana_chat_flotante.right = 24
                self.page.update()
