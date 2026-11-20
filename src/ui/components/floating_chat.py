"""Componente de ventana de chat flotante (Asistente Bot y Chat de Equipo)."""

from __future__ import annotations

from typing import Any

import flet as ft

from ...chat import (
    obtener_chips_configuracion,
    obtener_pie_ayuda,
)
from ...inventory import StockManager
from ...paths import application_root
from ..theme import ROJO
from .floating_chat_intents import procesar_mensaje_chat_agente

_ICONOS_CHAT = {
    "SEARCH": ft.Icons.SEARCH,
    "WARNING_AMBER_ROUNDED": ft.Icons.WARNING_AMBER_ROUNDED,
    "PRECISION_MANUFACTURING": ft.Icons.PRECISION_MANUFACTURING,
    "ANALYTICS": ft.Icons.ANALYTICS,
    "HISTORY": ft.Icons.HISTORY,
    "BACKUP": ft.Icons.BACKUP,
    "FACT_CHECK": ft.Icons.FACT_CHECK,
    "DASHBOARD": ft.Icons.DASHBOARD,
    "DESCRIPTION": ft.Icons.DESCRIPTION,
    "SCIENCE": ft.Icons.SCIENCE,
    "INVENTORY_2": ft.Icons.INVENTORY_2,
    "POINT_OF_SALE": ft.Icons.POINT_OF_SALE,
    "LOCAL_SHIPPING": ft.Icons.LOCAL_SHIPPING,
    "FOLDER_OPEN": ft.Icons.FOLDER_OPEN,
    "HELP_OUTLINE": ft.Icons.HELP_OUTLINE,
    "CHAT": ft.Icons.CHAT,
}


def crear_ventana_chat_flotante(interfaz: Any) -> ft.Container:
    """Construye y devuelve el contenedor del chat flotante con pestañas de Asistente Bot y Chat de Equipo."""
    rol_actual = interfaz.usuario_actual.role if interfaz.usuario_actual else "operador"
    ico_encabezado = ft.Icon(
        ft.Icons.FORUM if interfaz.modo_chat_activo == "equipo" else ft.Icons.SMART_TOY,
        color=ft.Colors.WHITE if interfaz.modo_oscuro else ROJO,
        size=18,
    )
    encabezado_chat = ft.Row(
        [
            ft.Row(
                [
                    ft.Container(
                        width=34,
                        height=34,
                        border_radius=10,
                        bgcolor=ft.Colors.RED_900 if interfaz.modo_oscuro else ft.Colors.RED_50,
                        alignment=ft.Alignment.CENTER,
                        content=ico_encabezado,
                    ),
                    ft.Column(
                        [
                            ft.Text("StockAgent · Chat y Asistente", size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_400, size=8),
                                    ft.Text(f"Rol: {rol_actual.capitalize()} · En línea", size=10, color=interfaz.secundario),
                                ],
                                spacing=4,
                            ),
                        ],
                        spacing=1,
                    ),
                ],
                spacing=8,
            ),
            ft.Row(
                [
                    ft.IconButton(icon=ft.Icons.DELETE_SWEEP_OUTLINED, icon_color=interfaz.secundario, icon_size=18, tooltip="Limpiar conversación del bot", on_click=interfaz.limpiar_chat),
                    ft.IconButton(icon=ft.Icons.KEYBOARD_ARROW_DOWN, icon_color=interfaz.secundario, icon_size=20, tooltip="Minimizar", on_click=interfaz.alternar_chat_flotante),
                    ft.IconButton(icon=ft.Icons.CLOSE, icon_color=interfaz.secundario, icon_size=18, tooltip="Cerrar", on_click=interfaz.cerrar_chat_flotante),
                ],
                spacing=0,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    chips_controles = []
    for item in obtener_chips_configuracion(rol_actual):
        if len(item) == 3:
            etiqueta, comando, ico_nombre = item
        else:
            etiqueta, comando = item
            ico_nombre = "SMART_TOY"
        icono = _ICONOS_CHAT.get(ico_nombre, ft.Icons.SMART_TOY)
        chips_controles.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icono, size=13, color=ft.Colors.WHITE if interfaz.modo_oscuro else ROJO),
                        ft.Text(etiqueta, size=11, weight=ft.FontWeight.W_600, color=interfaz.texto, no_wrap=True),
                    ],
                    spacing=5,
                    tight=True,
                ),
                bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=14,
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                ink=True,
                tooltip=f"Comando {comando} - Clic para ejecutar",
                on_click=lambda _e, cmd=comando: interfaz.ejecutar_comando_rapido(cmd),
            )
        )

    es_bot = interfaz.modo_chat_activo == "bot"
    cuerpo_bot = ft.Column(
        [
            ft.Row(chips_controles, scroll=ft.ScrollMode.AUTO, spacing=6),
            ft.Divider(height=6, color=interfaz.borde),
            interfaz.conversacion,
            ft.Row(
                [
                    interfaz.entrada_chat,
                    ft.IconButton(icon=ft.Icons.SEND, icon_color=ft.Colors.WHITE, bgcolor=ROJO, tooltip="Enviar mensaje al bot", on_click=interfaz.enviar_chat),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
            ft.Text(obtener_pie_ayuda(rol_actual), size=10, color=interfaz.secundario),
        ],
        expand=True,
        spacing=6,
        visible=es_bot,
    )

    cuerpo_equipo = ft.Column(
        [
            ft.Row(
                [
                    interfaz.selector_destinatario_equipo,
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        icon_size=18,
                        tooltip="Actualizar mensajes",
                        on_click=lambda _e: (
                            interfaz.refrescar_usuarios_chat_equipo(),
                            interfaz.cargar_mensajes_equipo(),
                            interfaz.marcar_mensajes_chat_leidos(solo_tab="equipo")
                            if hasattr(interfaz, "marcar_mensajes_chat_leidos")
                            else None,
                        ),
                    ),
                ],
                spacing=6,
            ),
            ft.Divider(height=6, color=interfaz.borde),
            interfaz.conversacion_equipo,
            ft.Row(
                [
                    interfaz.entrada_chat_equipo,
                    ft.IconButton(icon=ft.Icons.SEND, icon_color=ft.Colors.WHITE, bgcolor=ROJO, tooltip="Enviar al equipo", on_click=interfaz.enviar_mensaje_equipo),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ],
        expand=True,
        spacing=6,
        visible=not es_bot,
    )

    def cambiar_tab(modo: str) -> None:
        interfaz.modo_chat_activo = modo
        es_bot_nuevo = modo == "bot"
        cuerpo_bot.visible = es_bot_nuevo
        cuerpo_equipo.visible = not es_bot_nuevo

        bg_inact = ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200
        btn_tab_bot.bgcolor = ROJO if es_bot_nuevo else bg_inact
        txt_tab_bot.color = ft.Colors.WHITE if es_bot_nuevo else interfaz.texto
        ico_tab_bot.color = ft.Colors.WHITE if es_bot_nuevo else interfaz.texto

        btn_tab_equipo.bgcolor = ROJO if not es_bot_nuevo else bg_inact
        txt_tab_equipo.color = ft.Colors.WHITE if not es_bot_nuevo else interfaz.texto
        ico_tab_equipo.color = ft.Colors.WHITE if not es_bot_nuevo else interfaz.texto
        ico_encabezado.icon = ft.Icons.SMART_TOY if es_bot_nuevo else ft.Icons.FORUM

        if modo == "bot":
            if hasattr(interfaz, "marcar_mensajes_chat_leidos"):
                interfaz.marcar_mensajes_chat_leidos(solo_tab="bot")
        elif modo == "equipo":
            interfaz.refrescar_usuarios_chat_equipo()
            interfaz.cargar_mensajes_equipo()
            if hasattr(interfaz, "marcar_mensajes_chat_leidos"):
                interfaz.marcar_mensajes_chat_leidos(solo_tab="equipo")
            elif interfaz.usuario_actual:
                interfaz.order_store.marcar_mensajes_leidos(interfaz.usuario_actual.username)
                interfaz.actualizar_badge_chat()
        interfaz.page.update()

    interfaz._cambiar_tab_fn = cambiar_tab

    punto_tab_bot = ft.Container(
        width=8,
        height=8,
        border_radius=4,
        bgcolor=ft.Colors.RED_500,
        border=ft.Border.all(1, ft.Colors.WHITE),
        visible=bool(getattr(interfaz, "_mensajes_bot_no_leidos", 0) > 0),
    )
    interfaz.punto_tab_bot = punto_tab_bot
    ico_tab_bot = ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=15, color=ft.Colors.WHITE if es_bot else interfaz.texto)
    txt_tab_bot = ft.Text("Asistente Bot", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE if es_bot else interfaz.texto)
    btn_tab_bot = ft.Container(
        content=ft.Row([ico_tab_bot, txt_tab_bot, punto_tab_bot], spacing=5, tight=True),
        bgcolor=ROJO if es_bot else (ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=12,
        ink=True,
        on_click=lambda _e: cambiar_tab("bot"),
    )

    punto_tab_equipo = ft.Container(
        width=8,
        height=8,
        border_radius=4,
        bgcolor=ft.Colors.RED_500,
        border=ft.Border.all(1, ft.Colors.WHITE),
        visible=False,
    )
    interfaz.punto_tab_equipo = punto_tab_equipo
    ico_tab_equipo = ft.Icon(ft.Icons.FORUM_OUTLINED, size=15, color=interfaz.texto if es_bot else ft.Colors.WHITE)
    txt_tab_equipo = ft.Text("Chat Equipo", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto if es_bot else ft.Colors.WHITE)
    btn_tab_equipo = ft.Container(
        content=ft.Row([ico_tab_equipo, txt_tab_equipo, interfaz.texto_badge_tab, punto_tab_equipo], spacing=5, tight=True),
        bgcolor=(ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200) if es_bot else ROJO,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=12,
        ink=True,
        on_click=lambda _e: cambiar_tab("equipo"),
    )

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    alto_movil = (
        interfaz.alto_adaptable(480, margen=80)
        if hasattr(interfaz, "alto_adaptable")
        else 480
    )
    ventana = ft.Container(
        width=None if es_movil else 420,
        height=alto_movil if es_movil else 550,
        left=8 if es_movil else None,
        right=8 if es_movil else 24,
        bottom=75 if es_movil else 90,
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=16,
        shadow=ft.BoxShadow(
            blur_radius=22,
            spread_radius=2,
            color=ft.Colors.BLACK_54 if interfaz.modo_oscuro else ft.Colors.BLACK_26,
            offset=ft.Offset(0, 8),
        ),
        padding=10 if es_movil else 14,
        visible=interfaz.chat_visible,
        content=ft.Column([encabezado_chat, ft.Row([btn_tab_bot, btn_tab_equipo], spacing=8), cuerpo_bot, cuerpo_equipo], expand=True, spacing=8),
    )
    interfaz.ventana_chat_flotante = ventana
    return ventana


__all__ = [
    "StockManager",
    "application_root",
    "crear_ventana_chat_flotante",
    "procesar_mensaje_chat_agente",
]
