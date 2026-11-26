"""Componentes visuales reutilizables para el módulo Despacho (pistola QR, bultos y solo lectura)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import flet as ft

from ...orders import Pedido
from ..design import par_accion_tarjeta
from ..theme import ROJO


def construir_kpi_despacho(
    interfaz: Any,
    titulo: str,
    valor_control: ft.Text,
    icono: Any,
    color_acento: Any,
) -> ft.Container:
    """Construye una tarjeta KPI compacta para el encabezado del módulo Despacho."""
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    valor_control.max_lines = 1
    valor_control.overflow = ft.TextOverflow.ELLIPSIS
    return ft.Container(
        expand=True,
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.22, color_acento) if es_oscuro else interfaz.borde),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Row(
            [
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=9,
                    bgcolor=ft.Colors.with_opacity(0.16, color_acento),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icono, color=color_acento, size=18),
                ),
                ft.Column(
                    [
                        ft.Text(
                            titulo,
                            size=11,
                            color=interfaz.secundario,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        valor_control,
                    ],
                    spacing=1,
                    expand=True,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _construir_chips_bultos(
    interfaz: Any,
    total_bultos: int,
    escaneados: list[int],
) -> ft.Control:
    """Renderiza el avance de escaneo bulto por bulto (1/N … N/N)."""
    esc_set = set(escaneados)
    total = max(1, int(total_bultos or 1))
    if total > 12:
        progreso_color = ft.Colors.GREEN_500 if len(esc_set) >= total else (
            ft.Colors.AMBER_500 if esc_set else interfaz.secundario
        )
        return ft.Container(
            bgcolor=ft.Colors.with_opacity(0.14, progreso_color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.4, progreso_color)),
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            content=ft.Text(
                f"Bultos verificados: {len(esc_set)}/{total}",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=progreso_color,
            ),
        )

    chips: list[ft.Control] = []
    for idx in range(1, total + 1):
        ok = idx in esc_set
        color_chip = ft.Colors.GREEN_500 if ok else interfaz.secundario
        chips.append(
            ft.Container(
                bgcolor=ft.Colors.with_opacity(0.18 if ok else 0.06, color_chip),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.6 if ok else 0.25, color_chip)),
                border_radius=6,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE if ok else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            size=12,
                            color=color_chip,
                        ),
                        ft.Text(
                            f"Bulto {idx}/{total}",
                            size=10,
                            weight=ft.FontWeight.BOLD if ok else ft.FontWeight.W_500,
                            color=color_chip if ok else interfaz.texto,
                        ),
                    ],
                    spacing=3,
                    tight=True,
                ),
            )
        )
    return ft.Row(chips, wrap=True, spacing=5, run_spacing=4)


def construir_tarjeta_pedido_pendiente(
    interfaz: Any,
    pedido: Pedido,
    bultos_escaneados: list[int],
    on_despachar_manual: Callable[[Pedido], None],
    destacado: bool = False,
) -> ft.Container:
    """Renderiza una tarjeta operativa de pedido en estado `armado` listo para despachar."""
    parcial = len(bultos_escaneados) > 0
    borde_color = (
        ROJO
        if destacado
        else (ft.Colors.AMBER_500 if parcial else interfaz.borde)
    )
    guia_txt = f" · Guía: {pedido.numero_guia}" if getattr(pedido, "numero_guia", "") else ""
    fecha_txt = (pedido.created_at or "")[:16]

    info_col = ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=16, color=ROJO),
                    ft.Text(
                        f"Remito #{pedido.nota_pedido}",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=interfaz.texto,
                    ),
                    ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_500 if parcial else ft.Colors.BLUE_500),
                        border_radius=6,
                        padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                        content=ft.Text(
                            f"EN CONTROL ({len(bultos_escaneados)}/{pedido.bultos})"
                            if parcial
                            else f"ARMADO · {pedido.bultos} bulto(s)",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.AMBER_400 if parcial else ft.Colors.BLUE_400,
                        ),
                    ),
                ],
                spacing=8,
                wrap=True,
                run_spacing=4,
            ),
            ft.Text(
                f"Cliente: {pedido.cliente} · {pedido.logistica}{guia_txt}",
                size=12,
                color=interfaz.texto,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Text(
                f"Armador: {pedido.armador} · Armado: {fecha_txt}",
                size=11,
                color=interfaz.secundario,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
        spacing=3,
        expand=True,
    )
    btn_despachar = ft.Button(
        content="Despachar manual",
        icon=ft.Icons.LOCAL_SHIPPING,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        on_click=lambda _e, p=pedido: on_despachar_manual(p),
    )

    return ft.Container(
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1.5 if (destacado or parcial) else 1, borde_color),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Column(
            [
                par_accion_tarjeta(interfaz, info_col, btn_despachar, umbral=640.0, spacing=10),
                _construir_chips_bultos(interfaz, pedido.bultos, bultos_escaneados),
            ],
            spacing=8,
            tight=True,
        ),
    )


def construir_tarjeta_pedido_despachado(
    interfaz: Any,
    pedido: Pedido,
) -> ft.Container:
    """Renderiza una tarjeta de solo lectura para un pedido ya despachado (o entregado)."""
    est = (pedido.estado_despacho or "despachado").strip().lower()
    es_entregado = est == "entregado"
    badge_color = ft.Colors.TEAL_600 if es_entregado else ft.Colors.GREEN_600
    fecha_desp = pedido.despachado_at or pedido.created_at or ""
    quien = pedido.despachado_por or "Sin registrar"
    guia_txt = f" · Guía: {pedido.numero_guia}" if getattr(pedido, "numero_guia", "") else ""

    return ft.Container(
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, badge_color)),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Row(
            [
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=9,
                    bgcolor=ft.Colors.with_opacity(0.15, badge_color),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.LOCAL_SHIPPING, color=badge_color, size=18),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    f"Remito #{pedido.nota_pedido}",
                                    size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=interfaz.texto,
                                ),
                                ft.Container(
                                    bgcolor=badge_color,
                                    border_radius=6,
                                    padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                    content=ft.Text(
                                        est.upper(),
                                        size=10,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.WHITE,
                                    ),
                                ),
                                ft.Container(
                                    bgcolor=ft.Colors.with_opacity(0.12, interfaz.texto),
                                    border_radius=6,
                                    padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                    content=ft.Text(
                                        f"{pedido.bultos} bulto(s)",
                                        size=10,
                                        weight=ft.FontWeight.BOLD,
                                        color=interfaz.texto,
                                    ),
                                ),
                            ],
                            spacing=8,
                            wrap=True,
                        ),
                        ft.Text(
                            f"Cliente: {pedido.cliente} · {pedido.logistica}{guia_txt}",
                            size=12,
                            color=interfaz.texto,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            f"Despachado por: {quien} · Fecha despacho: {fecha_desp[:16]}",
                            size=11,
                            color=interfaz.secundario,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=3,
                    expand=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def abrir_modal_confirmar_despacho_manual(
    interfaz: Any,
    pedido: Pedido,
    on_confirmado: Callable[[bool, str], None],
) -> None:
    """Abre un diálogo modal para confirmar la cantidad exacta de bultos antes de despachar manualmente."""
    if not interfaz.exigir_roles("despachador"):
        return

    campo_bultos = ft.TextField(
        label="Cantidad de bultos verificados físicamente *",
        hint_text=f"Ingrese la cantidad de bultos (esperados: {pedido.bultos})",
        value="",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
        prefix_icon=ft.Icons.INVENTORY_2,
    )
    txt_error = ft.Text("", size=12, color=ft.Colors.RED_400)

    def _confirmar(_e: ft.Event | None = None) -> None:
        if not interfaz.exigir_roles("despachador"):
            return
        raw_val = (campo_bultos.value or "").strip()
        if not raw_val.isdigit():
            txt_error.value = "Ingrese un número entero válido de bultos."
            interfaz.page.update()
            return
        cant = int(raw_val)
        usuario_nom = (
            interfaz.usuario_actual.nombre_identificador
            if interfaz.usuario_actual
            else "Despachador"
        )
        ok, msg, _ped_upd = interfaz.order_store.despachar_pedido_manual(
            pedido_id=pedido.id,
            cantidad_bultos=cant,
            usuario=usuario_nom,
        )
        if not ok:
            txt_error.value = msg
            interfaz.page.update()
            return

        try:
            interfaz.page.pop_dialog()
        except Exception:
            pass
        on_confirmado(True, msg)

    campo_bultos.on_submit = _confirmar

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.LOCAL_SHIPPING, color=ROJO),
                ft.Text(f"Confirmar despacho · Remito #{pedido.nota_pedido}", weight=ft.FontWeight.BOLD, size=15),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=440,
            content=ft.Column(
                [
                    ft.Text(f"Cliente: {pedido.cliente}", size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Text(
                        f"Logística: {pedido.logistica} · Bultos registrados en remito: {pedido.bultos}",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=8),
                    campo_bultos,
                    txt_error,
                    ft.Text(
                        "Al confirmar, el estado del pedido pasará a DESPACHADO con tu usuario y horario actual.",
                        size=11,
                        color=interfaz.secundario,
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _e: interfaz.page.pop_dialog()),
            ft.Button(
                content="Confirmar Despacho",
                icon=ft.Icons.CHECK_CIRCLE,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=_confirmar,
            ),
        ],
    )
    interfaz.page.show_dialog(dlg)


def es_fecha_hoy(fecha_str: str) -> bool:
    """Devuelve True si el prefijo YYYY-MM-DD de `fecha_str` corresponde a la fecha actual."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    return str(fecha_str or "").strip().startswith(hoy)
