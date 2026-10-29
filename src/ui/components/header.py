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

    fila_acciones: list[ft.Control] = []
    if interfaz.usuario_actual.role == "administrador":
        fila_acciones.append(interfaz.contenedor_notificaciones)
    fila_acciones.extend(
        [
            boton_tema,
            ft.IconButton(
                icon=ft.Icons.BADGE_OUTLINED,
                tooltip="Mi perfil (Nombre y Email)",
                icon_color=interfaz.secundario,
                on_click=interfaz.mostrar_mi_perfil,
            ),
            ft.IconButton(
                icon=ft.Icons.KEY,
                tooltip="Cambiar mi contraseña",
                icon_color=interfaz.secundario,
                on_click=interfaz.mostrar_cambiar_mi_clave,
            ),
            ft.TextButton(
                f"{interfaz.usuario_actual.nombre_identificador} · Cerrar sesión",
                icon=ft.Icons.LOGOUT,
                on_click=interfaz.cerrar_sesion,
            ),
            interfaz.boton(
                "Actualizar", ft.Icons.REFRESH, interfaz.actualizar_estado, 150
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
                        f"Gestiona tus documentos, inventario y actividad · Red local: {esquema_red}://{ip_red}:{puerto_red}",
                        size=14,
                        color=interfaz.secundario,
                    ),
                    interfaz.pendientes_texto,
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
