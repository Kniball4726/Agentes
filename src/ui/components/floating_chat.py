"""Componente de ventana de chat flotante (Asistente Bot y Chat de Equipo)."""
from typing import Any
import flet as ft
from ...internal_chat import obtener_chips_configuracion, obtener_pie_ayuda
from ..theme import ROJO


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
                            ft.Text(
                                "StockAgent · Chat y Asistente",
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=interfaz.texto,
                            ),
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
                    ft.IconButton(
                        icon=ft.Icons.DELETE_SWEEP_OUTLINED,
                        icon_color=interfaz.secundario,
                        icon_size=18,
                        tooltip="Limpiar conversación del bot",
                        on_click=interfaz.limpiar_chat,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
                        icon_color=interfaz.secundario,
                        icon_size=20,
                        tooltip="Minimizar",
                        on_click=interfaz.alternar_chat_flotante,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        icon_color=interfaz.secundario,
                        icon_size=18,
                        tooltip="Cerrar",
                        on_click=interfaz.cerrar_chat_flotante,
                    ),
                ],
                spacing=0,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    def mapear_icono(nombre: str) -> str:
        iconos = {
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
        return iconos.get(nombre, ft.Icons.SMART_TOY)

    chips_def = obtener_chips_configuracion(rol_actual)
    chips_controles = []
    for item in chips_def:
        if len(item) == 3:
            etiqueta, comando, ico_nombre = item
        else:
            etiqueta, comando = item
            ico_nombre = "SMART_TOY"
        icono = mapear_icono(ico_nombre)
        boton_func = ft.Container(
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
        chips_controles.append(boton_func)

    chips_fila = ft.Row(
        chips_controles,
        scroll=ft.ScrollMode.AUTO,
        spacing=6,
    )

    input_fila = ft.Row(
        [
            interfaz.entrada_chat,
            ft.IconButton(
                icon=ft.Icons.SEND,
                icon_color=ft.Colors.WHITE,
                bgcolor=ROJO,
                tooltip="Enviar mensaje al bot",
                on_click=interfaz.enviar_chat,
            ),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.END,
    )

    pie_texto = ft.Text(
        obtener_pie_ayuda(rol_actual),
        size=10,
        color=interfaz.secundario,
    )

    es_bot = interfaz.modo_chat_activo == "bot"
    cuerpo_bot = ft.Column(
        [
            chips_fila,
            ft.Divider(height=6, color=interfaz.borde),
            interfaz.conversacion,
            input_fila,
            pie_texto,
        ],
        expand=True,
        spacing=6,
        visible=es_bot,
    )

    barra_equipo = ft.Row(
        [
            interfaz.selector_destinatario_equipo,
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                icon_size=18,
                tooltip="Actualizar mensajes",
                on_click=lambda _e: (
                    interfaz.refrescar_usuarios_chat_equipo(),
                    interfaz.cargar_mensajes_equipo(),
                ),
            ),
        ],
        spacing=6,
    )

    input_fila_equipo = ft.Row(
        [
            interfaz.entrada_chat_equipo,
            ft.IconButton(
                icon=ft.Icons.SEND,
                icon_color=ft.Colors.WHITE,
                bgcolor=ROJO,
                tooltip="Enviar al equipo",
                on_click=interfaz.enviar_mensaje_equipo,
            ),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    cuerpo_equipo = ft.Column(
        [
            barra_equipo,
            ft.Divider(height=6, color=interfaz.borde),
            interfaz.conversacion_equipo,
            input_fila_equipo,
        ],
        expand=True,
        spacing=6,
        visible=not es_bot,
    )

    def cambiar_tab(modo: str) -> None:
        interfaz.modo_chat_activo = modo
        es_bot_nuevo = (modo == "bot")
        cuerpo_bot.visible = es_bot_nuevo
        cuerpo_equipo.visible = not es_bot_nuevo

        btn_tab_bot.bgcolor = ROJO if es_bot_nuevo else (ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200)
        txt_tab_bot.color = ft.Colors.WHITE if es_bot_nuevo else interfaz.texto
        ico_tab_bot.color = ft.Colors.WHITE if es_bot_nuevo else interfaz.texto

        btn_tab_equipo.bgcolor = ROJO if not es_bot_nuevo else (ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200)
        txt_tab_equipo.color = ft.Colors.WHITE if not es_bot_nuevo else interfaz.texto
        ico_tab_equipo.color = ft.Colors.WHITE if not es_bot_nuevo else interfaz.texto

        ico_encabezado.icon = ft.Icons.SMART_TOY if es_bot_nuevo else ft.Icons.FORUM

        if modo == "equipo":
            interfaz.refrescar_usuarios_chat_equipo()
            interfaz.cargar_mensajes_equipo()
            if interfaz.usuario_actual:
                interfaz.order_store.marcar_mensajes_leidos(interfaz.usuario_actual.username)
                interfaz.actualizar_badge_chat()

        interfaz.page.update()

    interfaz._cambiar_tab_fn = cambiar_tab

    ico_tab_bot = ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=15, color=ft.Colors.WHITE if es_bot else interfaz.texto)
    txt_tab_bot = ft.Text("Asistente Bot", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE if es_bot else interfaz.texto)
    btn_tab_bot = ft.Container(
        content=ft.Row(
            [
                ico_tab_bot,
                txt_tab_bot,
            ],
            spacing=5,
            tight=True,
        ),
        bgcolor=ROJO if es_bot else (ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=12,
        ink=True,
        on_click=lambda _e: cambiar_tab("bot"),
    )

    ico_tab_equipo = ft.Icon(ft.Icons.FORUM_OUTLINED, size=15, color=interfaz.texto if es_bot else ft.Colors.WHITE)
    txt_tab_equipo = ft.Text("Chat Equipo", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto if es_bot else ft.Colors.WHITE)
    btn_tab_equipo = ft.Container(
        content=ft.Row(
            [
                ico_tab_equipo,
                txt_tab_equipo,
                interfaz.texto_badge_tab,
            ],
            spacing=5,
            tight=True,
        ),
        bgcolor=(ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200) if es_bot else ROJO,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=12,
        ink=True,
        on_click=lambda _e: cambiar_tab("equipo"),
    )

    barra_tabs = ft.Row(
        [
            btn_tab_bot,
            btn_tab_equipo,
        ],
        spacing=8,
    )

    es_movil = getattr(interfaz, "es_pantalla_movil", False)
    ventana = ft.Container(
        width=None if es_movil else 420,
        height=480 if es_movil else 550,
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
        content=ft.Column(
            [
                encabezado_chat,
                barra_tabs,
                cuerpo_bot,
                cuerpo_equipo,
            ],
            expand=True,
            spacing=8,
        ),
    )
    interfaz.ventana_chat_flotante = ventana
    return ventana
