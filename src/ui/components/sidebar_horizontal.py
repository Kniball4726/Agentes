"""Construcción de la barra superior horizontal de navegación de StockAgent."""

from pathlib import Path
from typing import Any, Callable
import flet as ft

from ..theme import FUENTE_MENU, FUENTE_MENU_BOLD, FUENTE_MENU_SEMIBOLD, ROJO, estilo_texto_menu
from .sidebar_sections import (
    obtener_secciones_rol,
    verificar_pendientes_categoria,
    _crear_boton_cierre_jornada,
)
from ..dialogs.dlg_movimientos_rapidos import (
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_salida_rapida,
)

def _crear_pildora_horizontal(
    *,
    texto: str,
    icono: ft.IconData,
    color_icono: str,
    color_texto: str,
    bgcolor: str,
    tooltip: str,
    on_click: Callable[[Any], Any],
    border_color: str | None = None,
    height: int = 30,
    icon_size: int = 14,
    padding_h: int = 8,
    spacing: int = 4,
) -> ft.Container:
    """Construye un acceso rápido compacto en la barra horizontal usando la tipografía de menú."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icono, size=icon_size, color=color_icono),
                ft.Text(
                    texto,
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color=color_texto,
                    font_family=FUENTE_MENU_BOLD,
                ),
            ],
            spacing=spacing,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        height=height,
        padding=ft.Padding.symmetric(horizontal=padding_h),
        border_radius=6,
        bgcolor=bgcolor,
        border=ft.Border.all(1, border_color) if border_color else None,
        tooltip=tooltip,
        on_click=on_click,
        ink=True,
    )


def construir_sidebar_horizontal_controls(interfaz: Any) -> list[ft.Control]:
    """Genera la lista de controles para el panel de navegación horizontal con menús desplegables (MenuBar)."""
    if interfaz.usuario_actual is None:
        raise ValueError("No hay un usuario autenticado para construir la barra de navegación.")
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

    estilo_item_menu = ft.ButtonStyle(text_style=estilo_texto_menu())
    estilo_submenu = ft.ButtonStyle(text_style=estilo_texto_menu("semibold"))

    for sec in secciones:
        menu_items: list[ft.Control] = []
        for texto, _icono, accion in sec.items:
            etiqueta_item = (
                f"Cierre de Jornada ({conteo_cierre})" if conteo_cierre > 0 else "Cierre de Jornada"
            ) if (sec.es_control_cierre and texto == "Cierre de Jornada") else texto
            menu_items.append(
                ft.MenuItemButton(
                    content=ft.Text(etiqueta_item, font_family=FUENTE_MENU),
                    style=estilo_item_menu,
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
                ft.Text(
                    sec.titulo,
                    size=12,
                    weight=ft.FontWeight.W_600,
                    font_family=FUENTE_MENU_SEMIBOLD,
                ),
                punto_rojo_h,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        header_content.value = sec.titulo

        submenu = ft.SubmenuButton(
            content=header_content,
            leading=ft.Icon(sec.icono, size=16, color=ROJO),
            style=estilo_submenu,
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
                ft.Text(
                    "StockAgent",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=interfaz.texto,
                    font_family=FUENTE_MENU_BOLD,
                ),
                ft.Container(
                    content=ft.Text(
                        f"{rol}".upper(),
                        size=9,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                        font_family=FUENTE_MENU_BOLD,
                    ),
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
    # - Operador: Cargar Pedido, Entrada y Salida
    if rol == "despachador":
        btn_desp_h = _crear_pildora_horizontal(
            texto="Despacho",
            icono=ft.Icons.QR_CODE_SCANNER,
            color_icono=ft.Colors.WHITE,
            color_texto=ft.Colors.WHITE,
            bgcolor=ROJO,
            padding_h=10,
            spacing=5,
            icon_size=15,
            tooltip="⚡ Abrir módulo Despacho (Pistola QR / Manual)",
            on_click=lambda _: interfaz.mostrar_modulo_despacho(),
        )
        controls.extend([
            btn_desp_h,
            ft.VerticalDivider(width=8, color=interfaz.borde),
        ])
    elif rol in ("operador", "administrador", "picker", "master"):
        if rol == "master":
            btn_usr_h = _crear_pildora_horizontal(
                texto="Usuarios",
                icono=ft.Icons.MANAGE_ACCOUNTS,
                color_icono=ft.Colors.BLUE_500,
                color_texto=interfaz.texto,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
                border_color=ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500),
                tooltip="⚡ Gestión y control de cuentas IAM",
                on_click=lambda _: interfaz.mostrar_gestion_usuarios(),
            )
            btn_aud_h = _crear_pildora_horizontal(
                texto="Auditoría",
                icono=ft.Icons.SECURITY,
                color_icono=ROJO,
                color_texto=interfaz.texto,
                bgcolor=ft.Colors.with_opacity(0.08, ROJO),
                border_color=ft.Colors.with_opacity(0.35, ROJO),
                tooltip="⚡ Registro de eventos y trazabilidad forense",
                on_click=lambda _: interfaz.mostrar_registro_auditoria(),
            )
            controls.extend([
                btn_usr_h,
                btn_aud_h,
                ft.VerticalDivider(width=8, color=interfaz.borde),
            ])
        else:
            btn_ent_h = _crear_pildora_horizontal(
                texto="Entrada",
                icono=ft.Icons.ADD_CIRCLE_OUTLINE,
                color_icono=ft.Colors.GREEN_600,
                color_texto=interfaz.texto,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
                border_color=ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600),
                tooltip="⚡ Entrada Rápida express (Devolución, Mov. Interno...)",
                on_click=lambda _: mostrar_dialogo_ingreso_rapido(interfaz),
            )
            btn_sal_h = _crear_pildora_horizontal(
                texto="Salida",
                icono=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                color_icono=ft.Colors.AMBER_700,
                color_texto=interfaz.texto,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700),
                border_color=ft.Colors.with_opacity(0.35, ft.Colors.AMBER_700),
                tooltip="⚡ Salida Rápida express (Rotura, Merma, Bajas...)",
                on_click=lambda _: mostrar_dialogo_salida_rapida(interfaz),
            )

            botones_h = [btn_ent_h, btn_sal_h]

            if rol == "operador":
                btn_ped_h = _crear_pildora_horizontal(
                    texto="Cargar Pedido",
                    icono=ft.Icons.POST_ADD,
                    color_icono=ft.Colors.WHITE,
                    color_texto=ft.Colors.WHITE,
                    bgcolor=ROJO,
                    height=32,
                    icon_size=16,
                    padding_h=10,
                    spacing=6,
                    tooltip="⚡ Cargar / Armar Pedido (Proceso Principal)",
                    on_click=lambda _: interfaz.mostrar_crear_pedido(),
                )
                botones_h = [btn_ped_h, btn_ent_h, btn_sal_h]
            elif rol == "picker":
                btn_meli_h = _crear_pildora_horizontal(
                    texto="Mercado Libre",
                    icono=ft.Icons.STOREFRONT,
                    color_icono=ft.Colors.AMBER_500,
                    color_texto=interfaz.texto,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_500),
                    border_color=ft.Colors.with_opacity(0.35, ft.Colors.AMBER_500),
                    tooltip="⚡ Descontar Mercado Libre",
                    on_click=lambda _: interfaz.mostrar_descuento_mercado_libre(),
                )
                botones_h.append(btn_meli_h)
            elif rol == "administrador":
                def _opt(nombre_metodo: str) -> Callable[[Any], None]:
                    return lambda _: getattr(interfaz, nombre_metodo)() if hasattr(interfaz, nombre_metodo) else None

                acciones_admin_h = [
                    ("Gestionar inventario", ft.Icons.INVENTORY, "⚡ Consulta de existencias e inventario en tiempo real", "mostrar_ver_stock"),
                    ("Planificar ingreso de fábrica", ft.Icons.ADD_TASK, "⚡ Planificar ingreso de fábrica", "mostrar_planificar_ingreso_fabrica"),
                    ("Planificar mercado full", ft.Icons.LOCAL_SHIPPING, "⚡ Planificar mercado full", "mostrar_planificar_full"),
                    ("Gestionar productos", ft.Icons.INVENTORY_2, "⚡ Gestionar Productos", "mostrar_gestion_productos"),
                    ("Ajuste de inventario", ft.Icons.TUNE, "⚡ Escanear mercadería o registrar ajuste de stock", "mostrar_ingreso_fabrica"),
                    ("Generar Pedido", ft.Icons.FACT_CHECK, "⚡ Calcular y generar planilla de pedido a fábrica", "generar_pedido_fabrica"),
                    ("Sincronizar", ft.Icons.SYNC, "⚡ Sincronizar catálogo SQLite con Productos.xlsx", "sincronizar_catalogo_excel"),
                ]
                botones_h = [
                    _crear_pildora_horizontal(
                        texto=txt,
                        icono=ico,
                        color_icono=ft.Colors.WHITE,
                        color_texto=ft.Colors.WHITE,
                        bgcolor=ROJO,
                        tooltip=tip,
                        on_click=_opt(metodo),
                    )
                    for txt, ico, tip, metodo in acciones_admin_h
                ]
                botones_h.extend([btn_ent_h, btn_sal_h])

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

