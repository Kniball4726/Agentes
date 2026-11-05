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

    opciones_menu_usuario = [
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
    ]

    if interfaz.es_pantalla_movil:
        btn_menu = ft.IconButton(
            icon=ft.Icons.MENU,
            icon_color=interfaz.texto,
            tooltip="Menú de navegación",
            on_click=interfaz._abrir_drawer_click,
        )
        boton_buscar_movil = ft.IconButton(
            icon=ft.Icons.SEARCH,
            icon_size=20,
            tooltip="Búsqueda Rápida Global (Ctrl + K o F2)",
            icon_color=ft.Colors.WHITE,
            bgcolor=ft.Colors.BLUE_GREY_700 if not interfaz.modo_oscuro else interfaz.fondo_acento,
            on_click=interfaz.mostrar_command_palette,
        )
        rol_etiqueta = (interfaz.usuario_actual.role or "").capitalize()
        nombre_mostrar = interfaz.usuario_actual.nombre_identificador
        usuario_conectado_movil = ft.Container(
            expand=True,
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=20,
            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
            content=ft.PopupMenuButton(
                tooltip="Mi Cuenta y Opciones",
                items=opciones_menu_usuario,
                content=ft.Row(
                    [
                        ft.CircleAvatar(
                            content=ft.Text(
                                (nombre_mostrar or "U")[:1].upper(),
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            radius=12,
                            bgcolor=ROJO,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    nombre_mostrar,
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=interfaz.texto,
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    f"@{interfaz.usuario_actual.username} · {rol_etiqueta}",
                                    size=10,
                                    color=interfaz.secundario,
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=0,
                            tight=True,
                            expand=True,
                        ),
                        ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16, color=interfaz.secundario),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )
        boton_tema_movil = ft.IconButton(
            icon=ft.Icons.WB_SUNNY if interfaz.modo_oscuro else ft.Icons.DARK_MODE,
            icon_size=20,
            tooltip="Modo claro" if interfaz.modo_oscuro else "Modo oscuro",
            icon_color=ft.Colors.AMBER_300 if interfaz.modo_oscuro else ft.Colors.WHITE,
            bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_700,
            on_click=interfaz.alternar_tema,
        )
        boton_actualizar_movil = ft.IconButton(
            icon=ft.Icons.REFRESH,
            icon_size=20,
            tooltip="Actualizar",
            icon_color=ft.Colors.WHITE,
            bgcolor=ROJO,
            on_click=interfaz.actualizar_estado,
        )
        interfaz.controles_tarea.append(boton_actualizar_movil)

        controles_titulo_movil: list[ft.Control] = [
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
        ]
        if interfaz.usuario_actual.role == "administrador":
            controles_titulo_movil.append(interfaz.contenedor_notificaciones)
        dot_conexion_movil = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_400, size=8),
                    ft.Text("En línea", size=10, color=ft.Colors.GREEN_400 if interfaz.modo_oscuro else ft.Colors.GREEN_700, weight=ft.FontWeight.W_500),
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=10,
            bgcolor=ft.Colors.GREEN_900 if interfaz.modo_oscuro else ft.Colors.GREEN_50,
            tooltip="Conectado al servidor local de StockAgent",
        )
        interfaz.semaforo_conexion_movil = dot_conexion_movil
        controles_titulo_movil.append(dot_conexion_movil)

        return ft.Column(
            [
                ft.Row(
                    controles_titulo_movil,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        boton_buscar_movil,
                        usuario_conectado_movil,
                        boton_tema_movil,
                        boton_actualizar_movil,
                    ],
                    wrap=False,
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=8,
        )

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
        items=opciones_menu_usuario,
    )

    boton_buscar = ft.IconButton(
        icon=ft.Icons.SEARCH,
        tooltip="Búsqueda Rápida Global (Ctrl + K o F2)",
        icon_color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLUE_GREY_700 if not interfaz.modo_oscuro else interfaz.fondo_acento,
        on_click=interfaz.mostrar_command_palette,
    )

    semaforo_conexion = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_400, size=9),
                ft.Text("En línea", size=11, color=ft.Colors.GREEN_400 if interfaz.modo_oscuro else ft.Colors.GREEN_700, weight=ft.FontWeight.W_500),
            ],
            spacing=5,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=16,
        border=ft.Border.all(1, ft.Colors.GREEN_800 if interfaz.modo_oscuro else ft.Colors.GREEN_300),
        bgcolor=ft.Colors.GREEN_900 if interfaz.modo_oscuro else ft.Colors.GREEN_50,
        tooltip="Conectado al servidor local de StockAgent y sincronizado",
    )

    pos_actual = getattr(interfaz, "posicion_sidebar", "izquierda")

    def _item_dock(label: str, pos_key: str, icon_data: ft.IconData) -> ft.PopupMenuItem:
        activo = (pos_actual == pos_key)
        return ft.PopupMenuItem(
            icon=ft.Icons.CHECK if activo else icon_data,
            content=ft.Text(f"{label} (Activo)" if activo else label, weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL),
            on_click=lambda _e, k=pos_key: interfaz.cambiar_posicion_sidebar(k),
        )

    boton_dock = ft.PopupMenuButton(
        icon=ft.Icons.VIEW_SIDEBAR_OUTLINED if pos_actual != "oculto" else ft.Icons.FULLSCREEN,
        tooltip=f"Posición de barra de menú: {pos_actual.capitalize()} (Clic para mover)",
        items=[
            _item_dock("Barra a la Izquierda", "izquierda", ft.Icons.DOCK),
            _item_dock("Barra a la Derecha", "derecha", ft.Icons.DOCK),
            _item_dock("Barra Arriba (Horizontal)", "arriba", ft.Icons.HORIZONTAL_SPLIT),
            _item_dock("Barra Abajo (Horizontal)", "abajo", ft.Icons.HORIZONTAL_SPLIT),
            _item_dock("Ocultar Barra (Pantalla Completa)", "oculto", ft.Icons.FULLSCREEN),
        ],
    )

    interfaz.semaforo_conexion = semaforo_conexion
    fila_acciones: list[ft.Control] = [semaforo_conexion]
    if interfaz.usuario_actual.role == "administrador":
        fila_acciones.append(interfaz.contenedor_notificaciones)
    fila_acciones.extend(
        [
            boton_buscar,
            boton_dock,
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
