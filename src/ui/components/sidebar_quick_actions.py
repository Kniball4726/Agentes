"""Accesos rápidos por rol mostrados en la parte superior de la barra lateral."""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from ..dialogs.dlg_movimientos_rapidos import (
    mostrar_dialogo_ingreso_rapido,
    mostrar_dialogo_salida_rapida,
)
from ..theme import ROJO


def _crear_boton_rapido_sidebar(
    *,
    texto: str,
    icono: ft.IconData,
    color_icono: str,
    color_texto: str,
    bgcolor: str,
    tooltip: str,
    on_click: Callable[[Any], Any],
    border_color: str | None = None,
    height: int = 32,
    text_size: int = 11,
    icon_size: int = 14,
    spacing: int = 4,
    shadow: ft.BoxShadow | None = None,
) -> ft.Container:
    """Construye un botón uniforme de acceso rápido para el menú lateral."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icono, size=icon_size, color=color_icono),
                ft.Text(texto, size=text_size, weight=ft.FontWeight.BOLD, color=color_texto),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=spacing,
        ),
        expand=True,
        height=height,
        border_radius=7 if height < 40 else 8,
        bgcolor=bgcolor,
        border=ft.Border.all(1, border_color) if border_color else None,
        tooltip=tooltip,
        on_click=on_click,
        ink=True,
        shadow=shadow,
    )


def _construir_accesos_master(interfaz: Any) -> list[ft.Control]:
    btn_usr = _crear_boton_rapido_sidebar(
        texto="Usuarios",
        icono=ft.Icons.MANAGE_ACCOUNTS,
        color_icono=ft.Colors.BLUE_500,
        color_texto=interfaz.texto,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_500),
        border_color=ft.Colors.with_opacity(0.35, ft.Colors.BLUE_500),
        tooltip="⚡ Gestión y control de cuentas IAM",
        on_click=lambda _: interfaz.mostrar_gestion_usuarios(),
    )
    btn_aud = _crear_boton_rapido_sidebar(
        texto="Auditoría",
        icono=ft.Icons.SECURITY,
        color_icono=ROJO,
        color_texto=interfaz.texto,
        bgcolor=ft.Colors.with_opacity(0.08, ROJO),
        border_color=ft.Colors.with_opacity(0.35, ROJO),
        tooltip="⚡ Registro de eventos y trazabilidad forense",
        on_click=lambda _: interfaz.mostrar_registro_auditoria(),
    )
    btn_env = _crear_boton_rapido_sidebar(
        texto="Ambientes",
        icono=ft.Icons.TUNE,
        color_icono=ft.Colors.AMBER_400,
        color_texto=interfaz.texto,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_400),
        border_color=ft.Colors.with_opacity(0.35, ft.Colors.AMBER_400),
        tooltip="⚡ Cambiar entre Producción y QA / Pruebas",
        on_click=lambda _: interfaz.mostrar_gestion_ambientes(),
    )
    return [ft.Row([btn_usr, btn_aud], spacing=6), ft.Row([btn_env])]


def _construir_accesos_operador(
    interfaz: Any,
    btn_entrada: ft.Container,
    btn_salida: ft.Container,
) -> list[ft.Control]:
    btn_pedido = _crear_boton_rapido_sidebar(
        texto="Cargar Pedido",
        icono=ft.Icons.POST_ADD,
        color_icono=ft.Colors.WHITE,
        color_texto=ft.Colors.WHITE,
        bgcolor=ROJO,
        height=48,
        text_size=14,
        icon_size=24,
        spacing=8,
        tooltip="⚡ Cargar y escanear remito / armar nuevo pedido (Proceso Principal)",
        on_click=lambda _: interfaz.mostrar_crear_pedido(),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=6,
            color=ft.Colors.with_opacity(0.35, ROJO),
            offset=ft.Offset(0, 2),
        ),
    )
    return [
        ft.Row([btn_pedido]),
        ft.Row([btn_entrada, btn_salida], spacing=6),
    ]


def _construir_accesos_picker(
    interfaz: Any,
    btn_entrada: ft.Container,
    btn_salida: ft.Container,
) -> list[ft.Control]:
    especificos = [
        ("Descontar ML", ft.Icons.STOREFRONT, "⚡ Descontar y escanear etiquetas de Mercado Libre", lambda _: interfaz.mostrar_descuento_mercado_libre()),
        ("Full", ft.Icons.LOCAL_SHIPPING, "⚡ Preparación guiada de Mercado Envíos Full (escaneo y validación en tiempo real)", lambda _: interfaz.mostrar_picking_guiado_full()),
        ("Ingreso de Fábrica", ft.Icons.INVENTORY_2, "⚡ Control de recepción de fábrica por escaneo (validación en tiempo real)", lambda _: interfaz.mostrar_control_ingreso_fabrica()),
    ]
    filas: list[ft.Control] = [
        ft.Row([
            _crear_boton_rapido_sidebar(
                texto=txt,
                icono=ico,
                color_icono=ft.Colors.WHITE,
                color_texto=ft.Colors.WHITE,
                bgcolor=ROJO,
                tooltip=tip,
                on_click=cb,
            )
        ])
        for txt, ico, tip, cb in especificos
    ]
    filas.append(ft.Row([btn_entrada, btn_salida], spacing=6))
    return filas


def _construir_accesos_admin(
    interfaz: Any,
    btn_entrada: ft.Container,
    btn_salida: ft.Container,
) -> list[ft.Control]:
    def _opt(nombre_metodo: str) -> Callable[[Any], None]:
        return lambda _: getattr(interfaz, nombre_metodo)() if hasattr(interfaz, nombre_metodo) else None

    acciones = [
        ("Gestionar inventario", ft.Icons.INVENTORY, "⚡ Consulta interactiva de existencias y niveles de stock en tiempo real", _opt("mostrar_ver_stock")),
        ("Planificar ingreso de fábrica", ft.Icons.ADD_TASK, "⚡ Planificar y monitorear ingreso de remitos de fábrica", _opt("mostrar_planificar_ingreso_fabrica")),
        ("Planificar mercado full", ft.Icons.LOCAL_SHIPPING, "⚡ Planificar y monitorear envíos a Mercado Envíos Full", _opt("mostrar_planificar_full")),
        ("Gestionar productos", ft.Icons.INVENTORY_2, "⚡ Gestión del catálogo maestro de productos", _opt("mostrar_gestion_productos")),
        ("Ajuste de inventario", ft.Icons.TUNE, "⚡ Escanear mercadería o registrar ajuste de stock", _opt("mostrar_ingreso_fabrica")),
        ("Generar Pedido", ft.Icons.FACT_CHECK, "⚡ Calcular sugerido y generar planilla Excel de reposición a fábrica", _opt("generar_pedido_fabrica")),
        ("Sincronizar", ft.Icons.SYNC, "⚡ Sincronizar catálogo SQLite con Productos.xlsx", _opt("sincronizar_catalogo_excel")),
    ]
    filas: list[ft.Control] = [
        ft.Row([
            _crear_boton_rapido_sidebar(
                texto=txt,
                icono=ico,
                color_icono=ft.Colors.WHITE,
                color_texto=ft.Colors.WHITE,
                bgcolor=ROJO,
                tooltip=tip,
                on_click=cb,
            )
        ])
        for txt, ico, tip, cb in acciones
    ]
    filas.append(ft.Row([btn_entrada, btn_salida], spacing=6))
    return filas


def construir_acceso_rapido_sidebar(interfaz: Any, rol: str) -> ft.Control | None:
    """Devuelve la botonera de acceso rápido acorde al rol activo o None si no aplica."""
    if rol not in ("operador", "administrador", "picker", "master"):
        return None
    if rol == "master":
        return ft.Column(_construir_accesos_master(interfaz), spacing=6, tight=True)

    btn_entrada = _crear_boton_rapido_sidebar(
        texto="Entrada",
        icono=ft.Icons.ADD_CIRCLE_OUTLINE,
        color_icono=ft.Colors.GREEN_600,
        color_texto=interfaz.texto,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN_600),
        border_color=ft.Colors.with_opacity(0.35, ft.Colors.GREEN_600),
        tooltip="⚡ Entrada Rápida express por escaneo (Devolución, Mov. Interno...)",
        on_click=lambda _: mostrar_dialogo_ingreso_rapido(interfaz),
    )
    btn_salida = _crear_boton_rapido_sidebar(
        texto="Salida",
        icono=ft.Icons.REMOVE_CIRCLE_OUTLINE,
        color_icono=ft.Colors.AMBER_700,
        color_texto=interfaz.texto,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER_700),
        border_color=ft.Colors.with_opacity(0.35, ft.Colors.AMBER_700),
        tooltip="⚡ Salida Rápida express por escaneo (Rotura, Merma, Muestras...)",
        on_click=lambda _: mostrar_dialogo_salida_rapida(interfaz),
    )

    if rol == "operador":
        filas = _construir_accesos_operador(interfaz, btn_entrada, btn_salida)
    elif rol == "picker":
        filas = _construir_accesos_picker(interfaz, btn_entrada, btn_salida)
    else:
        filas = _construir_accesos_admin(interfaz, btn_entrada, btn_salida)
    return ft.Column(filas, spacing=6, tight=True)
