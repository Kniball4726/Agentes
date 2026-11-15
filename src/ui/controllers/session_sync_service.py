"""Servicio independiente de sincronización en tiempo real entre sesiones y chat de equipo."""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable, Iterable

import flet as ft

from ..theme import ROJO

logger = logging.getLogger(__name__)


def _sesiones_activas_por_defecto() -> Iterable[Any]:
    mod = sys.modules.get("src.flet_gui")
    if mod is not None and hasattr(mod, "SESIONES_ACTIVAS"):
        return list(mod.SESIONES_ACTIVAS)
    return []


class SessionSyncService:
    """Sincroniza el estado entre múltiples sesiones conectadas y gestiona el chat interno."""

    def __init__(
        self,
        host: Any,
        sessions_provider: Callable[[], Iterable[Any]] | None = None,
        check_roles_fn: Callable[..., bool] | None = None,
        enrich_message_fn: Callable[[str], str] | None = None,
    ) -> None:
        self._host = host
        self._sessions_provider = sessions_provider or _sesiones_activas_por_defecto
        self._check_roles_fn = check_roles_fn
        self._enrich_message_fn = enrich_message_fn

    def _exigir_roles(self, *roles: Any) -> bool:
        fn = self._check_roles_fn or getattr(self._host, "exigir_roles", None)
        return bool(fn(*roles)) if callable(fn) else True

    def _enriquecer_mensaje(self, texto: str) -> str:
        fn = self._enrich_message_fn or getattr(self._host, "_enriquecer_mensaje_con_pedidos", None)
        return fn(texto) if callable(fn) else texto

    def sincronizar_sesiones(
        self,
        notificar_chat: tuple[str, str, str] | None = None,
        aviso_colaborativo: str | None = None,
    ) -> None:
        """Actualiza en tiempo real otras sesiones abiertas y el chat de equipo."""
        try:
            sesiones = list(self._sessions_provider())
        except Exception:
            return

        for sesion in sesiones:
            if sesion is self._host or getattr(sesion, "usuario_actual", None) is None:
                continue
            try:
                if aviso_colaborativo and any(
                    w in aviso_colaborativo.lower() for w in ("entorno", "ambiente", "qa", "producción")
                ):
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
                                    ft.Text(
                                        aviso_colaborativo,
                                        color=ft.Colors.WHITE,
                                        size=12,
                                        weight=ft.FontWeight.W_500,
                                    ),
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
        usuario = getattr(self._host, "usuario_actual", None)
        if not usuario:
            return
        try:
            no_leidos = self._host.order_store.contar_mensajes_no_leidos(usuario.username)
            if hasattr(self._host, "badge_chat_container") and hasattr(self._host, "texto_badge_chat"):
                if no_leidos > 0:
                    self._host.texto_badge_chat.value = str(no_leidos)
                    self._host.badge_chat_container.visible = True
                else:
                    self._host.badge_chat_container.visible = False
            if hasattr(self._host, "texto_badge_tab"):
                self._host.texto_badge_tab.value = f" ({no_leidos})" if no_leidos > 0 else ""
            self._host.page.update()
        except Exception:
            pass

    def refrescar_usuarios_chat_equipo(self) -> None:
        opciones = [ft.dropdown.Option("Todos", "📢 Todos (Canal General)")]
        usuario_actual = getattr(self._host, "usuario_actual", None)
        try:
            usuarios = self._host.user_store.list_users(include_master=True)
            for u in usuarios:
                if usuario_actual and u.username != usuario_actual.username and u.active:
                    etiqueta = (
                        f"👤 {u.nombre} (@{u.username}) ({u.role.capitalize()})"
                        if u.nombre and u.nombre.strip()
                        else f"👤 @{u.username} ({u.role.capitalize()})"
                    )
                    opciones.append(ft.dropdown.Option(u.username, etiqueta))
        except Exception:
            pass
        self._host.selector_destinatario_equipo.options = opciones
        if not self._host.selector_destinatario_equipo.value:
            self._host.selector_destinatario_equipo.value = "Todos"

    def cargar_mensajes_equipo(self) -> None:
        usuario_actual = getattr(self._host, "usuario_actual", None)
        if not usuario_actual:
            return
        mensajes = self._host.order_store.listar_mensajes_chat(usuario=usuario_actual.username, limite=60)
        self._host.conversacion_equipo.controls.clear()

        if not mensajes:
            self._host.conversacion_equipo.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.FORUM_OUTLINED, size=36, color=self._host.secundario),
                            ft.Text(
                                "No hay mensajes en el canal de equipo.\nEscribe para comunicarte con tus compañeros.",
                                size=12,
                                color=self._host.secundario,
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
            modo_oscuro = bool(getattr(self._host, "modo_oscuro", True))
            for m in mensajes:
                es_mio = m.emisor == usuario_actual.username
                bg_burbuja = (
                    (ft.Colors.RED_900 if modo_oscuro else ft.Colors.RED_50)
                    if es_mio
                    else (ft.Colors.BLUE_GREY_800 if modo_oscuro else ft.Colors.GREY_100)
                )
                borde_burbuja = ft.Border.all(
                    1,
                    ft.Colors.RED_300 if es_mio else self._host.borde,
                )

                if m.destinatario == "Todos":
                    tag_dest = "📢 Para: Todos"
                    color_tag = ft.Colors.BLUE_400 if modo_oscuro else ft.Colors.BLUE_700
                else:
                    tag_dest = f"🔒 {'Para ti' if not es_mio else f'Para @{m.destinatario}'}"
                    color_tag = ft.Colors.AMBER_400 if modo_oscuro else ft.Colors.AMBER_800

                titulo_emisor = "Tú" if es_mio else f"@{m.emisor}"
                color_emisor = ROJO if es_mio else (
                    ft.Colors.BLUE_300 if modo_oscuro else ft.Colors.BLUE_GREY_900
                )

                burbuja = ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(titulo_emisor, size=11, weight=ft.FontWeight.BOLD, color=color_emisor),
                                    ft.Text(tag_dest, size=9, weight=ft.FontWeight.W_500, color=color_tag),
                                    ft.Text(m.created_at[11:16], size=9, color=self._host.secundario),
                                ],
                                spacing=8,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(m.mensaje, size=12, color=self._host.texto, selectable=True),
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
                self._host.conversacion_equipo.controls.append(burbuja)

        try:
            self._host.page.update()
        except Exception:
            pass

    def enviar_mensaje_equipo(self, _evento: ft.Event | None = None) -> None:
        if not self._exigir_roles("operador", "picker", "administrador", "master", "consulta"):
            return
        texto = (self._host.entrada_chat_equipo.value or "").strip()
        if not texto:
            return
        self._host.entrada_chat_equipo.value = ""
        usuario_actual = getattr(self._host, "usuario_actual", None)
        emisor = usuario_actual.username if usuario_actual else "Operador"
        destinatario = self._host.selector_destinatario_equipo.value or "Todos"
        texto_enriquecido = self._enriquecer_mensaje(texto)

        self._host.order_store.enviar_mensaje_chat(
            emisor=emisor,
            mensaje=texto_enriquecido,
            destinatario=destinatario,
        )
        self.cargar_mensajes_equipo()
        self.sincronizar_sesiones(notificar_chat=(emisor, destinatario, texto))
