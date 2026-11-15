"""Mixin para sincronización en tiempo real entre sesiones y chat de equipo."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

from ..theme import ROJO

logger = logging.getLogger(__name__)


class SessionSyncMixin:
    """Provee métodos para sincronización reactiva de estado y chat de equipo."""

    page: ft.Page
    usuario_actual: Any
    order_store: Any
    user_store: Any
    modo_oscuro: bool
    modo_chat_activo: str
    secundario: str
    borde: str
    texto: str
    badge_chat_container: Any
    texto_badge_chat: Any
    texto_badge_tab: Any
    selector_destinatario_equipo: Any
    conversacion_equipo: Any
    entrada_chat_equipo: Any

    def sincronizar_sesiones(
        self,
        notificar_chat: tuple[str, str, str] | None = None,
        aviso_colaborativo: str | None = None,
    ) -> None:
        """Actualiza en tiempo real otras sesiones abiertas en el navegador y el chat de equipo."""
        try:
            from ...flet_gui import SESIONES_ACTIVAS
            sesiones = list(SESIONES_ACTIVAS)
        except ImportError:
            return

        for sesion in sesiones:
            if sesion is self or getattr(sesion, "usuario_actual", None) is None:
                continue
            try:
                if aviso_colaborativo and any(w in aviso_colaborativo.lower() for w in ("entorno", "ambiente", "qa", "producción")):
                    if hasattr(sesion, "recargar_ambiente"):
                        sesion.recargar_ambiente()
                else:
                    sesion.actualizar_estado()
                sesion.actualizar_badge_chat()
                if getattr(sesion, "modo_chat_activo", "") == "equipo":
                    sesion.cargar_mensajes_equipo()
                if aviso_colaborativo:
                    try:
                        snack_colab = ft.SnackBar(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.SYNC_ALT, color=ft.Colors.WHITE, size=16),
                                    ft.Text(aviso_colaborativo, color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_500),
                                ],
                                spacing=8,
                            ),
                            bgcolor=ft.Colors.BLUE_GREY_900 if sesion.modo_oscuro else ft.Colors.BLUE_GREY_800,
                            duration=3500,
                        )
                        sesion.page.show_dialog(snack_colab)
                        sesion.reproducir_sonido("notificacion")
                        sesion.page.update()
                    except Exception:
                        pass
                if notificar_chat is not None:
                    emisor, dest, msg_corto = notificar_chat
                    usr_dest = sesion.usuario_actual.username
                    if dest == "Todos" or dest.lower() == usr_dest.lower():
                        aviso = f"💬 Nuevo mensaje de @{emisor}: {msg_corto[:65]}"
                        snack = ft.SnackBar(
                            content=ft.Text(aviso, color=ft.Colors.WHITE, size=12),
                            bgcolor=ROJO,
                            duration=4000,
                        )
                        sesion.page.show_dialog(snack)
                        sesion.page.update()
            except Exception:
                pass

    def actualizar_badge_chat(self) -> None:
        if not getattr(self, "usuario_actual", None):
            return
        try:
            no_leidos = self.order_store.contar_mensajes_no_leidos(self.usuario_actual.username)
            if hasattr(self, "badge_chat_container") and hasattr(self, "texto_badge_chat"):
                if no_leidos > 0:
                    self.texto_badge_chat.value = str(no_leidos)
                    self.badge_chat_container.visible = True
                else:
                    self.badge_chat_container.visible = False
            if hasattr(self, "texto_badge_tab"):
                self.texto_badge_tab.value = f" ({no_leidos})" if no_leidos > 0 else ""
            self.page.update()
        except Exception:
            pass

    def refrescar_usuarios_chat_equipo(self) -> None:
        opciones = [ft.dropdown.Option("Todos", "📢 Todos (Canal General)")]
        try:
            usuarios = self.user_store.list_users(include_master=True)
            for u in usuarios:
                if self.usuario_actual and u.username != self.usuario_actual.username and u.active:
                    etiqueta = (
                        f"👤 {u.nombre} (@{u.username}) ({u.role.capitalize()})"
                        if u.nombre and u.nombre.strip()
                        else f"👤 @{u.username} ({u.role.capitalize()})"
                    )
                    opciones.append(ft.dropdown.Option(u.username, etiqueta))
        except Exception:
            pass
        self.selector_destinatario_equipo.options = opciones
        if not self.selector_destinatario_equipo.value:
            self.selector_destinatario_equipo.value = "Todos"

    def cargar_mensajes_equipo(self) -> None:
        if not getattr(self, "usuario_actual", None):
            return
        mensajes = self.order_store.listar_mensajes_chat(usuario=self.usuario_actual.username, limite=60)
        self.conversacion_equipo.controls.clear()

        if not mensajes:
            self.conversacion_equipo.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.FORUM_OUTLINED, size=36, color=self.secundario),
                            ft.Text(
                                "No hay mensajes en el canal de equipo.\nEscribe para comunicarte con tus compañeros.",
                                size=12,
                                color=self.secundario,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=25,
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for m in mensajes:
                es_mio = m.emisor == self.usuario_actual.username
                bg_burbuja = (
                    ft.Colors.RED_900 if self.modo_oscuro else ft.Colors.RED_50
                ) if es_mio else (
                    ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.GREY_100
                )
                borde_burbuja = ft.Border.all(
                    1,
                    ft.Colors.RED_300 if es_mio else self.borde,
                )

                if m.destinatario == "Todos":
                    tag_dest = "📢 Para: Todos"
                    color_tag = ft.Colors.BLUE_400 if self.modo_oscuro else ft.Colors.BLUE_700
                else:
                    tag_dest = f"🔒 {'Para ti' if not es_mio else f'Para @{m.destinatario}'}"
                    color_tag = ft.Colors.AMBER_400 if self.modo_oscuro else ft.Colors.AMBER_800

                titulo_emisor = "Tú" if es_mio else f"@{m.emisor}"
                color_emisor = ROJO if es_mio else (ft.Colors.BLUE_300 if self.modo_oscuro else ft.Colors.BLUE_GREY_900)

                burbuja = ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(titulo_emisor, size=11, weight=ft.FontWeight.BOLD, color=color_emisor),
                                    ft.Text(tag_dest, size=9, weight=ft.FontWeight.W_500, color=color_tag),
                                    ft.Text(m.created_at[11:16], size=9, color=self.secundario),
                                ],
                                spacing=8,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(m.mensaje, size=12, color=self.texto, selectable=True),
                        ],
                        spacing=3,
                        tight=True,
                    ),
                    bgcolor=bg_burbuja,
                    border=borde_burbuja,
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                    margin=ft.Margin.only(
                        left=35 if es_mio else 0,
                        right=0 if es_mio else 35,
                    ),
                )
                self.conversacion_equipo.controls.append(burbuja)

        try:
            self.page.update()
        except Exception:
            pass

    def enviar_mensaje_equipo(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles("operador", "picker", "administrador", "master", "consulta"):
            return
        texto = (self.entrada_chat_equipo.value or "").strip()
        if not texto:
            return
        self.entrada_chat_equipo.value = ""
        emisor = self.usuario_actual.username if self.usuario_actual else "Operador"
        destinatario = self.selector_destinatario_equipo.value or "Todos"
        texto_enriquecido = self._enriquecer_mensaje_con_pedidos(texto)

        self.order_store.enviar_mensaje_chat(
            emisor=emisor,
            mensaje=texto_enriquecido,
            destinatario=destinatario,
        )
        self.cargar_mensajes_equipo()
        self.sincronizar_sesiones(notificar_chat=(emisor, destinatario, texto))
