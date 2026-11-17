"""Vista y renderizado de pedidos preparados del turno activo en el Dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any
import flet as ft
from ..theme import ROJO


def renderizar_pedidos_preparados_turno(interfaz: Any, pedidos_pendientes_turno: list[Any]) -> None:
    """Renderiza la lista descendente de pedidos preparados en el turno activo."""
    if interfaz.usuario_actual and getattr(interfaz.usuario_actual, "role", None) in ("master", "picker"):
        interfaz.lista_pedidos_preparados.controls.clear()
        return

    total_bultos_turno = sum(p.bultos for p in pedidos_pendientes_turno)
    fecha_hoy_str = datetime.now().strftime("%A %d/%m/%Y").capitalize()

    interfaz.header_pedidos_fecha.value = fecha_hoy_str
    interfaz.header_pedidos_subtitulo.value = (
        f"{len(pedidos_pendientes_turno)} pedido(s) preparados en el turno actual"
        if pedidos_pendientes_turno
        else "Turno activo · Sin pedidos pendientes"
    )
    interfaz.header_pedidos_bultos.value = f"📦 {total_bultos_turno} bultos preparados"

    interfaz.lista_pedidos_preparados.controls.clear()
    if not pedidos_pendientes_turno:
        interfaz.lista_pedidos_preparados.controls.append(
            ft.Container(
                padding=20,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=32, color=ft.Colors.GREEN_400),
                        ft.Text("No hay pedidos pendientes de cierre.", size=12, color=interfaz.secundario),
                        ft.Text("Los pedidos que cargues aparecerán aquí en tiempo real.", size=11, color=interfaz.secundario),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
            )
        )
        return

    for ped in pedidos_pendientes_turno:
        hora_c = ped.created_at[11:16] if ped.created_at and len(ped.created_at) >= 16 else ""
        num_p = f"Pedido #{ped.numero_pedido} · " if getattr(ped, "numero_pedido", "") else ""
        titulo_card = f"{num_p}Remito: {ped.nota_pedido}"

        def abrir_modificar_o_ver(p_obj=ped):
            if interfaz.usuario_actual and interfaz.usuario_actual.role == "operador":
                interfaz.mostrar_dialogo_editar_pedido(p_obj, al_final=interfaz.actualizar_listas)
            elif interfaz.usuario_actual and interfaz.usuario_actual.role == "administrador":
                interfaz.mostrar_detalle_pedido_modal(p_obj)

        card_pedido = ft.Container(
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            ink=True,
            tooltip="Clic para abrir y modificar este pedido" if (interfaz.usuario_actual and interfaz.usuario_actual.role == "operador") else "Clic para ver detalle del pedido",
            on_click=lambda _e, p_obj=ped: abrir_modificar_o_ver(p_obj),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.INVENTORY_2, size=18, color=ROJO),
                                bgcolor=ft.Colors.RED_50,
                                padding=6,
                                border_radius=6,
                            ),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(titulo_card, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                            ft.Container(
                                                content=ft.Text(f"{ped.bultos} bulto(s)", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                                bgcolor=ft.Colors.BLUE_GREY_700,
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                border_radius=10,
                                                ink=True,
                                                tooltip="Clic para ajuste rápido de bultos" if (interfaz.usuario_actual and interfaz.usuario_actual.role == "operador") else None,
                                                on_click=(lambda _e, p_obj=ped: interfaz.mostrar_dialogo_ajuste_bultos_express(p_obj, al_final=interfaz.actualizar_listas)) if (interfaz.usuario_actual and interfaz.usuario_actual.role == "operador") else None,
                                            ),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.Text(f"Cliente: {ped.cliente} · {ped.logistica}", size=11, color=interfaz.secundario),
                                    ft.Text(f"Artículos: {ped.resumen_items or f'{ped.articulos_descontados} un.'}", size=10, color=ft.Colors.GREEN_400),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                        expand=True,
                    ),
                    ft.Column(
                        [
                            ft.Text(hora_c, size=10, color=interfaz.secundario, weight=ft.FontWeight.W_500),
                            *(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        icon_size=16,
                                        tooltip="Modificar pedido",
                                        icon_color=ft.Colors.BLUE_400,
                                        on_click=lambda _e, p_obj=ped: interfaz.mostrar_dialogo_editar_pedido(p_obj, al_final=interfaz.actualizar_listas),
                                    )
                                ]
                                if (interfaz.usuario_actual and interfaz.usuario_actual.role == "operador")
                                else []
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        spacing=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        interfaz.lista_pedidos_preparados.controls.append(card_pedido)
