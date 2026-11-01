"""Diálogo y banner de alerta para productos en quiebre de stock."""

from typing import Any
import flet as ft
from ..theme import ROJO


def actualizar_alerta_quiebre(interfaz: Any, criticos: list | None = None) -> None:
    """Actualiza y renderiza el banner de alerta de quiebre de stock en el dashboard."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "administrador":
        interfaz.banner_alerta_quiebre.visible = False
        return

    if criticos is None:
        try:
            from ...stock_manager import StockManager
            sm = StockManager(interfaz.menu.ruta_excel_base)
            criticos = sm.obtener_analisis_reposicion(solo_criticos=True)
        except Exception:
            criticos = []

    if not criticos:
        interfaz.banner_alerta_quiebre.visible = False
        return

    agotados = sum(1 for p in criticos if int(p["stock"]) <= 0)
    quiebres = len(criticos) - agotados

    if not hasattr(interfaz, "_quiebres_telegram_notificados"):
        interfaz._quiebres_telegram_notificados = set()

    for c in criticos:
        item = dict(c) if hasattr(c, "keys") else (c if isinstance(c, dict) else {})
        cod_c = str(item.get("code", "")).strip()
        if cod_c and cod_c not in interfaz._quiebres_telegram_notificados:
            interfaz._quiebres_telegram_notificados.add(cod_c)
            try:
                from ...telegram_notifier import notificar_quiebre_stock_telegram
                notificar_quiebre_stock_telegram(
                    codigo=cod_c,
                    nombre=str(item.get("name", "")).strip(),
                    stock_actual=int(item.get("stock", 0)),
                    stock_minimo=int(item.get("stock_minimo", item.get("min_stock", 0))),
                )
            except Exception:
                pass

    interfaz.banner_alerta_quiebre.visible = True
    interfaz.banner_alerta_quiebre.bgcolor = (
        ft.Colors.RED_900 if interfaz.modo_oscuro else ft.Colors.RED_50
    )
    interfaz.banner_alerta_quiebre.border = ft.Border.all(
        1.5, ft.Colors.RED_400 if interfaz.modo_oscuro else ft.Colors.RED_700
    )
    interfaz.banner_alerta_quiebre.border_radius = 12
    interfaz.banner_alerta_quiebre.padding = ft.Padding(16, 12, 16, 12)
    es_movil = interfaz.es_pantalla_movil

    bloque_info_quiebre = ft.Row(
        [
            ft.Icon(
                ft.Icons.WARNING_AMBER_ROUNDED,
                color=ft.Colors.RED_400 if interfaz.modo_oscuro else ft.Colors.RED_700,
                size=28,
            ),
            ft.Column(
                [
                    ft.Text(
                        f"ALERTA DE QUIEBRE DE STOCK ({len(criticos)} producto{'s' if len(criticos) != 1 else ''} en riesgo)",
                        weight=ft.FontWeight.BOLD,
                        size=13,
                        color=ft.Colors.RED_300 if interfaz.modo_oscuro else ft.Colors.RED_800,
                    ),
                    ft.Text(
                        f"{agotados} sin stock o negativo · {quiebres} en stock mínimo de seguridad",
                        size=11,
                        color=interfaz.texto,
                    ),
                ],
                spacing=2,
                expand=True,
            ),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        expand=not es_movil,
    )
    bloque_botones_quiebre = ft.Row(
        [
            ft.Button(
                "Ver detalle",
                icon=ft.Icons.VISIBILITY,
                on_click=lambda _e, items=criticos: interfaz.mostrar_detalle_quiebre(items),
                bgcolor=ft.Colors.TRANSPARENT,
                color=ft.Colors.RED_300 if interfaz.modo_oscuro else ft.Colors.RED_800,
            ),
            ft.Button(
                "Generar pedido fábrica",
                icon=ft.Icons.FILE_DOWNLOAD,
                on_click=interfaz.generar_pedido_fabrica,
                bgcolor=ft.Colors.TRANSPARENT,
                color=ft.Colors.RED_300 if interfaz.modo_oscuro else ft.Colors.RED_800,
            ),
            ft.Button(
                "Cargar pedido fábrica",
                icon=ft.Icons.INVENTORY_2,
                on_click=interfaz.mostrar_ingreso_fabrica,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
            ),
        ],
        spacing=6,
        wrap=es_movil,
    )
    interfaz.banner_alerta_quiebre.content = (
        ft.Column(
            [bloque_info_quiebre, bloque_botones_quiebre],
            spacing=10,
            tight=True,
        )
        if es_movil
        else ft.Row(
            [bloque_info_quiebre, bloque_botones_quiebre],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )


def mostrar_detalle_quiebre(interfaz: Any, criticos: list) -> None:
    """Muestra el modal detallado de productos con stock en quiebre o agotados."""
    if not interfaz.exigir_roles("administrador"):
        return

    lista = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=360)
    for p in criticos:
        cod = str(p["code"])
        nom = str(p["name"])
        stk = int(p["stock"])
        s_min = int(p["stock_minimo"])
        pedir = int(p["cantidad_sugerida_pedir"])

        if stk <= 0:
            tag_txt = "AGOTADO"
            tag_color = ft.Colors.RED_400
        else:
            tag_txt = f"QUIEBRE (Mín: {s_min})"
            tag_color = ft.Colors.AMBER_400

        lista.controls.append(
            ft.Container(
                padding=8,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                content=ft.Row(
                    [
                        ft.Text(cod, width=70, weight=ft.FontWeight.BOLD, size=12),
                        ft.Text(nom, expand=True, size=12),
                        ft.Text(
                            f"{stk} un.",
                            width=65,
                            color=tag_color,
                            weight=ft.FontWeight.BOLD,
                            size=12,
                        ),
                        ft.Text(
                            tag_txt,
                            width=120,
                            color=tag_color,
                            size=11,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            f"Pedir: +{pedir} un.",
                            width=100,
                            color=ft.Colors.BLUE_300 if interfaz.modo_oscuro else ft.Colors.BLUE_700,
                            size=11,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    if not criticos:
        lista.controls.append(
            ft.Text("No hay productos en quiebre de stock.", color=interfaz.secundario)
        )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_400, size=24),
                ft.Text(f"Productos en quiebre de stock ({len(criticos)})"),
            ],
            spacing=8,
        ),
        content=ft.Column(
            [
                ft.Text(
                    "Productos cuyo stock actual es menor o igual al mínimo de seguridad establecido:",
                    size=12,
                    color=interfaz.secundario,
                ),
                ft.Divider(height=1),
                lista,
            ],
            tight=True,
            width=680,
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo(
                "Generar pedido Excel",
                lambda _e: (interfaz.page.pop_dialog(), interfaz.generar_pedido_fabrica()),
            ),
            interfaz.boton_dialogo(
                "Cargar pedido fábrica",
                lambda _e: (interfaz.page.pop_dialog(), interfaz.mostrar_ingreso_fabrica()),
            ),
        ],
    )
    interfaz.page.show_dialog(dialogo)
