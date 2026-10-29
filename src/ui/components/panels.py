"""Componentes visuales del panel principal: tarjetas de métricas e informes de actividad."""

from typing import Any

import flet as ft

from ..theme import ROJO


def construir_panel_metricas(interfaz: Any) -> ft.Control:
    """Genera las tarjetas de métricas en vivo para la jornada activa."""
    metricas = [
        ("PDF de la jornada", "pdf", ft.Icons.DESCRIPTION),
        ("Canjes de la jornada", "canjes", ft.Icons.SHOPPING_BAG),
        ("Pedidos ML", "ml", ft.Icons.LOCAL_SHIPPING),
        ("Total Jornada", "total", ft.Icons.RECEIPT_LONG),
        ("Informes", "informes", ft.Icons.INSERT_CHART),
    ]
    if interfaz.usuario_actual and interfaz.usuario_actual.role == "administrador":
        metricas.append(("Quiebres de stock", "quiebres", ft.Icons.WARNING_AMBER))
    tarjetas = []
    for titulo, clave, icono in metricas:
        valor = ft.Text("0", size=25, weight=ft.FontWeight.BOLD, color=interfaz.texto)
        interfaz.contadores[clave] = valor
        tarjetas.append(
            ft.Container(
                expand=True,
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=12,
                padding=16,
                content=ft.Row(
                    [
                        ft.Container(
                            width=40,
                            height=40,
                            border_radius=10,
                            bgcolor=ft.Colors.RED_50,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icono, color=ROJO, size=20),
                        ),
                        ft.Column(
                            [
                                ft.Text(titulo, size=11, color=interfaz.secundario),
                                valor,
                            ],
                            spacing=3,
                        ),
                    ],
                    spacing=12,
                ),
            )
        )
    if interfaz.es_pantalla_movil:
        for t in tarjetas:
            t.expand = False
            t.col = 6
            t.padding = 10
        return ft.ResponsiveRow(tarjetas, spacing=8, run_spacing=8)
    return ft.Row(tarjetas, spacing=12)


def construir_panel_informes_actividad(interfaz: Any) -> ft.Control:
    """Genera el panel de lista de informes recientes y actividad en tiempo real."""
    contenido_informes = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Informes generados", size=16, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Icon(ft.Icons.DESCRIPTION, color=ROJO, size=18),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            interfaz.lista_informes,
        ],
        expand=True,
        spacing=10,
    )
    contenido_actividad = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Actividad", size=16, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Icon(ft.Icons.BOLT, color=ROJO, size=18),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            interfaz.actividad,
        ],
        expand=True,
        spacing=10,
    )
    if interfaz.es_pantalla_movil:
        return ft.Column(
            [
                interfaz.tarjeta(contenido_informes),
                interfaz.tarjeta(contenido_actividad),
            ],
            spacing=12,
        )
    return ft.Row(
        [
            interfaz.tarjeta(contenido_informes, expand=True),
            interfaz.tarjeta(contenido_actividad, expand=True),
        ],
        spacing=12,
        expand=True,
    )
