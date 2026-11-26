"""Controlador independiente para el chat asistente flotante y comandos rápidos."""

from __future__ import annotations

import asyncio
import re
from typing import Any, Callable

import flet as ft

from ...auth import USER_ROLES
from ...chat import obtener_mensaje_bienvenida
from ..components import crear_ventana_chat_flotante, procesar_mensaje_chat_agente


class ChatAssistantController:
    """Gestiona visibilidad, formato de burbujas, comandos rápidos y envío al agente."""

    def __init__(
        self,
        host: Any,
        check_roles_fn: Callable[..., bool] | None = None,
    ) -> None:
        self._host = host
        self._check_roles_fn = check_roles_fn

    def _exigir_roles(self, *roles: Any) -> bool:
        fn = self._check_roles_fn or getattr(self._host, "exigir_roles", None)
        return bool(fn(*roles)) if callable(fn) else True

    def enriquecer_mensaje_con_pedidos(self, texto: str) -> str:
        """Si el mensaje menciona #remito o #nota, adjunta el resumen del pedido."""
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
            res = self._host.order_store.obtener_pedido_resumen_chat(ref)
            if res:
                resumenes.append(res)
        if resumenes:
            return texto + "\n" + "\n".join(resumenes)
        return texto

    def alternar_chat_flotante(self, _evento: ft.Event | None = None) -> None:
        self._host.chat_visible = not bool(self._host.chat_visible)
        ventana = getattr(self._host, "ventana_chat_flotante", None)
        if ventana is not None:
            ventana.visible = self._host.chat_visible
        if self._host.chat_visible:
            modo = getattr(self._host, "modo_chat_activo", "bot")
            if modo == "equipo":
                refrescar = getattr(self._host, "refrescar_usuarios_chat_equipo", None)
                cargar = getattr(self._host, "cargar_mensajes_equipo", None)
                if callable(refrescar):
                    refrescar()
                if callable(cargar):
                    cargar()
            marcar = getattr(self._host, "marcar_mensajes_chat_leidos", None)
            if callable(marcar):
                marcar(solo_tab=modo)
                return
        self._host.page.update()

    def cerrar_chat_flotante(self, _evento: ft.Event | None = None) -> None:
        self._host.chat_visible = False
        ventana = getattr(self._host, "ventana_chat_flotante", None)
        if ventana is not None:
            ventana.visible = False
            self._host.page.update()

    def limpiar_chat(self, _evento: ft.Event | None = None) -> None:
        self._host.conversacion.controls.clear()
        self._host._mensajes_bot_no_leidos = 0
        usuario = getattr(self._host, "usuario_actual", None)
        rol_actual = usuario.role if usuario else "operador"
        nom_actual = usuario.username if usuario else ""
        self.escribir_chat(
            "Agente",
            f"Conversación reiniciada.\n\n{obtener_mensaje_bienvenida(rol_actual, nom_actual)}",
        )
        actualizar_badge = getattr(self._host, "actualizar_badge_chat", None)
        if callable(actualizar_badge):
            actualizar_badge()
        else:
            self._host.page.update()

    def ejecutar_comando_rapido(self, comando: str) -> None:
        if comando == "/stock":
            self._host.entrada_chat.value = "/stock "
            self._host.entrada_chat.focus()
            self._host.page.update()
            return
        self._host.entrada_chat.value = comando
        asyncio.create_task(self.enviar_chat(None))

    def cambiar_pestana_chat(self, modo: str) -> None:
        self._host.modo_chat_activo = modo
        ventana = getattr(self._host, "ventana_chat_flotante", None)
        if ventana is not None:
            ventana.visible = True
            self._host.chat_visible = True
        cambiar_fn = getattr(self._host, "_cambiar_tab_fn", None)
        if callable(cambiar_fn):
            cambiar_fn(modo)
        else:
            self._host.page.update()

    def crear_ventana_chat_flotante(self) -> ft.Container:
        return crear_ventana_chat_flotante(self._host)

    def panel_chat(self) -> ft.Control:
        if getattr(self._host, "ventana_chat_flotante", None) is None:
            self.crear_ventana_chat_flotante()
        return self._host.ventana_chat_flotante  # type: ignore[return-value]

    def escribir_chat(self, emisor: str, mensaje: str) -> None:
        modo_oscuro = bool(getattr(self._host, "modo_oscuro", True))
        from ..design import colores_de

        colores = colores_de(self._host)
        if emisor == "Tú":
            color = colores.etiqueta_emisor
            bgcolor = ft.Colors.RED_900 if modo_oscuro else ft.Colors.RED_50
        else:
            color = ft.Colors.CYAN_200 if modo_oscuro else ft.Colors.TEAL_900
            bgcolor = ft.Colors.BLUE_GREY_800 if modo_oscuro else ft.Colors.GREY_100
        self._host.conversacion.controls.append(
            ft.Container(
                bgcolor=bgcolor,
                border_radius=10,
                padding=10,
                content=ft.Column(
                    [
                        ft.Text(emisor, size=10, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(mensaje, size=12, color=self._host.texto),
                    ],
                    spacing=3,
                ),
            )
        )

    async def enviar_chat(self, _evento: ft.Event | None = None) -> None:
        if not self._exigir_roles(*USER_ROLES):
            return
        mensaje = (self._host.entrada_chat.value or "").strip()
        if not mensaje:
            return
        self._host.entrada_chat.value = ""
        self.escribir_chat("Tú", mensaje)
        await procesar_mensaje_chat_agente(self._host, mensaje)
