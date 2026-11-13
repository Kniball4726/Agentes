"""Mixin para la ventana flotante de chat asistente y canal del equipo."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import flet as ft

from ...internal_chat import obtener_mensaje_bienvenida
from ...user_store import USER_ROLES
from ..components import crear_ventana_chat_flotante, procesar_mensaje_chat_agente
from ..theme import ROJO


class ChatPanelMixin:
    """Gestiona la visibilidad, tabs, formato de mensajes y comandos del chat flotante."""

    page: ft.Page
    usuario_actual: Any
    order_store: Any
    modo_oscuro: bool
    texto: str
    chat_visible: bool
    modo_chat_activo: str
    ventana_chat_flotante: ft.Container | None
    conversacion: ft.ListView
    entrada_chat: ft.TextField

    def _enriquecer_mensaje_con_pedidos(self, texto: str) -> str:
        """Si el mensaje menciona #remito o #nota, adjunta automáticamente el resumen del pedido."""
        referencias = re.findall(r"#([A-Za-z0-9_-]{2,40})", texto)
        if not referencias:
            return texto
        resumenes: list[str] = []
        vistos: set[str] = set()
        for ref in referencias:
            ref_norm = ref.upper()
            if ref_norm in vistos:
                continue
            vistos.add(ref_norm)
            res = self.order_store.obtener_pedido_resumen_chat(ref)
            if res:
                resumenes.append(res)
        if resumenes:
            return texto + "\n" + "\n".join(resumenes)
        return texto

    def alternar_chat_flotante(self, _evento: ft.Event | None = None) -> None:
        self.chat_visible = not self.chat_visible
        if self.ventana_chat_flotante is not None:
            self.ventana_chat_flotante.visible = self.chat_visible
            self.page.update()

    def cerrar_chat_flotante(self, _evento: ft.Event | None = None) -> None:
        self.chat_visible = False
        if self.ventana_chat_flotante is not None:
            self.ventana_chat_flotante.visible = False
            self.page.update()

    def limpiar_chat(self, _evento: ft.Event | None = None) -> None:
        self.conversacion.controls.clear()
        rol_actual = self.usuario_actual.role if self.usuario_actual else "operador"
        nom_actual = self.usuario_actual.username if self.usuario_actual else ""
        self.escribir_chat(
            "Agente",
            f"Conversación reiniciada.\n\n{obtener_mensaje_bienvenida(rol_actual, nom_actual)}",
        )
        self.page.update()

    def ejecutar_comando_rapido(self, comando: str) -> None:
        if comando == "/stock":
            self.entrada_chat.value = "/stock "
            self.entrada_chat.focus()
            self.page.update()
            return
        self.entrada_chat.value = comando
        asyncio.create_task(self.enviar_chat(None))

    def cambiar_pestaña_chat(self, modo: str) -> None:
        self.modo_chat_activo = modo
        if self.ventana_chat_flotante is not None:
            self.ventana_chat_flotante.visible = True
            self.chat_visible = True
        if hasattr(self, "_cambiar_tab_fn") and self._cambiar_tab_fn is not None:
            self._cambiar_tab_fn(modo)
        else:
            self.page.update()

    def crear_ventana_chat_flotante(self) -> ft.Container:
        return crear_ventana_chat_flotante(self)

    def panel_chat(self) -> ft.Control:
        if self.ventana_chat_flotante is None:
            self.crear_ventana_chat_flotante()
        return self.ventana_chat_flotante  # type: ignore[return-value]

    def escribir_chat(self, emisor: str, mensaje: str) -> None:
        color = ROJO if emisor == "Tú" else ft.Colors.RED_300
        if emisor == "Tú":
            bgcolor = ft.Colors.RED_900 if self.modo_oscuro else ft.Colors.RED_50
        else:
            bgcolor = ft.Colors.BLUE_GREY_800 if self.modo_oscuro else ft.Colors.GREY_100
        self.conversacion.controls.append(
            ft.Container(
                bgcolor=bgcolor,
                border_radius=10,
                padding=10,
                content=ft.Column(
                    [
                        ft.Text(emisor, size=10, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(mensaje, size=12, color=self.texto),
                    ],
                    spacing=3,
                ),
            )
        )

    async def enviar_chat(self, _evento: ft.Event | None = None) -> None:
        if not self.exigir_roles(*USER_ROLES):
            return
        mensaje = (self.entrada_chat.value or "").strip()
        if not mensaje:
            return
        self.entrada_chat.value = ""
        self.escribir_chat("Tú", mensaje)
        await procesar_mensaje_chat_agente(self, mensaje)
