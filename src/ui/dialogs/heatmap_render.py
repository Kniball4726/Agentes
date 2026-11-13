"""Componentes de renderizado visual para el Mapa de Calor, Matriz ABC y Slotting."""

from __future__ import annotations

from typing import Any, Callable, List

import flet as ft

from ...warehouse_slotting import (
    DEFAULT_RACKS,
    HeatmapSlot,
    ProductoRotacion,
    SlottingSuggestion,
)
from ..theme import ROJO

_RACK_DESCRIPTIONS = {
    "A": "RACK A — Cabecera de Empaque / Despacho (Zona Prime)",
    "B": "RACK B — Sector Central Frontal",
    "C": "RACK C — Sector Central Posterior",
    "D": "RACK D — Fondo de Depósito (Almacenamiento Lejano)",
}
_LEVEL_NAMES = {3: "Nivel 3 (Alto)", 2: "Nivel 2 (⭐ Dorada)", 1: "Nivel 1 (Piso)"}
_LEYENDA_COLORS = (
    ("#D32F2F", "Muy Caliente (>70%)"),
    ("#FF9800", "Caliente (40-70%)"),
    ("#FFC107", "Medio (15-40%)"),
    ("#37474F", "Frío (<15%)"),
)


def kpi_heatmap_card(interfaz: Any, titulo: str, control_valor: ft.Text) -> ft.Container:
    """Construye una tarjeta KPI uniforme para la cabecera del panel Slotting."""
    return ft.Container(
        content=ft.Column([ft.Text(titulo, size=11, color=interfaz.secundario), control_valor], spacing=2),
        bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
        border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
        border_radius=8,
        padding=10,
        expand=True,
    )


def leyenda_termica_heatmap(interfaz: Any) -> ft.Row:
    """Construye la barra de leyenda térmica de ubicaciones."""
    controles: list[ft.Control] = [
        ft.Text("Leyenda térmica:", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario)
    ]
    for bgcolor, etiqueta in _LEYENDA_COLORS:
        controles.append(ft.Container(width=12, height=12, bgcolor=bgcolor, border_radius=2))
        controles.append(ft.Text(etiqueta, size=10, color=interfaz.secundario))
    controles.append(ft.Text("· ⭐ Zona Dorada", size=10, color=ft.Colors.AMBER_400, weight=ft.FontWeight.BOLD))
    return ft.Row(controles, spacing=6, wrap=True)


def renderizar_layout_heatmap(
    interfaz: Any,
    container: ft.Column,
    mapa_calor_actual: List[HeatmapSlot],
    on_select_slot: Callable[[HeatmapSlot], None],
) -> None:
    """Renderiza los racks, niveles y celdas interactivas del mapa térmico."""
    container.controls.clear()
    slots_por_rack: dict[str, list[HeatmapSlot]] = {r: [] for r in DEFAULT_RACKS}
    for s in mapa_calor_actual:
        if s.rack in slots_por_rack:
            slots_por_rack[s.rack].append(s)

    for rack_id in DEFAULT_RACKS:
        filas_niveles: dict[int, list[HeatmapSlot]] = {3: [], 2: [], 1: []}
        for s in slots_por_rack[rack_id]:
            if s.nivel in filas_niveles:
                filas_niveles[s.nivel].append(s)

        columnas_estantes: list[ft.Control] = []
        for nivel_num in (3, 2, 1):
            celdas: list[ft.Control] = [
                ft.Container(
                    content=ft.Text(_LEVEL_NAMES[nivel_num], size=10, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                    width=110,
                    alignment=ft.Alignment(-1, 0),
                )
            ]
            for slot in sorted(filas_niveles[nivel_num], key=lambda x: x.modulo):
                tip = f"{slot.ubicacion}\nPicks: {slot.picks_totales}\nArtículos: {len(slot.skus_alojados)}"
                celdas.append(
                    ft.Container(
                        tooltip=tip,
                        content=ft.Column(
                            [
                                ft.Text(f"M{slot.modulo:02d}", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text(f"{slot.picks_totales}p", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=1,
                        ),
                        bgcolor=slot.color_hex,
                        border=ft.Border.all(
                            1.5 if slot.es_zona_dorada else 1,
                            ft.Colors.AMBER_ACCENT if slot.es_zona_dorada else ft.Colors.WHITE_24,
                        ),
                        border_radius=6,
                        width=62,
                        height=44,
                        alignment=ft.Alignment(0, 0),
                        on_click=lambda _e, s=slot: on_select_slot(s),
                        ink=True,
                    )
                )
            columnas_estantes.append(ft.Row(celdas, spacing=6))

        card_rack = ft.Container(
            bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
            border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
            border_radius=8,
            padding=10,
            content=ft.Column(
                [
                    ft.Row([ft.Icon(ft.Icons.GRID_ON, size=16, color=ROJO), ft.Text(_RACK_DESCRIPTIONS[rack_id], size=12, weight=ft.FontWeight.BOLD)], spacing=6),
                    ft.Container(height=4),
                    ft.Column(columnas_estantes, spacing=4),
                ],
                spacing=2,
            ),
        )
        container.controls.append(card_rack)


def renderizar_lista_abc(
    interfaz: Any,
    container: ft.ListView,
    analisis_actual: List[ProductoRotacion],
    query: str,
    cat_sel: str,
) -> None:
    """Renderiza el listado filtrado de clasificación ABC."""
    container.controls.clear()
    q = query.strip().lower()
    filtrados = [
        p for p in analisis_actual
        if (cat_sel == "TODAS" or p.categoria_abc == cat_sel)
        and (not q or q in p.codigo.lower() or q in p.nombre.lower())
    ]

    if not filtrados:
        container.controls.append(
            ft.Container(
                content=ft.Text("No se encontraron productos coincidentes.", italic=True, size=12, color=interfaz.secundario),
                padding=16,
                alignment=ft.Alignment(0, 0),
            )
        )
        return

    for prod in filtrados:
        color_badge = (
            ft.Colors.RED_400 if prod.categoria_abc == "A"
            else (ft.Colors.AMBER_400 if prod.categoria_abc == "B" else ft.Colors.BLUE_GREY_300)
        )
        bg_badge = (
            ft.Colors.RED_900 if prod.categoria_abc == "A"
            else (ft.Colors.AMBER_900 if prod.categoria_abc == "B" else ft.Colors.BLUE_GREY_900)
        )
        tag_desalineado = (
            ft.Container(
                content=ft.Text("DESALINEADO", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.ORANGE_900,
                padding=ft.Padding(5, 2, 5, 2),
                border_radius=4,
            )
            if prod.desalineado
            else ft.Container()
        )
        container.controls.append(
            ft.Container(
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=6,
                padding=8,
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(f"Clase {prod.categoria_abc}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=bg_badge,
                            padding=ft.Padding(6, 4, 6, 4),
                            border_radius=4,
                            width=60,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            [
                                ft.Row([ft.Text(f"[{prod.codigo}]", weight=ft.FontWeight.BOLD, size=12), ft.Text(prod.nombre, weight=ft.FontWeight.W_500, size=12, expand=True, no_wrap=True), tag_desalineado], spacing=6),
                                ft.Row(
                                    [
                                        ft.Text(f"Picks: {prod.total_despachos}", size=11, weight=ft.FontWeight.BOLD, color=color_badge),
                                        ft.Text(f"Unidades: {prod.unidades_despachadas}", size=11, color=interfaz.secundario),
                                        ft.Text(f"Acumulado: {prod.porcentaje_acumulado}%", size=11, color=interfaz.secundario),
                                        ft.Text(f"📍 Actual: {prod.ubicacion_actual}", size=11, weight=ft.FontWeight.BOLD),
                                        ft.Text(f"➔ Sugerida: {prod.ubicacion_sugerida}", size=11, color=ft.Colors.GREEN_400),
                                    ],
                                    spacing=12,
                                ),
                            ],
                            expand=True,
                            spacing=3,
                        ),
                    ],
                    spacing=10,
                ),
            )
        )


def renderizar_lista_sugerencias(
    interfaz: Any,
    container: ft.ListView,
    sugerencias_actuales: List[SlottingSuggestion],
    on_reubicar: Callable[[SlottingSuggestion], None],
) -> None:
    """Renderiza el listado de sugerencias de reubicación ergonómica (slotting)."""
    container.controls.clear()
    if not sugerencias_actuales:
        container.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.VERIFIED, color=ft.Colors.GREEN_400, size=36),
                        ft.Text("¡Depósito 100% Optimizado!", weight=ft.FontWeight.BOLD, size=14),
                        ft.Text("Todos los artículos de alta rotación residen en ubicaciones estratégicas y ergonómicas.", size=12, color=interfaz.secundario),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                ),
                padding=24,
                alignment=ft.Alignment(0, 0),
            )
        )
        return

    for sug in sugerencias_actuales:
        badge_color = ft.Colors.RED_400 if sug.categoria_abc == "A" else ft.Colors.BLUE_GREY_400
        container.controls.append(
            ft.Container(
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=8,
                padding=10,
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.SWAP_HORIZ,
                            size=24,
                            color=ft.Colors.ORANGE_400 if sug.categoria_abc == "A" else ft.Colors.CYAN_400,
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(f"[{sug.sku}]", weight=ft.FontWeight.BOLD, size=12),
                                        ft.Text(sug.nombre, weight=ft.FontWeight.W_500, size=12, expand=True, no_wrap=True),
                                        ft.Container(
                                            content=ft.Text(f"Clase {sug.categoria_abc}", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            bgcolor=badge_color,
                                            padding=ft.Padding(5, 2, 5, 2),
                                            border_radius=4,
                                        ),
                                    ],
                                    spacing=6,
                                ),
                                ft.Text(sug.motivo, size=11, color=interfaz.secundario),
                                ft.Row(
                                    [
                                        ft.Text(f"📍 Actual: {sug.ubicacion_actual}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300),
                                        ft.Icon(ft.Icons.ARROW_FORWARD, size=12, color=interfaz.secundario),
                                        ft.Text(f"🎯 Sugerida: {sug.ubicacion_sugerida}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                                        ft.Text(f"({sug.impacto})", size=10, color=interfaz.secundario),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            expand=True,
                            spacing=3,
                        ),
                        ft.Button(
                            "Reubicar",
                            icon=ft.Icons.CHECK,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, padding=ft.Padding(10, 6, 10, 6)),
                            on_click=lambda _e, s=sug: on_reubicar(s),
                        ),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            )
        )
