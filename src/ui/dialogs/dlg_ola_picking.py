"""Diálogo modal interactivo para la visualización y ejecución de Ola de Picking (Wave Picking)."""

from __future__ import annotations

from typing import Any
import flet as ft

from ..design import par_accion_tarjeta
from ..theme import ROJO
from ...orders.picking_wave import consolidar_ola_picking, crear_y_reservar_ola_picking


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

        stock_fis = int(it.get("stock_fisico", 0) or 0)
        stock_res = int(it.get("stock_reservado", 0) or 0)
        stock_disp = int(it.get("stock_disponible", 0) or 0)
        sub_controles: list[ft.Control] = [
            ft.Text(
                f"[{it['codigo']}] {it['descripcion']}",
                weight=ft.FontWeight.BOLD,
                size=12,
                color=interfaz.texto,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                resumen_pedidos_str,
                size=10,
                color=interfaz.secundario,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ]
        if stock_fis > 0 or stock_res > 0 or it.get("lote_sugerido"):
            disp_color = ft.Colors.RED_400 if stock_disp < int(it["total_unidades"]) else ft.Colors.TEAL_400
            partes_disp = [f"Disp: {stock_disp} u. (Fís: {stock_fis} · Res: {stock_res})"]
            if it.get("lote_sugerido"):
                fv_txt = f" vto {it['vencimiento_sugerido']}" if it.get("vencimiento_sugerido") else ""
                partes_disp.append(f"FEFO: {it['lote_sugerido']}{fv_txt}")
            sub_controles.append(
                ft.Text(
                    " | ".join(partes_disp),
                    size=10,
                    color=disp_color,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )

        info_item = ft.Row(
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
                    sub_controles,
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=10,
            expand=True,
        )
        badge_total = ft.Container(
            content=ft.Text(f"x{it['total_unidades']}", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            bgcolor=ROJO,
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=12,
        )
        fila_item = ft.Container(
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            content=par_accion_tarjeta(interfaz, info_item, badge_total, umbral=480.0, spacing=8),
        )
        lista_controles.append(fila_item)

    acciones: list[ft.Control] = []
    if product_store is not None and hasattr(product_store, "reservar_stock"):
        def _reservar_ola(_e: ft.Event) -> None:
            usuario_actual = str(
                getattr(interfaz, "usuario_actual", "")
                or getattr(interfaz, "username", "")
                or "operario"
            ).strip()
            try:
                res = crear_y_reservar_ola_picking(
                    order_store,
                    pedidos_target,
                    product_store,
                    usuario=usuario_actual,
                )
                total_res = int(res.get("reserva", {}).get("total_unidades_reservadas", 0))
                interfaz.notificar(
                    f"Stock reservado para ola {res['referencia_id']} ({total_res} u.)."
                )
                interfaz.page.pop_dialog()
            except Exception as exc:
                interfaz.notificar(f"No se pudo reservar la ola: {exc}")

        acciones.append(
            ft.Button("Reservar Stock de la Ola", on_click=_reservar_ola)
        )
    acciones.append(ft.TextButton("Cerrar", on_click=lambda _: interfaz.page.pop_dialog()))

    ancho_dlg = interfaz.ancho_adaptable(540) if hasattr(interfaz, "ancho_adaptable") else 540
    alto_dlg = interfaz.alto_adaptable(380) if hasattr(interfaz, "alto_adaptable") else 380
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WAVES, color=ft.Colors.BLUE_400),
                ft.Column(
                    [
                        ft.Text("Ola de Picking Consolidada (Wave Picking)", size=16, weight=ft.FontWeight.BOLD, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{total_pedidos} pedidos agrupados · {len(items_ola)} SKUs · {total_unidades} unidades totales", size=11, color=interfaz.secundario, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=ancho_dlg,
            height=alto_dlg,
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
        actions=acciones,
    )
    interfaz.page.show_dialog(dialogo)
