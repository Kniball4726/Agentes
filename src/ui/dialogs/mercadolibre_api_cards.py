"""Constructores de tarjetas y pestañas para el diálogo de Mercado Libre API."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ..design import colores_de, es_viewport_estrecho, par_accion_tarjeta
from ..theme import ROJO


def construir_tarjeta_orden_ml(
    interfaz: Any,
    ord_info: dict[str, Any],
    ya_procesado: bool,
    seleccionada: bool,
    on_check_change: Callable[[ft.Event], None],
) -> ft.Container:
    """Construye la tarjeta visual de una orden sincronizada de Mercado Libre."""
    colores = colores_de(interfaz)
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

    es_estrecho = es_viewport_estrecho(interfaz, umbral=620.0)
    filas_items: list[ft.Control] = []
    for it in ord_info["items_coincidentes"]:
        stk_post = it["stock_actual"] - it["cantidad"]
        stk_color = colores.error if stk_post < 0 else interfaz.secundario
        if es_estrecho:
            filas_items.append(
                ft.Column(
                    [
                        ft.Text(
                            f"[{it['codigo']}] {it['nombre']}",
                            size=11,
                            weight=ft.FontWeight.W_500,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            [
                                ft.Text(f"-{it['cantidad']} un.", color=colores.error, weight=ft.FontWeight.BOLD, size=11),
                                ft.Text(f"Stock: {it['stock_actual']} -> {stk_post}", size=11, color=stk_color),
                            ],
                            spacing=10,
                            wrap=True,
                        ),
                    ],
                    spacing=1,
                    tight=True,
                )
            )
        else:
            filas_items.append(
                ft.Row(
                    [
                        ft.Text(f"[{it['codigo']}]", weight=ft.FontWeight.BOLD, size=11, width=70),
                        ft.Text(it["nombre"], size=11, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"-{it['cantidad']} un.", color=colores.error, weight=ft.FontWeight.BOLD, size=11, width=60),
                        ft.Text(f"Stock: {it['stock_actual']} -> {stk_post}", size=11, color=stk_color, width=130),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )

    for no_it in ord_info["items_no_coincidentes"]:
        filas_items.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER, color=colores.advertencia, size=14),
                    ft.Text(
                        f"No reconocido: {no_it['titulo']} (Cant: {no_it['cantidad']})",
                        size=11,
                        color=colores.advertencia,
                        expand=True,
                    ),
                ],
            )
        )

    ref = ord_info["ref_pedido"]
    cabecera_info = ft.Row(
        [
            ft.Checkbox(
                value=seleccionada,
                disabled=ya_procesado,
                on_change=on_check_change,
            ),
            ft.Column(
                [
                    ft.Text(f"{ref} · {ord_info['cliente']}", weight=ft.FontWeight.BOLD, size=12, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(
                        f"Fecha: {ord_info['fecha']} | {ord_info['total_unidades']} un. | Total: ${ord_info['total_importe']:,.2f}",
                        size=11,
                        color=interfaz.secundario,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                expand=True,
                spacing=2,
            ),
        ],
        spacing=6,
        expand=not es_estrecho,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return ft.Container(
        bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
        border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
        border_radius=8,
        padding=10,
        content=ft.Column(
            [
                par_accion_tarjeta(interfaz, cabecera_info, chip_estado, umbral=540.0, spacing=8),
                ft.Container(
                    padding=ft.Padding(left=12 if es_estrecho else 28, top=4, right=4, bottom=4),
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
                wrap=True,
                run_spacing=6,
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
                wrap=True,
                run_spacing=6,
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
