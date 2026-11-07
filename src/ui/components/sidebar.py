"""Panel de navegación lateral (Sidebar) interactivo para StockAgent."""

from datetime import datetime
from pathlib import Path
from typing import Any, Callable
import flet as ft

from ..theme import ROJO
from ..user_preferences import (
    guardar_preferencia_usuario,
    obtener_preferencias_usuario,
)
from .sidebar_sections import (
    SeccionMenu,
    obtener_secciones_rol,
    _obtener_seccion_predeterminada,
    verificar_pendientes_categoria,
    actualizar_puntos_pendientes_sidebar,
    _crear_boton_cierre_jornada,
)
from .sidebar_horizontal import construir_sidebar_horizontal_controls
from ..dialogs.dlg_preferencias import mostrar_dialogo_preferencias
from ..dialogs.dlg_movimientos_rapidos import (
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_salida_rapida,
)

def construir_sidebar_controls(interfaz: Any) -> list[ft.Control]:
    """Genera la lista de controles para el panel lateral organizados en menús desplegables tipo acordeón."""
    assert interfaz.usuario_actual is not None
    logo_path = Path(__file__).resolve().parent.parent.parent / "img" / "ultratech.png"
    logo_bytes = logo_path.read_bytes() if logo_path.exists() else b""

    controls: list[ft.Control] = [
        ft.Row(
            [
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=12,
                    bgcolor=ft.Colors.GREY_900 if interfaz.modo_oscuro else ft.Colors.RED_50,
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(0.18, ft.Colors.WHITE) if interfaz.modo_oscuro else ft.Colors.RED_100,
                    ),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Image(
                        src=logo_bytes,
                        width=42,
                        height=42,
                        fit=ft.BoxFit.CONTAIN,
                    ),
                ),
                ft.Column(
                    [
                        ft.Text("StockAgent", size=18, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ft.Text("Panel de control", size=11, color=interfaz.secundario),
                    ],
                    spacing=2,
                ),
            ],
            spacing=10,
        ),
        ft.Text(
            f"{interfaz.usuario_actual.nombre_identificador} · {interfaz.usuario_actual.role}",
            size=11,
            color=interfaz.secundario,
        ),
        ft.Divider(height=16, color=interfaz.borde),
        ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SEARCH, size=15, color=ROJO),
                    ft.Text("Buscar módulo...", size=11, color=interfaz.secundario, expand=True),
                    ft.Container(
                        content=ft.Text("F2", size=9, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                        padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, interfaz.borde)),
                        border_radius=4,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, interfaz.borde)),
            bgcolor=ft.Colors.with_opacity(0.04, interfaz.texto),
            tooltip="Búsqueda Rápida Universal (Ctrl + K o F2)",
            on_click=lambda _: interfaz.mostrar_command_palette(),
            ink=True,
        ),
        ft.Container(height=4),
    ]

    secciones = obtener_secciones_rol(interfaz)
    username = interfaz.usuario_actual.username
    rol = interfaz.usuario_actual.role

    # Botonera de Acceso Rápido en menú lateral:
    # - Master: Usuarios y Auditoría
    # - Picker: Entrada, Salida y Descontar Mercado Libre
    # - Administrador: Solo Entrada y Salida (Ingreso y Egreso)
    # - Operador: Entrada, Salida, Cargar Pedido y Mercado Libre
    if rol in ("operador", "administrador", "picker", "master"):
        if rol == "master":
            btn_usr = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.MANAGE_ACCOUNTS, size=14, color=ft.Colors.BLUE_500),
                        ft.Text("Usuarios", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
                expand=True,
                height=32,
                border_radius=7,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
                tooltip="⚡ Gestión y control de cuentas IAM",
                on_click=lambda _: interfaz.mostrar_gestion_usuarios(),
                ink=True,
            )
            btn_aud = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.SECURITY, size=14, color=ROJO),
                        ft.Text("Auditoría", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
                expand=True,
                height=32,
                border_radius=7,
                bgcolor=ft.Colors.with_opacity(0.08, ROJO),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ROJO)),
                tooltip="⚡ Registro de eventos y trazabilidad forense",
                on_click=lambda _: interfaz.mostrar_registro_auditoria(),
                ink=True,
            )
            controls.append(
                ft.Column(
                    [ft.Row([btn_usr, btn_aud], spacing=6)],
                    spacing=6,
                    tight=True,
                )
            )
            controls.append(ft.Container(height=4))
        else:
            btn_entrada = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=14, color=ft.Colors.GREEN_600),
                        ft.Text("Entrada", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
                expand=True,
                height=32,
                border_radius=7,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600)),
                tooltip="⚡ Entrada Rápida express por escaneo (Devolución, Mov. Interno...)",
                on_click=lambda _: mostrar_dialogo_ingreso_rapido(interfaz),
                ink=True,
            )

            btn_salida = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, size=14, color=ft.Colors.AMBER_700),
                        ft.Text("Salida", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=4,
                ),
                expand=True,
                height=32,
                border_radius=7,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_700)),
                tooltip="⚡ Salida Rápida express por escaneo (Rotura, Merma, Muestras...)",
                on_click=lambda _: mostrar_dialogo_salida_rapida(interfaz),
                ink=True,
            )

            filas_botones = [ft.Row([btn_entrada, btn_salida], spacing=6)]

            if rol == "operador":
                btn_pedido = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.POST_ADD, size=14, color=ft.Colors.BLUE_500),
                            ft.Text("Cargar Pedido", size=10, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    expand=True,
                    height=32,
                    border_radius=7,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
                    tooltip="⚡ Cargar y escanear remito / armar nuevo pedido",
                    on_click=lambda _: interfaz.mostrar_crear_pedido(),
                    ink=True,
                )
                btn_meli = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.STOREFRONT, size=14, color=ft.Colors.AMBER_500),
                            ft.Text("Mercado Libre", size=10, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    expand=True,
                    height=32,
                    border_radius=7,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_500),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_500)),
                    tooltip="⚡ Descontar y escanear etiquetas de Mercado Libre",
                    on_click=lambda _: interfaz.mostrar_descuento_mercado_libre(),
                    ink=True,
                )
                filas_botones.append(ft.Row([btn_pedido, btn_meli], spacing=6))
            elif rol == "picker":
                btn_meli = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.STOREFRONT, size=14, color=ft.Colors.AMBER_500),
                            ft.Text("Descontar ML", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    expand=True,
                    height=32,
                    border_radius=7,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_500),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_500)),
                    tooltip="⚡ Descontar y escanear etiquetas de Mercado Libre",
                    on_click=lambda _: interfaz.mostrar_descuento_mercado_libre(),
                    ink=True,
                )
                filas_botones.append(ft.Row([btn_meli], spacing=6))
            elif rol == "administrador":
                btn_prod = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INVENTORY_2, size=14, color=ft.Colors.BLUE_500),
                            ft.Text("Productos", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    expand=True,
                    height=32,
                    border_radius=7,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
                    tooltip="⚡ Gestión del catálogo maestro de productos",
                    on_click=lambda _: interfaz.mostrar_gestion_productos(),
                    ink=True,
                )
                filas_botones.append(ft.Row([btn_prod], spacing=6))

            controls.append(
                ft.Column(
                    filas_botones,
                    spacing=6,
                    tight=True,
                )
            )
            controls.append(ft.Container(height=4))

    prefs = obtener_preferencias_usuario(username)
    seccion_abierta_pref = prefs.get("seccion_abierta")
    seccion_por_defecto = _obtener_seccion_predeterminada(rol)

    # Si el usuario tiene una sección preferida guardada, abrir esa; si no, abrir la predeterminada del rol
    seccion_a_abrir = seccion_abierta_pref if seccion_abierta_pref is not None else seccion_por_defecto

    # Conteo dinámico de pedidos pendientes para el badge de CONTROL Y CIERRE
    conteo_cierre = 0
    if hasattr(interfaz, "order_store") and interfaz.order_store:
        try:
            conteo_dict = interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo()
            conteo_cierre = int(conteo_dict.get("total", 0))
        except Exception:
            conteo_cierre = 0

    lista_tiles: list[ft.ExpansionTile] = []

    def _crear_callback_acordeon(tile_obj: ft.ExpansionTile, nombre_sec: str) -> Callable[[Any], None]:
        def al_cambiar(e: Any) -> None:
            esta_abierto = str(e.data).lower() in ("true", "1")
            if esta_abierto:
                for t in lista_tiles:
                    if t is not tile_obj:
                        t.expanded = False
                guardar_preferencia_usuario(username, "seccion_abierta", nombre_sec)
            else:
                guardar_preferencia_usuario(username, "seccion_abierta", "")
            if hasattr(interfaz, "page") and interfaz.page:
                try:
                    interfaz.page.update()
                except Exception:
                    pass
        return al_cambiar

    for sec in secciones:
        esta_expandido = (sec.titulo == seccion_a_abrir)
        sec_buttons: list[ft.Control] = []

        for texto, icono, accion in sec.items:
            if sec.es_control_cierre and texto == "Cierre de Jornada":
                sec_buttons.append(_crear_boton_cierre_jornada(interfaz, ancho=218))
            else:
                btn = interfaz.boton(texto, icono, accion)
                btn.icon = None
                btn.bgcolor = ft.Colors.TRANSPARENT
                btn.color = interfaz.texto
                btn.elevation = 0
                btn.height = 36
                btn.style = ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=6),
                    overlay_color=ft.Colors.with_opacity(0.08, interfaz.texto),
                    alignment=ft.Alignment.CENTER_LEFT,
                    padding=ft.Padding.only(left=16, right=8),
                )
                sec_buttons.append(btn)

        # Encabezado del título con punto rojo indicador si hay pendientes
        tiene_pendientes, tooltip_pendientes = verificar_pendientes_categoria(interfaz, sec.titulo)
        punto_rojo = ft.Container(
            width=7,
            height=7,
            border_radius=4,
            bgcolor=ROJO,
            tooltip=tooltip_pendientes if tiene_pendientes else None,
            visible=tiene_pendientes,
        )
        if not isinstance(getattr(interfaz, "puntos_pendientes_sidebar", None), dict):
            interfaz.puntos_pendientes_sidebar = {}
        if isinstance(interfaz.puntos_pendientes_sidebar, dict):
            interfaz.puntos_pendientes_sidebar[sec.titulo] = punto_rojo

        if sec.es_control_cierre:
            interfaz.badge_seccion_cierre = punto_rojo

        titulo_tile = ft.Row(
            [
                ft.Text(sec.titulo, size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                punto_rojo,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        titulo_tile.value = sec.titulo

        tile = ft.ExpansionTile(
            title=titulo_tile,
            leading=ft.Icon(sec.icono, size=18, color=ROJO),
            controls=sec_buttons,
            controls_padding=ft.Padding.only(left=2, right=2, top=4, bottom=6),
            tile_padding=ft.Padding.symmetric(horizontal=4, vertical=0),
            maintain_state=True,
            expanded=esta_expandido,
            dense=True,
            shape=ft.RoundedRectangleBorder(radius=8, side=ft.BorderSide(0, ft.Colors.TRANSPARENT)),
            collapsed_shape=ft.RoundedRectangleBorder(radius=8, side=ft.BorderSide(0, ft.Colors.TRANSPARENT)),
        )
        tile.on_change = _crear_callback_acordeon(tile, sec.titulo)
        lista_tiles.append(tile)
        controls.append(tile)

    controls.extend(
        [
            ft.Container(height=8),
            ft.Row(
                [
                    ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_600, size=10),
                    ft.Text("Agente local activo", size=12, color=interfaz.secundario),
                ],
                spacing=8,
            ),
        ]
    )
    return controls




__all__ = [
    "SeccionMenu",
    "obtener_secciones_rol",
    "_obtener_seccion_predeterminada",
    "verificar_pendientes_categoria",
    "actualizar_puntos_pendientes_sidebar",
    "_crear_boton_cierre_jornada",
    "construir_sidebar_controls",
    "construir_sidebar_horizontal_controls",
]
