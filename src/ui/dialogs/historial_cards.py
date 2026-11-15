"""Componentes de fila, encabezado de fecha y barra de cabecera para historial de pedidos."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ...orders import Pedido
from ..theme import ROJO
from .historial_archivos import abrir_comprobante_pedido
from .historial_detalle import mostrar_detalle_pedido_modal


def _formatear_fecha_corta(f_str: str) -> str:
    try:
        partes = f_str.split("-")
        if len(partes) == 3:
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
    except Exception:
        pass
    return f_str


def _coincide_pedido(p: Pedido, q: str) -> bool:
    if not q:
        return True
    q = q.lower().strip()
    c_at = p.created_at or ""
    campos = (
        p.cliente or "",
        p.nota_pedido or "",
        str(getattr(p, "numero_pedido", "") or ""),
        p.armador or "",
        p.logistica or "",
        c_at,
        _formatear_fecha_corta(c_at[:10]),
        str(getattr(p, "fecha_retiro", "") or ""),
        p.nombre_archivo or "",
    )
    return any(q in campo.lower() for campo in campos)


def _estado_visual_despacho(p: Pedido) -> tuple[str, str, str, str]:
    est_desp = (getattr(p, "estado_despacho", "armado") or "armado").lower()
    if est_desp == "entregado":
        return "#16a34a", "ENTREGADO", "armado", "Estado actual: Entregado (clic para volver a Armado)"
    if est_desp == "despachado":
        return "#d97706", "DESPACHADO", "entregado", "Marcar como DESPACHADO"
    return "#2563eb", "ARMADO", "despachado", "Marcar como DESPACHADO"


def _construir_encabezado_fecha(f_clave: str, hoy_str: str, cant: int) -> ft.Container:
    fecha_display = f_clave
    try:
        partes = f_clave.split("-")
        if len(partes) == 3:
            fecha_display = f"{int(partes[2])}/{int(partes[1])}/{partes[0]}"
    except Exception:
        pass
    es_hoy = f_clave == hoy_str
    return ft.Container(
        bgcolor="#18181c",
        border=ft.Border(
            left=ft.BorderSide(4, ROJO),
            top=ft.BorderSide(1, "#27272a"),
            right=ft.BorderSide(1, "#27272a"),
            bottom=ft.BorderSide(1, "#27272a"),
        ),
        border_radius=ft.BorderRadius(top_left=4, bottom_left=4, top_right=8, bottom_right=8),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        margin=ft.Margin.only(top=10, bottom=4),
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=ROJO),
                        ft.Text(fecha_display, weight=ft.FontWeight.BOLD, size=13, color="#f4f4f5"),
                        *(
                            [
                                ft.Container(
                                    content=ft.Text("HOY", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor=ROJO,
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    border_radius=4,
                                )
                            ]
                            if es_hoy
                            else []
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    content=ft.Text(f"{cant} pedido{'s' if cant != 1 else ''}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ROJO,
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _construir_fila_pedido(
    interfaz: Any,
    p: Pedido,
    pedidos_seleccionados: set[int],
    on_toggle_sel: Callable[[ft.Event, int], None],
    on_row_hover: Callable[[ft.HoverEvent], None],
    on_cambiar_estado: Callable[[Pedido, str], None],
) -> ft.Container:
    es_anulado = getattr(p, "estado", "") == "anulado"
    col_desp_bg, lbl_desp, sig_estado, tip_estado = _estado_visual_despacho(p)

    nota_obs = ""
    col_obs = "#a1a1aa"
    if getattr(p, "agregado", False):
        nota_obs = "agregado"
        col_obs = "#eab308"
    elif p.resumen_items:
        res_c = p.resumen_items.strip()
        nota_obs = (res_c[:18] + "...") if len(res_c) > 20 else res_c

    badge_firma = ft.Container(
        content=ft.Text("ANULADO" if es_anulado else lbl_desp, size=10, weight=ft.FontWeight.BOLD, color="#ffffff"),
        bgcolor="#dc2626" if es_anulado else col_desp_bg,
        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
        border_radius=4,
        tooltip=tip_estado if not es_anulado else "Pedido anulado",
        on_click=(lambda _e, ped=p, st=sig_estado: on_cambiar_estado(ped, st)) if not es_anulado else None,
    )

    return ft.Container(
        bgcolor="#141416",
        border=ft.Border(bottom=ft.BorderSide(0.5, "#222226")),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        ink=True,
        on_hover=on_row_hover,
        on_click=lambda _e, ped=p: mostrar_detalle_pedido_modal(interfaz, ped),
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Checkbox(
                        value=p.id in pedidos_seleccionados,
                        tooltip="Seleccionar para despacho en lote",
                        on_change=lambda e, pid=p.id: on_toggle_sel(e, pid),
                        scale=0.8,
                    ),
                    width=30,
                    alignment=ft.Alignment(-1, 0),
                ),
                ft.Container(content=ft.Text(p.nota_pedido or "-", size=12, color="#f4f4f5"), width=75),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.DESCRIPTION_OUTLINED,
                                icon_size=15,
                                icon_color="#9ca3af",
                                tooltip=f"Ver/reimprimir comprobante ({p.nombre_archivo or 'Sin archivo'})",
                                on_click=lambda _e, ped=p: abrir_comprobante_pedido(interfaz, ped),
                                style=ft.ButtonStyle(padding=0),
                                width=18,
                                height=18,
                            ),
                            ft.Text(
                                p.cliente or "Sin Cliente",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color="#f4f4f5",
                                overflow=ft.TextOverflow.ELLIPSIS,
                                max_lines=1,
                                expand=True,
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    width=240,
                ),
                ft.Container(content=ft.Text(p.numero_pedido or "-", size=12, color="#d4d4d8"), width=65),
                ft.Container(content=ft.Text(str(p.bultos), size=12, weight=ft.FontWeight.BOLD, color="#d4d4d8"), width=55),
                ft.Container(content=ft.Text(p.logistica or "-", size=12, color="#d4d4d8", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), width=170),
                ft.Container(content=ft.Text(p.armador or "-", size=12, color="#a1a1aa", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), width=140),
                ft.Container(
                    content=ft.Text(
                        nota_obs,
                        size=11,
                        weight=ft.FontWeight.BOLD if nota_obs == "agregado" else ft.FontWeight.NORMAL,
                        color=col_obs,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        max_lines=1,
                    ),
                    width=90,
                ),
                ft.Container(
                    content=ft.Text(getattr(p, "fecha_retiro", "") or "-", size=11, color="#a1a1aa", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                    width=115,
                ),
                ft.Container(content=badge_firma, width=90),
                ft.Container(content=ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color="#71717a"), width=30, alignment=ft.Alignment(1, 0)),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def construir_cabecera_columnas_historial() -> ft.Container:
    """Genera la cabecera tabular fija de la vista histórica de pedidos."""
    return ft.Container(
        bgcolor="#18181b",
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border=ft.Border(bottom=ft.BorderSide(1, "#27272a")),
        content=ft.Row(
            [
                ft.Container(width=30),
                *[
                    ft.Container(content=ft.Text(lbl, size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=w)
                    for lbl, w in (
                        ("Nota", 75), ("Cliente", 240), ("Numero", 65), ("Bultos", 55),
                        ("Logistica", 170), ("Preparador", 140), ("Nota", 90),
                        ("Fecha de retiro o entrega", 115), ("Firma", 90),
                    )
                ],
                ft.Container(width=30),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
