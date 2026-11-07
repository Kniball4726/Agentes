"""Construcción de la barra superior horizontal de navegación de StockAgent."""

from pathlib import Path
from typing import Any, Callable
import flet as ft

from ..theme import ROJO
from .sidebar_sections import (
    SeccionMenu,
    obtener_secciones_rol,
    _crear_boton_cierre_jornada,
)
from ..dialogs.dlg_movimientos_rapidos import (
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_salida_rapida,
)

def construir_sidebar_horizontal_controls(interfaz: Any) -> list[ft.Control]:
    """Genera la lista de controles para el panel de navegación horizontal con menús desplegables (MenuBar)."""
    assert interfaz.usuario_actual is not None
    logo_path = Path(__file__).resolve().parent.parent.parent / "img" / "ultratech.png"
    logo_bytes = logo_path.read_bytes() if logo_path.exists() else b""

    secciones = obtener_secciones_rol(interfaz)
    rol = interfaz.usuario_actual.role

    # Conteo dinámico de pedidos pendientes
    conteo_cierre = 0
    if hasattr(interfaz, "order_store") and interfaz.order_store:
        try:
            conteo_dict = interfaz.order_store.contar_pedidos_pendientes_cierre_por_tipo()
            conteo_cierre = int(conteo_dict.get("total", 0))
        except Exception:
            conteo_cierre = 0

    menu_bar_controls: list[ft.Control] = []

    for sec in secciones:
        menu_items: list[ft.Control] = []
        for texto, icono, accion in sec.items:
            if sec.es_control_cierre and texto == "Cierre de Jornada":
                btn_item = ft.MenuItemButton(
                    content=ft.Text(f"Cierre de Jornada ({conteo_cierre})" if conteo_cierre > 0 else "Cierre de Jornada"),
                    on_click=accion,
                )
                menu_items.append(btn_item)
            else:
                menu_items.append(
                    ft.MenuItemButton(
                        content=ft.Text(texto),
                        on_click=accion,
                    )
                )

        # Encabezado con punto rojo indicador si hay pendientes
        tiene_pendientes_h, tooltip_h = verificar_pendientes_categoria(interfaz, sec.titulo)
        punto_rojo_h = ft.Container(
            width=7,
            height=7,
            border_radius=4,
            bgcolor=ROJO,
            tooltip=tooltip_h if tiene_pendientes_h else None,
            visible=tiene_pendientes_h,
        )
        if not isinstance(getattr(interfaz, "puntos_pendientes_horizontal", None), dict):
            interfaz.puntos_pendientes_horizontal = {}
        if isinstance(interfaz.puntos_pendientes_horizontal, dict):
            interfaz.puntos_pendientes_horizontal[sec.titulo] = punto_rojo_h

        if sec.es_control_cierre:
            interfaz.badge_h_seccion_cierre = punto_rojo_h

        header_content = ft.Row(
            [
                ft.Text(sec.titulo, size=12, weight=ft.FontWeight.W_600),
                punto_rojo_h,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        header_content.value = sec.titulo

        submenu = ft.SubmenuButton(
            content=header_content,
            leading=ft.Icon(sec.icono, size=16, color=ROJO),
            controls=menu_items,
        )
        menu_bar_controls.append(submenu)

    menu_bar = ft.MenuBar(
        style=ft.MenuStyle(
            bgcolor=ft.Colors.TRANSPARENT,
            elevation=0,
            padding=ft.Padding.symmetric(horizontal=4, vertical=2),
        ),
        controls=menu_bar_controls,
    )

    controls: list[ft.Control] = [
        ft.Row(
            [
                ft.Container(
                    width=28,
                    height=28,
                    border_radius=8,
                    bgcolor=ft.Colors.GREY_900 if interfaz.modo_oscuro else ft.Colors.RED_50,
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(0.18, ft.Colors.WHITE) if interfaz.modo_oscuro else ft.Colors.RED_100,
                    ),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Image(src=logo_bytes, width=28, height=28, fit=ft.BoxFit.CONTAIN),
                ),
                ft.Text("StockAgent", size=14, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ft.Container(
                    content=ft.Text(f"{rol}".upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ROJO,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        ft.VerticalDivider(width=16, color=interfaz.borde),
        ft.IconButton(
            icon=ft.Icons.SEARCH,
            icon_size=18,
            icon_color=interfaz.secundario,
            tooltip="Búsqueda rápida (Ctrl + K / F2)",
            on_click=lambda _: interfaz.mostrar_command_palette(),
        ),
        ft.VerticalDivider(width=8, color=interfaz.borde),
    ]

    # Barra horizontal de accesos rápidos:
    # - Master: Usuarios y Auditoría
    # - Picker: Entrada, Salida y Mercado Libre
    # - Administrador: Solo Entrada y Salida (Ingreso y Egreso)
    # - Operador: Entrada, Salida, Cargar Pedido y Mercado Libre
    if rol in ("operador", "administrador", "picker", "master"):
        if rol == "master":
            btn_usr_h = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.MANAGE_ACCOUNTS, size=14, color=ft.Colors.BLUE_500),
                        ft.Text("Usuarios", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=30,
                padding=ft.Padding.symmetric(horizontal=8),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
                tooltip="⚡ Gestión y control de cuentas IAM",
                on_click=lambda _: interfaz.mostrar_gestion_usuarios(),
                ink=True,
            )
            btn_aud_h = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.SECURITY, size=14, color=ROJO),
                        ft.Text("Auditoría", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=30,
                padding=ft.Padding.symmetric(horizontal=8),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.08, ROJO),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ROJO)),
                tooltip="⚡ Registro de eventos y trazabilidad forense",
                on_click=lambda _: interfaz.mostrar_registro_auditoria(),
                ink=True,
            )
            controls.extend([
                btn_usr_h,
                btn_aud_h,
                ft.VerticalDivider(width=8, color=interfaz.borde),
            ])
        else:
            btn_ent_h = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=14, color=ft.Colors.GREEN_600),
                        ft.Text("Entrada", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=30,
                padding=ft.Padding.symmetric(horizontal=8),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600)),
                tooltip="⚡ Entrada Rápida express (Devolución, Mov. Interno...)",
                on_click=lambda _: mostrar_dialogo_ingreso_rapido(interfaz),
                ink=True,
            )
            btn_sal_h = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE, size=14, color=ft.Colors.AMBER_700),
                        ft.Text("Salida", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                height=30,
                padding=ft.Padding.symmetric(horizontal=8),
                border_radius=6,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_700)),
                tooltip="⚡ Salida Rápida express (Rotura, Merma, Bajas...)",
                on_click=lambda _: mostrar_dialogo_salida_rapida(interfaz),
                ink=True,
            )

            botones_h = [btn_ent_h, btn_sal_h]

            if rol == "operador":
                btn_ped_h = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.POST_ADD, size=14, color=ft.Colors.BLUE_500),
                            ft.Text("Cargar Pedido", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    height=30,
                    padding=ft.Padding.symmetric(horizontal=8),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
                    tooltip="⚡ Cargar / Armar Pedido",
                    on_click=lambda _: interfaz.mostrar_crear_pedido(),
                    ink=True,
                )
                btn_meli_h = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.STOREFRONT, size=14, color=ft.Colors.AMBER_500),
                            ft.Text("Mercado Libre", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    height=30,
                    padding=ft.Padding.symmetric(horizontal=8),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_500),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_500)),
                    tooltip="⚡ Descontar Mercado Libre",
                    on_click=lambda _: interfaz.mostrar_descuento_mercado_libre(),
                    ink=True,
                )
                botones_h.extend([btn_ped_h, btn_meli_h])
            elif rol == "picker":
                btn_meli_h = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.STOREFRONT, size=14, color=ft.Colors.AMBER_500),
                            ft.Text("Mercado Libre", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    height=30,
                    padding=ft.Padding.symmetric(horizontal=8),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_500),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.AMBER_500)),
                    tooltip="⚡ Descontar Mercado Libre",
                    on_click=lambda _: interfaz.mostrar_descuento_mercado_libre(),
                    ink=True,
                )
                botones_h.append(btn_meli_h)
            elif rol == "administrador":
                btn_prod_h = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INVENTORY_2, size=14, color=ft.Colors.BLUE_500),
                            ft.Text("Productos", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    height=30,
                    padding=ft.Padding.symmetric(horizontal=8),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500)),
                    tooltip="⚡ Gestionar Productos",
                    on_click=lambda _: interfaz.mostrar_gestion_productos(),
                    ink=True,
                )
                botones_h.append(btn_prod_h)

            botones_h.append(ft.VerticalDivider(width=8, color=interfaz.borde))
            controls.extend(botones_h)

    controls.append(menu_bar)

    # Para operador, agregar también botón directo visible en la barra horizontal para Cierre rápido
    if rol == "operador":
        btn_cierre_directo = _crear_boton_cierre_jornada(interfaz, ancho=None)
        btn_cierre_directo.height = 34
        controls.extend([
            ft.VerticalDivider(width=12, color=interfaz.borde),
            btn_cierre_directo,
        ])

    return controls

