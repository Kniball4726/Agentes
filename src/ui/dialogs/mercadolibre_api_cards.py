"""Constructores de tarjetas y pestañas para el diálogo de Mercado Libre API."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ..theme import ROJO


def construir_tarjeta_orden_ml(
    interfaz: Any,
    ord_info: dict[str, Any],
    ya_procesado: bool,
    seleccionada: bool,
    on_check_change: Callable[[ft.Event], None],
) -> ft.Container:
    """Construye la tarjeta visual de una orden sincronizada de Mercado Libre."""
    if ya_procesado:
        chip_estado = ft.Container(
            content=ft.Text("YA DESCONTADO", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
            bgcolor=ft.Colors.GREY_800,
            padding=ft.Padding(6, 2, 6, 2),
            border_radius=4,
        )
    elif not ord_info["stock_suficiente"]:
        chip_estado = ft.Container(
            content=ft.Text("FALTA STOCK", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_100),
            bgcolor=ft.Colors.RED_900,
            padding=ft.Padding(6, 2, 6, 2),
            border_radius=4,
        )
    else:
        chip_estado = ft.Container(
            content=ft.Text("LISTO P/ DESCUENTO", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_100),
            bgcolor=ft.Colors.GREEN_800,
            padding=ft.Padding(6, 2, 6, 2),
            border_radius=4,
        )

    filas_items: list[ft.Control] = []
    for it in ord_info["items_coincidentes"]:
        stk_post = it["stock_actual"] - it["cantidad"]
        stk_color = ft.Colors.RED_400 if stk_post < 0 else interfaz.secundario
        filas_items.append(
            ft.Row(
                [
                    ft.Text(f"[{it['codigo']}]", weight=ft.FontWeight.BOLD, size=11, width=70),
                    ft.Text(it["nombre"], size=11, expand=True, no_wrap=True),
                    ft.Text(f"-{it['cantidad']} un.", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD, size=11, width=60),
                    ft.Text(f"Stock: {it['stock_actual']} -> {stk_post}", size=11, color=stk_color, width=130),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )

    for no_it in ord_info["items_no_coincidentes"]:
        filas_items.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.AMBER_400, size=14),
                    ft.Text(
                        f"No reconocido: {no_it['titulo']} (Cant: {no_it['cantidad']})",
                        size=11,
                        color=ft.Colors.AMBER_400,
                        expand=True,
                    ),
                ],
            )
        )

    ref = ord_info["ref_pedido"]
    return ft.Container(
        bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
        border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
        border_radius=8,
        padding=10,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Checkbox(
                            value=seleccionada,
                            disabled=ya_procesado,
                            on_change=on_check_change,
                        ),
                        ft.Column(
                            [
                                ft.Text(f"{ref} · {ord_info['cliente']}", weight=ft.FontWeight.BOLD, size=12),
                                ft.Text(
                                    f"Fecha: {ord_info['fecha']} | {ord_info['total_unidades']} un. | Total: ${ord_info['total_importe']:,.2f}",
                                    size=11,
                                    color=interfaz.secundario,
                                ),
                            ],
                            expand=True,
                            spacing=2,
                        ),
                        chip_estado,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    padding=ft.Padding(left=28, top=4, right=4, bottom=4),
                    content=ft.Column(filas_items, spacing=2),
                ),
            ],
            spacing=4,
        ),
    )


def construir_contenido_dialogo_ml(
    interfaz: Any,
    es_master: bool,
    on_sincronizar: Callable,
    chk_solo_pendientes: ft.Checkbox,
    texto_resumen_sincronizacion: ft.Text,
    lista_ordenes_view: ft.ListView,
    controles_config: list[ft.Control],
    texto_estado_config: ft.Text,
    on_probar_conexion: Callable,
    on_guardar_config: Callable,
) -> ft.Control:
    """Construye la vista de órdenes y (solo para Master) las pestañas con credenciales API."""
    vista_ordenes = ft.Column(
        [
            ft.Row(
                [
                    ft.Button(
                        "Sincronizar Ahora",
                        icon=ft.Icons.SYNC,
                        bgcolor=ROJO,
                        color=ft.Colors.WHITE,
                        on_click=on_sincronizar,
                    ),
                    chk_solo_pendientes,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            texto_resumen_sincronizacion,
            ft.Divider(height=10, color=interfaz.borde),
            lista_ordenes_view,
        ],
        spacing=6,
        expand=True,
    )

    if not es_master:
        return ft.Container(
            content=vista_ordenes,
            padding=ft.Padding.all(4),
            expand=True,
        )

    vista_config = ft.Column(
        [
            ft.Text(
                "Configuración de credenciales de la aplicación en Mercado Libre Developers:",
                size=12,
                color=interfaz.secundario,
            ),
            *controles_config,
            texto_estado_config,
            ft.Row(
                [
                    ft.OutlinedButton("Probar Conexión", icon=ft.Icons.CHECK_CIRCLE, on_click=on_probar_conexion),
                    ft.Button("Guardar Configuración", icon=ft.Icons.SAVE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=on_guardar_config),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    return ft.Tabs(
        length=2,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Órdenes Sincronizadas", icon=ft.Icons.LIST_ALT),
                        ft.Tab(label="Credenciales API (Master)", icon=ft.Icons.SETTINGS),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[vista_ordenes, vista_config],
                ),
            ],
        ),
    )
