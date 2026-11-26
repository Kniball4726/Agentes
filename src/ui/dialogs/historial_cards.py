"""Componentes de fila, encabezado de fecha y barra de cabecera para historial de pedidos."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ...orders import Pedido
from ..design import colores_de, es_viewport_estrecho
from ..theme import ROJO
from .historial_archivos import abrir_comprobante_pedido
from .historial_detalle import mostrar_detalle_pedido_modal
from .pedidos_gestion import construir_botones_baja_pedido


def _es_operador_activo(interfaz: Any | None) -> bool:
    usuario = getattr(interfaz, "usuario_actual", None) if interfaz is not None else None
    return bool(usuario and getattr(usuario, "role", None) == "operador")


def _columnas_historial(es_operador: bool) -> tuple[tuple[str, int], ...]:
    if es_operador:
        return (
            ("Nota", 75),
            ("Cliente", 205),
            ("Numero", 60),
            ("Bultos", 50),
            ("Logistica", 145),
            ("Preparador", 125),
            ("Nota", 85),
            ("Fecha de retiro o entrega", 110),
            ("Firma", 88),
        )
    return (
        ("Nota", 75),
        ("Cliente", 240),
        ("Numero", 65),
        ("Bultos", 55),
        ("Logistica", 170),
        ("Preparador", 140),
        ("Nota", 90),
        ("Fecha de retiro o entrega", 115),
        ("Firma", 90),
    )


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


def _construir_encabezado_fecha(f_clave: str, hoy_str: str, cant: int, interfaz: Any | None = None) -> ft.Container:
    fecha_display = f_clave
    try:
        partes = f_clave.split("-")
        if len(partes) == 3:
            fecha_display = f"{int(partes[2])}/{int(partes[1])}/{partes[0]}"
    except Exception:
        pass
    es_hoy = f_clave == hoy_str
    colores = colores_de(interfaz)
    return ft.Container(
        bgcolor="#18181c" if colores.modo_oscuro else colores.superficie_suave,
        border=ft.Border(
            left=ft.BorderSide(4, ROJO),
            top=ft.BorderSide(1, colores.borde),
            right=ft.BorderSide(1, colores.borde),
            bottom=ft.BorderSide(1, colores.borde),
        ),
        border_radius=ft.BorderRadius(top_left=4, bottom_left=4, top_right=8, bottom_right=8),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        margin=ft.Margin.only(top=10, bottom=4),
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=ROJO),
                        ft.Text(fecha_display, weight=ft.FontWeight.BOLD, size=13, color=colores.texto),
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


def _construir_tarjeta_pedido_estrecho(
    interfaz: Any,
    p: Pedido,
    pedidos_seleccionados: set[int],
    on_toggle_sel: Callable[[ft.Event, int], None],
    on_cambiar_estado: Callable[[Pedido, str], None],
    badge_firma: ft.Container,
    nota_obs: str,
    col_obs: Any,
    es_operador: bool,
    on_recargar: Callable[[], None] | None,
) -> ft.Container:
    """Renderiza un pedido del historial como tarjeta compacta adaptable en pantallas estrechas."""
    colores = colores_de(interfaz)
    acciones_op = (
        construir_botones_baja_pedido(
            interfaz,
            p,
            on_finalizar=on_recargar,
            icon_size=16,
            button_size=26,
        )
        if es_operador
        else []
    )
    meta_chips: list[ft.Control] = [
        ft.Text(f"📦 {p.bultos} bulto(s)", size=11, weight=ft.FontWeight.BOLD, color=colores.texto),
        ft.Text(f"🚚 {p.logistica or '-'}", size=11, color=colores.secundario),
        ft.Text(f"👤 {p.armador or '-'}", size=11, color=colores.secundario),
    ]
    fecha_ret = getattr(p, "fecha_retiro", "") or ""
    if fecha_ret:
        meta_chips.append(ft.Text(f"📅 {fecha_ret}", size=11, color=colores.secundario))
    if nota_obs:
        meta_chips.append(
            ft.Text(
                nota_obs,
                size=11,
                weight=ft.FontWeight.BOLD if nota_obs == "agregado" else ft.FontWeight.NORMAL,
                color=col_obs,
            )
        )

    return ft.Container(
        bgcolor=colores.superficie_suave,
        border=ft.Border.all(1, colores.borde),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        margin=ft.Margin.only(bottom=4),
        ink=True,
        on_click=lambda _e, ped=p: mostrar_detalle_pedido_modal(interfaz, ped),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Checkbox(
                            value=p.id in pedidos_seleccionados,
                            tooltip="Seleccionar para despacho en lote",
                            on_change=lambda e, pid=p.id: on_toggle_sel(e, pid),
                            scale=0.85,
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(p.nota_pedido or "-", size=12, weight=ft.FontWeight.BOLD, color=colores.texto),
                                        *(
                                            [ft.Text(f"#{p.numero_pedido}", size=11, color=colores.secundario)]
                                            if getattr(p, "numero_pedido", "")
                                            else []
                                        ),
                                        badge_firma,
                                    ],
                                    spacing=6,
                                    wrap=True,
                                    run_spacing=4,
                                ),
                                ft.Text(
                                    p.cliente or "Sin Cliente",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=colores.texto,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DESCRIPTION_OUTLINED,
                            icon_size=18,
                            icon_color=colores.secundario,
                            tooltip=f"Ver/reimprimir comprobante ({p.nombre_archivo or 'Sin archivo'})",
                            on_click=lambda _e, ped=p: abrir_comprobante_pedido(interfaz, ped),
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(meta_chips, spacing=10, wrap=True, run_spacing=4),
                *(
                    [
                        ft.Row(
                            [*acciones_op],
                            spacing=4,
                            alignment=ft.MainAxisAlignment.END,
                        )
                    ]
                    if acciones_op
                    else []
                ),
            ],
            spacing=6,
            tight=True,
        ),
    )


def _construir_fila_pedido(
    interfaz: Any,
    p: Pedido,
    pedidos_seleccionados: set[int],
    on_toggle_sel: Callable[[ft.Event, int], None],
    on_row_hover: Callable[[ft.HoverEvent], None],
    on_cambiar_estado: Callable[[Pedido, str], None],
    on_recargar: Callable[[], None] | None = None,
) -> ft.Container:
    es_anulado = getattr(p, "estado", "") == "anulado"
    es_operador = _es_operador_activo(interfaz)
    anchos = {lbl: w for lbl, w in _columnas_historial(es_operador)}
    # La segunda columna "Nota" corresponde a observaciones; preservamos sus anchos exactos.
    w_nota_obs = 85 if es_operador else 90
    w_chevron = 24 if es_operador else 30
    col_desp_bg, lbl_desp, sig_estado, tip_estado = _estado_visual_despacho(p)

    nota_obs = ""
    colores = colores_de(interfaz)
    col_obs = colores.secundario
    if getattr(p, "agregado", False):
        nota_obs = "agregado"
        col_obs = colores.advertencia
    elif p.resumen_items:
        res_c = p.resumen_items.strip()
        nota_obs = (res_c[:18] + "...") if len(res_c) > 20 else res_c

    badge_firma = ft.Container(
        content=ft.Text("ANULADO" if es_anulado else lbl_desp, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        bgcolor="#dc2626" if es_anulado else col_desp_bg,
        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
        border_radius=4,
        tooltip=tip_estado if not es_anulado else "Pedido anulado",
        on_click=(lambda _e, ped=p, st=sig_estado: on_cambiar_estado(ped, st)) if not es_anulado else None,
    )

    if es_viewport_estrecho(interfaz, umbral=860.0):
        return _construir_tarjeta_pedido_estrecho(
            interfaz,
            p,
            pedidos_seleccionados,
            on_toggle_sel,
            on_cambiar_estado,
            badge_firma,
            nota_obs,
            col_obs,
            es_operador,
            on_recargar,
        )

    botones_accion = (
        [
            ft.Container(
                content=ft.Row(
                    construir_botones_baja_pedido(
                        interfaz,
                        p,
                        on_finalizar=on_recargar,
                        icon_size=16,
                        button_size=24,
                    ),
                    spacing=4,
                    tight=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                width=58,
                alignment=ft.Alignment(0, 0),
            )
        ]
        if es_operador
        else []
    )

    return ft.Container(
        bgcolor=colores.superficie_suave,
        border=ft.Border(bottom=ft.BorderSide(0.5, colores.borde)),
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
                ft.Container(content=ft.Text(p.nota_pedido or "-", size=12, color=colores.texto), width=75),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.DESCRIPTION_OUTLINED,
                                icon_size=15,
                                icon_color=colores.secundario,
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
                                color=colores.texto,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                max_lines=1,
                                expand=True,
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    width=anchos["Cliente"],
                ),
                ft.Container(content=ft.Text(p.numero_pedido or "-", size=12, color=colores.secundario), width=anchos["Numero"]),
                ft.Container(content=ft.Text(str(p.bultos), size=12, weight=ft.FontWeight.BOLD, color=colores.texto), width=anchos["Bultos"]),
                ft.Container(content=ft.Text(p.logistica or "-", size=12, color=colores.secundario, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), width=anchos["Logistica"]),
                ft.Container(content=ft.Text(p.armador or "-", size=12, color=colores.secundario, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), width=anchos["Preparador"]),
                ft.Container(
                    content=ft.Text(
                        nota_obs,
                        size=11,
                        weight=ft.FontWeight.BOLD if nota_obs == "agregado" else ft.FontWeight.NORMAL,
                        color=col_obs,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        max_lines=1,
                    ),
                    width=w_nota_obs,
                ),
                ft.Container(
                    content=ft.Text(getattr(p, "fecha_retiro", "") or "-", size=11, color=colores.secundario, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                    width=anchos["Fecha de retiro o entrega"],
                ),
                ft.Container(content=badge_firma, width=anchos["Firma"]),
                *botones_accion,
                ft.Container(content=ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=colores.secundario), width=w_chevron, alignment=ft.Alignment(1, 0)),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def construir_cabecera_columnas_historial(interfaz: Any | None = None) -> ft.Container:
    """Genera la cabecera tabular fija de la vista histórica de pedidos."""
    if interfaz is not None and es_viewport_estrecho(interfaz, umbral=860.0):
        return ft.Container(visible=False, height=0)
    colores = colores_de(interfaz)
    es_operador = _es_operador_activo(interfaz)
    w_chevron = 24 if es_operador else 30
    return ft.Container(
        bgcolor=colores.superficie_suave,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border=ft.Border(bottom=ft.BorderSide(1, colores.borde)),
        content=ft.Row(
            [
                ft.Container(width=30),
                *[
                    ft.Container(content=ft.Text(lbl, size=12, weight=ft.FontWeight.W_500, color=colores.secundario), width=w)
                    for lbl, w in _columnas_historial(es_operador)
                ],
                *(
                    [
                        ft.Container(
                            content=ft.Text("Acciones", size=12, weight=ft.FontWeight.W_500, color=colores.secundario),
                            width=58,
                            alignment=ft.Alignment(0, 0),
                        )
                    ]
                    if es_operador
                    else []
                ),
                ft.Container(width=w_chevron),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
