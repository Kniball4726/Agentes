"""Componente de encabezado de la aplicación."""

import os
from typing import Any

import flet as ft

from ..theme import ROJO


def construir_encabezado(interfaz: Any) -> ft.Control:
    """Construye el encabezado superior con acciones de usuario, tema y estado de red."""
    assert interfaz.usuario_actual is not None
    from ...flet_gui import PUERTO_WEB_DEFAULT, obtener_ip_local

    boton_tema = ft.Button(
        content="Modo claro" if interfaz.modo_oscuro else "Modo oscuro",
        icon=ft.Icons.WB_SUNNY if interfaz.modo_oscuro else ft.Icons.DARK_MODE,
        on_click=interfaz.alternar_tema,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
    )
    interfaz._actualizar_icono_notificaciones()

    menu_usuario = ft.PopupMenuButton(
        content=ft.Row(
            [
                ft.CircleAvatar(
                    content=ft.Text(
                        (interfaz.usuario_actual.nombre_identificador or "U")[:1].upper(),
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    radius=14,
                    bgcolor=ROJO,
                ),
                ft.Text(
                    interfaz.usuario_actual.nombre_identificador,
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=interfaz.texto,
                ),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16, color=interfaz.secundario),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        tooltip="Mi Cuenta y Opciones",
        items=[
            ft.PopupMenuItem(
                icon=ft.Icons.BADGE_OUTLINED,
                content="Mi Perfil (Nombre y Email)",
                on_click=interfaz.mostrar_mi_perfil,
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.KEY,
                content="Cambiar mi contraseña",
                on_click=interfaz.mostrar_cambiar_mi_clave,
            ),
            ft.PopupMenuItem(),
            ft.PopupMenuItem(
                icon=ft.Icons.LOGOUT,
                content="Cerrar sesión",
                on_click=interfaz.cerrar_sesion,
            ),
        ],
    )

    boton_buscar = ft.IconButton(
        icon=ft.Icons.SEARCH,
        tooltip="Búsqueda Rápida Global (Ctrl + K o F2)",
        icon_color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLUE_GREY_700 if not interfaz.modo_oscuro else interfaz.fondo_acento,
        on_click=interfaz.mostrar_command_palette,
    )

    fila_acciones: list[ft.Control] = []
    if interfaz.usuario_actual.role == "administrador":
        fila_acciones.append(interfaz.contenedor_notificaciones)
    fila_acciones.extend(
        [
            boton_buscar,
            boton_tema,
            menu_usuario,
            interfaz.boton(
                "Actualizar", ft.Icons.REFRESH, interfaz.actualizar_estado, 130
            ),
        ]
    )

    ip_red = obtener_ip_local()
    puerto_red = os.environ.get("STOCKAGENT_PORT", str(PUERTO_WEB_DEFAULT))
    esquema_red = os.environ.get("STOCKAGENT_SCHEME", "http")

    if interfaz.es_pantalla_movil:
        btn_menu = ft.IconButton(
            icon=ft.Icons.MENU,
            icon_color=interfaz.texto,
            tooltip="Menú de navegación",
            on_click=interfaz._abrir_drawer_click,
        )
        return ft.Column(
            [
                ft.Row(
                    [
                        btn_menu,
                        ft.Column(
                            [
                                ft.Text(
                                    "Panel de control",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color=interfaz.texto,
                                ),
                                interfaz.pendientes_texto,
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    fila_acciones,
                    wrap=True,
                    spacing=6,
                ),
            ],
            spacing=8,
        )

    return ft.Row(
        [
            ft.Column(
                [
                    ft.Text(
                        "Panel de control",
                        size=28,
                        weight=ft.FontWeight.BOLD,
                        color=interfaz.texto,
                    ),
                    ft.Text(
                        (f"Consola de Seguridad, IAM y Auditoría · Red local: {esquema_red}://{ip_red}:{puerto_red}"
                         if interfaz.usuario_actual.role == "master"
                         else f"Gestiona tus documentos, inventario y actividad · Red local: {esquema_red}://{ip_red}:{puerto_red}"),
                        size=14,
                        color=interfaz.secundario,
                    ),
                    (ft.Text("Módulo de Administración Técnica y Auditoría de Seguridad", size=12, color=ROJO, weight=ft.FontWeight.BOLD)
                     if interfaz.usuario_actual.role == "master"
                     else interfaz.pendientes_texto),
                ],
                spacing=4,
            ),
            ft.Row(
                fila_acciones,
                spacing=10,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
