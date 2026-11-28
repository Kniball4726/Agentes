"""Componente de encabezado de la aplicación."""

import os
from typing import Any

import flet as ft

from ...paths import is_qa_environment
from ..theme import FUENTE_MENU, FUENTE_MENU_BOLD, ROJO, estilo_texto_menu


def _crear_badge_qa(tamano: str = "desktop") -> ft.Control | None:
    if not is_qa_environment():
        return None
    es_movil = tamano == "movil"
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.BUG_REPORT, size=12 if es_movil else 14, color=ft.Colors.BLACK),
                ft.Text(
                    "AMBIENTE QA",
                    size=9 if es_movil else 11,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.BLACK,
                ),
            ],
            spacing=4,
            tight=True,
        ),
        bgcolor=ft.Colors.AMBER_400,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=6 if es_movil else 8, vertical=2 if es_movil else 3),
        tooltip="Modo Pruebas QA: Base de datos aislada (data_qa), no afecta datos reales.",
    )


def _crear_opciones_menu_usuario(interfaz: Any) -> list[ft.PopupMenuItem]:
    estilo_item = estilo_texto_menu(color=interfaz.texto)
    return [
        ft.PopupMenuItem(
            icon=ft.Icons.BADGE_OUTLINED,
            content="Mi Perfil (Nombre y Email)",
            label_text_style=estilo_item,
            on_click=interfaz.mostrar_mi_perfil,
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.KEY,
            content="Cambiar mi contraseña",
            label_text_style=estilo_item,
            on_click=interfaz.mostrar_cambiar_mi_clave,
        ),
        ft.PopupMenuItem(),
        ft.PopupMenuItem(
            icon=ft.Icons.LOGOUT,
            content="Cerrar sesión",
            label_text_style=estilo_item,
            on_click=interfaz.cerrar_sesion,
        ),
    ]


def _crear_semaforo_conexion(modo_oscuro: bool, *, compacto: bool) -> ft.Container:
    color_texto = ft.Colors.GREEN_400 if modo_oscuro else ft.Colors.GREEN_700
    bgcolor = ft.Colors.GREEN_900 if modo_oscuro else ft.Colors.GREEN_50
    if compacto:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_400, size=8),
                    ft.Text("En línea", size=10, color=color_texto, weight=ft.FontWeight.W_500),
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=10,
            bgcolor=bgcolor,
            tooltip="Conectado al servidor local de StockAgent",
        )
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_400, size=9),
                ft.Text("En línea", size=11, color=color_texto, weight=ft.FontWeight.W_500),
            ],
            spacing=5,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=16,
        border=ft.Border.all(1, ft.Colors.GREEN_800 if modo_oscuro else ft.Colors.GREEN_300),
        bgcolor=bgcolor,
        tooltip="Conectado al servidor local de StockAgent y sincronizado",
    )


def _crear_menu_usuario_movil(
    interfaz: Any,
    opciones_menu_usuario: list[ft.PopupMenuItem],
) -> ft.Container:
    rol_etiqueta = (interfaz.usuario_actual.role or "").capitalize()
    nombre_mostrar = interfaz.usuario_actual.nombre_identificador
    return ft.Container(
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
                            font_family=FUENTE_MENU_BOLD,
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
                                font_family=FUENTE_MENU_BOLD,
                            ),
                            ft.Text(
                                f"@{interfaz.usuario_actual.username} · {rol_etiqueta}",
                                size=10,
                                color=interfaz.secundario,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                font_family=FUENTE_MENU,
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


def _crear_menu_usuario_desktop(
    interfaz: Any,
    opciones_menu_usuario: list[ft.PopupMenuItem],
) -> ft.PopupMenuButton:
    nombre_mostrar = interfaz.usuario_actual.nombre_identificador
    return ft.PopupMenuButton(
        content=ft.Row(
            [
                ft.CircleAvatar(
                    content=ft.Text(
                        (nombre_mostrar or "U")[:1].upper(),
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                        font_family=FUENTE_MENU_BOLD,
                    ),
                    radius=14,
                    bgcolor=ROJO,
                ),
                ft.Text(
                    nombre_mostrar,
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=interfaz.texto,
                    font_family=FUENTE_MENU_BOLD,
                ),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16, color=interfaz.secundario),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        tooltip="Mi Cuenta y Opciones",
        items=opciones_menu_usuario,
    )


def _crear_boton_dock(interfaz: Any) -> ft.PopupMenuButton:
    pos_actual = getattr(interfaz, "posicion_sidebar", "izquierda")
    opciones_dock = (
        ("Barra a la Izquierda", "izquierda", ft.Icons.DOCK),
        ("Barra a la Derecha", "derecha", ft.Icons.DOCK),
        ("Barra Arriba (Horizontal)", "arriba", ft.Icons.HORIZONTAL_SPLIT),
        ("Barra Abajo (Horizontal)", "abajo", ft.Icons.HORIZONTAL_SPLIT),
        ("Ocultar Barra (Pantalla Completa)", "oculto", ft.Icons.FULLSCREEN),
    )
    items: list[ft.PopupMenuItem] = []
    for label, pos_key, icon_data in opciones_dock:
        activo = pos_actual == pos_key
        items.append(
            ft.PopupMenuItem(
                icon=ft.Icons.CHECK if activo else icon_data,
                content=ft.Text(
                    f"{label} (Activo)" if activo else label,
                    weight=ft.FontWeight.BOLD if activo else ft.FontWeight.NORMAL,
                    font_family=FUENTE_MENU_BOLD if activo else FUENTE_MENU,
                    color=interfaz.texto,
                ),
                label_text_style=estilo_texto_menu(
                    "bold" if activo else "regular",
                    color=interfaz.texto,
                ),
                on_click=lambda _e, k=pos_key: interfaz.cambiar_posicion_sidebar(k),
            )
        )
    return ft.PopupMenuButton(
        icon=ft.Icons.VIEW_SIDEBAR_OUTLINED if pos_actual != "oculto" else ft.Icons.FULLSCREEN,
        tooltip=f"Posición de barra de menú: {pos_actual.capitalize()} (Clic para mover)",
        items=items,
    )


def _construir_encabezado_movil(
    interfaz: Any,
    opciones_menu_usuario: list[ft.PopupMenuItem],
) -> ft.Control:
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
    usuario_conectado_movil = _crear_menu_usuario_movil(interfaz, opciones_menu_usuario)
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

    badge_qa_movil = _crear_badge_qa("movil")
    controles_titulo: list[ft.Control] = [
        btn_menu,
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Panel de control",
                            size=20,
                            weight=ft.FontWeight.BOLD,
                            color=interfaz.texto,
                        ),
                        *([badge_qa_movil] if badge_qa_movil else []),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                interfaz.pendientes_texto,
            ],
            spacing=2,
            expand=True,
        ),
    ]
    if interfaz.usuario_actual.role == "administrador":
        controles_titulo.append(interfaz.contenedor_notificaciones)

    dot_conexion_movil = _crear_semaforo_conexion(interfaz.modo_oscuro, compacto=True)
    interfaz.semaforo_conexion_movil = dot_conexion_movil
    controles_titulo.append(dot_conexion_movil)

    return ft.Column(
        [
            ft.Row(controles_titulo, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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


def _construir_bloque_titulo_desktop(interfaz: Any, url_red: str) -> ft.Column:
    rol = interfaz.usuario_actual.role
    titulo = "Módulo Despacho" if rol == "despachador" else "Panel de control"
    if rol == "master":
        subtitulo = f"Consola de Seguridad, IAM y Auditoría · Red local: {url_red}"
        pie: ft.Control = ft.Text(
            "Módulo de Administración Técnica y Auditoría de Seguridad",
            size=12,
            color=ROJO,
            weight=ft.FontWeight.BOLD,
        )
    elif rol == "despachador":
        subtitulo = f"Control de despacho por pistola QR y cantidad de bultos · Red local: {url_red}"
        pie = interfaz.pendientes_texto
    else:
        subtitulo = f"Gestiona tus documentos, inventario y actividad · Red local: {url_red}"
        pie = (
            ft.Text(
                "Módulo de Picking y Despacho · Movimientos de Stock",
                size=12,
                color=ROJO,
                weight=ft.FontWeight.BOLD,
            )
            if rol == "picker"
            else interfaz.pendientes_texto
        )

    badge_qa = _crear_badge_qa("desktop")
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        titulo,
                        size=28,
                        weight=ft.FontWeight.BOLD,
                        color=interfaz.texto,
                    ),
                    *([badge_qa] if badge_qa else []),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Text(
                subtitulo,
                size=14,
                color=interfaz.secundario,
                overflow=ft.TextOverflow.ELLIPSIS,
                max_lines=2,
            ),
            pie,
        ],
        spacing=4,
        expand=True,
    )


def _obtener_url_red_local() -> str:
    from ...server_app import PUERTO_WEB_DEFAULT, obtener_ip_local

    ip_red = obtener_ip_local()
    puerto_red = os.environ.get("STOCKAGENT_PORT", str(PUERTO_WEB_DEFAULT))
    esquema_red = os.environ.get("STOCKAGENT_SCHEME", "http")
    return f"{esquema_red}://{ip_red}:{puerto_red}"


def _construir_encabezado_desktop(
    interfaz: Any,
    opciones_menu_usuario: list[ft.PopupMenuItem],
    boton_tema: ft.Button,
) -> ft.Control:
    semaforo_conexion = _crear_semaforo_conexion(interfaz.modo_oscuro, compacto=False)
    interfaz.semaforo_conexion = semaforo_conexion

    boton_buscar = ft.IconButton(
        icon=ft.Icons.SEARCH,
        tooltip="Búsqueda Rápida Global (Ctrl + K o F2)",
        icon_color=ft.Colors.WHITE,
        bgcolor=ft.Colors.BLUE_GREY_700 if not interfaz.modo_oscuro else interfaz.fondo_acento,
        on_click=interfaz.mostrar_command_palette,
    )

    fila_acciones: list[ft.Control] = [semaforo_conexion]
    if interfaz.usuario_actual.role == "administrador":
        fila_acciones.append(interfaz.contenedor_notificaciones)
    fila_acciones.extend(
        [
            boton_buscar,
            _crear_boton_dock(interfaz),
            boton_tema,
            _crear_menu_usuario_desktop(interfaz, opciones_menu_usuario),
            interfaz.boton("Actualizar", ft.Icons.REFRESH, interfaz.actualizar_estado, 130),
        ]
    )

    return ft.Row(
        [
            _construir_bloque_titulo_desktop(interfaz, _obtener_url_red_local()),
            ft.Row(fila_acciones, spacing=10, wrap=True),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def construir_encabezado(interfaz: Any) -> ft.Control:
    """Construye el encabezado superior con acciones de usuario, tema y estado de red."""
    if interfaz.usuario_actual is None:
        raise ValueError("No hay un usuario autenticado para construir el encabezado.")

    interfaz._actualizar_icono_notificaciones()
    opciones_menu_usuario = _crear_opciones_menu_usuario(interfaz)
    if interfaz.es_pantalla_movil:
        return _construir_encabezado_movil(interfaz, opciones_menu_usuario)

    boton_tema = ft.Button(
        content="Modo claro" if interfaz.modo_oscuro else "Modo oscuro",
        icon=ft.Icons.WB_SUNNY if interfaz.modo_oscuro else ft.Icons.DARK_MODE,
        on_click=interfaz.alternar_tema,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
    )
    return _construir_encabezado_desktop(interfaz, opciones_menu_usuario, boton_tema)
