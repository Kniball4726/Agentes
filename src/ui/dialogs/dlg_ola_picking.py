"""Diálogo modal interactivo para la visualización y ejecución de Ola de Picking (Wave Picking)."""

from __future__ import annotations

from typing import Any
import flet as ft

from ..theme import ROJO
from ...orders.picking_wave import consolidar_ola_picking


def mostrar_dialogo_ola_picking(
    interfaz: Any,
    pedidos: list[Any] | None = None,
) -> None:
    """Abre el diálogo de Ola de Picking consolidada por pasillos/estanterías."""
    if not interfaz.exigir_roles("picker", "operador", "administrador"):
        return

    order_store = getattr(interfaz, "order_store", None)
    if order_store is None:
        interfaz.notificar("El módulo de pedidos no está inicializado.")
        return

    pedidos_target = pedidos
    if pedidos_target is None:
        try:
            pedidos_target = order_store.listar_pedidos_pendientes_cierre()
        except Exception:
            pedidos_target = []

    if not pedidos_target:
        interfaz.notificar("No hay pedidos activos para agrupar en ola de picking.")
        return

    product_store = None
    if hasattr(interfaz, "stock_manager") and hasattr(interfaz.stock_manager, "product_store"):
        product_store = interfaz.stock_manager.product_store

    items_ola = consolidar_ola_picking(order_store, pedidos_target, product_store=product_store)

    if not items_ola:
        interfaz.notificar("Los pedidos seleccionados no contienen artículos para recolectar.")
        return

    total_unidades = sum(it["total_unidades"] for it in items_ola)
    total_pedidos = len(pedidos_target)

    lista_controles: list[ft.Control] = []
    for it in items_ola:
        ubic_txt = it["ubicacion"] or "Sin asignar"
        tiene_ubic = bool(it["ubicacion"])

        resumen_pedidos_str = " · ".join(
            f"#{p['nota_pedido']} ({p['cantidad']} u.)" for p in it["pedidos"][:3]
        )
        if len(it["pedidos"]) > 3:
            resumen_pedidos_str += f" (+{len(it['pedidos']) - 3} pedidos más)"

        fila_item = ft.Container(
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(
                                    ubic_txt,
                                    size=10,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE if tiene_ubic else ft.Colors.BLUE_GREY_200,
                                ),
                                bgcolor=ft.Colors.TEAL_700 if tiene_ubic else ft.Colors.BLUE_GREY_800,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                border_radius=6,
                            ),
                            ft.Column(
                                [
                                    ft.Text(f"[{it['codigo']}] {it['descripcion']}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                    ft.Text(resumen_pedidos_str, size=10, color=interfaz.secundario),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(f"x{it['total_unidades']}", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        bgcolor=ROJO,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=12,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        lista_controles.append(fila_item)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WAVES, color=ft.Colors.BLUE_400),
                ft.Column(
                    [
                        ft.Text("Ola de Picking Consolidada (Wave Picking)", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{total_pedidos} pedidos agrupados · {len(items_ola)} SKUs · {total_unidades} unidades totales", size=11, color=interfaz.secundario),
                    ],
                    spacing=2,
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=540,
            height=380,
            content=ft.Column(
                [
                    ft.Text(
                        "Ruta sugerida de recolección agrupada por ubicación física para minimizar el recorrido en galpón:",
                        size=11,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=8),
                    ft.Container(
                        content=ft.ListView(lista_controles, spacing=6),
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
        ),
        actions=[
            ft.TextButton("Cerrar", on_click=lambda _: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
