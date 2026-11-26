"""Componentes visuales Flet para reposición a picking y alertas de vencimiento FEFO."""

from __future__ import annotations

from typing import Any, Callable, List

import flet as ft

from ...warehouse_slotting import SugerenciaReposicionPicking
from ..design import es_viewport_estrecho

_COLOR_PRIORIDAD = {
    "URGENTE": ft.Colors.RED_600,
    "ALTA": ft.Colors.ORANGE_700,
    "MEDIA": ft.Colors.BLUE_700,
}

_COLOR_ALERTA_FEFO = {
    "VENCIDO": ft.Colors.RED_700,
    "CRITICO": ft.Colors.ORANGE_700,
    "PROXIMO": ft.Colors.AMBER_700,
}


def _estilo_tarjeta(interfaz: Any) -> tuple[Any, Any]:
    dark = bool(getattr(interfaz, "modo_oscuro", True))
    bgcolor = ft.Colors.WHITE_10 if dark else ft.Colors.GREY_100
    border = ft.Border.all(1, ft.Colors.WHITE_24 if dark else ft.Colors.GREY_300)
    return bgcolor, border


def _badge_texto(etiqueta: str, bgcolor: Any) -> ft.Container:
    return ft.Container(
        content=ft.Text(etiqueta, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        bgcolor=bgcolor,
        padding=ft.Padding(6, 2, 6, 2),
        border_radius=4,
    )


def _construir_card_reposicion(
    interfaz: Any,
    sug: SugerenciaReposicionPicking,
    estrecho: bool,
    on_ejecutar_traslado: Callable[[SugerenciaReposicionPicking], None],
) -> ft.Container:
    bgcolor, border = _estilo_tarjeta(interfaz)
    color_prio = _COLOR_PRIORIDAD.get(sug.prioridad, ft.Colors.BLUE_GREY_600)
    detalle_fefo = (
        f" · Lote FEFO: {sug.lote_fefo} (vto {sug.fecha_vencimiento_fefo})"
        if sug.lote_fefo
        else ""
    )
    info = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(f"[{sug.product_code}]", weight=ft.FontWeight.BOLD, size=12),
                    ft.Text(
                        sug.product_name,
                        weight=ft.FontWeight.W_500,
                        size=12,
                        expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    _badge_texto(sug.prioridad, color_prio),
                ],
                spacing=6,
            ),
            ft.Text(f"{sug.motivo}{detalle_fefo}", size=11, color=interfaz.secundario),
            ft.Row(
                [
                    ft.Text(
                        f"Origen ({sug.zona_origen}): {sug.ubicacion_origen} ({sug.stock_reserva_origen} u.)",
                        size=11,
                        color=ft.Colors.CYAN_400,
                    ),
                    ft.Icon(ft.Icons.ARROW_FORWARD, size=12, color=interfaz.secundario),
                    ft.Text(
                        f"Picking: {sug.ubicacion_destino} ({sug.stock_picking_actual} u.)",
                        size=11,
                        color=ft.Colors.GREEN_400,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        f"Sugerido: +{sug.cantidad_sugerida} u.",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.AMBER_400,
                    ),
                ],
                spacing=8,
                run_spacing=4,
                wrap=True,
            ),
        ],
        expand=True,
        spacing=3,
    )
    btn_trasladar = ft.Button(
        "Ejecutar Traslado",
        icon=ft.Icons.LOCAL_SHIPPING_OUTLINED,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.TEAL_700,
            color=ft.Colors.WHITE,
            padding=ft.Padding(10, 6, 10, 6),
        ),
        on_click=lambda _e, s=sug: on_ejecutar_traslado(s),
    )
    ico = ft.Icon(ft.Icons.MOVE_TO_INBOX_ROUNDED, color=color_prio, size=24)
    cuerpo: ft.Control = (
        ft.Column(
            [ft.Row([ico, info], spacing=10), btn_trasladar],
            spacing=8,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.END,
        )
        if estrecho
        else ft.Row(
            [ico, info, btn_trasladar],
            spacing=10,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
    )
    return ft.Container(
        bgcolor=bgcolor,
        border=border,
        border_radius=8,
        padding=10,
        content=cuerpo,
    )


def _construir_card_alerta_fefo(
    interfaz: Any,
    lote: dict[str, Any],
) -> ft.Container:
    bgcolor, border = _estilo_tarjeta(interfaz)
    nivel = str(lote.get("nivel_alerta", "PROXIMO")).upper()
    color_badge = _COLOR_ALERTA_FEFO.get(nivel, ft.Colors.AMBER_700)
    dias_rest = lote.get("dias_para_vencer")
    if dias_rest is None:
        dias_txt = "Sin cálculo de días"
    elif int(dias_rest) < 0:
        dias_txt = f"Vencido hace {abs(int(dias_rest))} d."
    elif int(dias_rest) == 0:
        dias_txt = "Vence HOY"
    else:
        dias_txt = f"Vence en {int(dias_rest)} d."

    ubic_txt = str(lote.get("ubicacion") or "Sin ubicación")
    return ft.Container(
        bgcolor=bgcolor,
        border=border,
        border_radius=8,
        padding=10,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.EVENT_BUSY_ROUNDED if nivel == "VENCIDO" else ft.Icons.SCHEDULE_ROUNDED, color=color_badge, size=22),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(f"[{lote.get('product_code', '')}]", weight=ft.FontWeight.BOLD, size=12),
                                ft.Text(
                                    str(lote.get("product_name") or lote.get("product_code") or ""),
                                    size=12,
                                    weight=ft.FontWeight.W_500,
                                    expand=True,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                _badge_texto(nivel, color_badge),
                            ],
                            spacing=6,
                        ),
                        ft.Row(
                            [
                                ft.Text(f"Lote: {lote.get('lote', '')}", size=11, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Ubic.: {ubic_txt}", size=11, color=interfaz.secundario),
                                ft.Text(f"Saldo: {lote.get('stock', 0)} u.", size=11, color=ft.Colors.CYAN_400),
                                ft.Text(
                                    f"Vto: {lote.get('fecha_vencimiento', '')} ({dias_txt})",
                                    size=11,
                                    color=color_badge,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                            spacing=10,
                            wrap=True,
                            run_spacing=4,
                        ),
                    ],
                    expand=True,
                    spacing=3,
                ),
            ],
            spacing=10,
        ),
    )


def renderizar_panel_reposicion_y_fefo(
    interfaz: Any,
    container: ft.ListView,
    sugerencias_reposicion: List[SugerenciaReposicionPicking],
    alertas_fefo: list[dict[str, Any]],
    filtro_nivel: str,
    on_ejecutar_traslado: Callable[[SugerenciaReposicionPicking], None],
) -> None:
    """Renderiza sugerencias de reposición a picking y alertas de lotes próximos a vencer."""
    container.controls.clear()
    nivel_norm = (filtro_nivel or "TODOS").strip().upper()
    alertas_filtradas = [
        a
        for a in alertas_fefo
        if nivel_norm == "TODOS" or str(a.get("nivel_alerta", "")).upper() == nivel_norm
    ]

    estrecho = es_viewport_estrecho(interfaz, umbral=600.0)

    container.controls.append(
        ft.Text(
            f"Reposición Pulmón/Pallet → Picking ({len(sugerencias_reposicion)})",
            size=12,
            weight=ft.FontWeight.BOLD,
            color=interfaz.texto,
        )
    )
    if sugerencias_reposicion:
        for sug in sugerencias_reposicion:
            container.controls.append(
                _construir_card_reposicion(interfaz, sug, estrecho, on_ejecutar_traslado)
            )
    else:
        container.controls.append(
            ft.Text(
                "Sin reposiciones urgentes pendientes entre zonas de reserva y picking.",
                size=11,
                italic=True,
                color=interfaz.secundario,
            )
        )

    container.controls.append(ft.Divider(height=10, color=interfaz.borde))
    container.controls.append(
        ft.Text(
            f"Alertas de Vencimiento FEFO ({len(alertas_filtradas)})",
            size=12,
            weight=ft.FontWeight.BOLD,
            color=interfaz.texto,
        )
    )
    if alertas_filtradas:
        for lote in alertas_filtradas:
            container.controls.append(_construir_card_alerta_fefo(interfaz, lote))
    else:
        container.controls.append(
            ft.Text(
                "No hay lotes vencidos o próximos a vencer para el filtro seleccionado.",
                size=11,
                italic=True,
                color=interfaz.secundario,
            )
        )
