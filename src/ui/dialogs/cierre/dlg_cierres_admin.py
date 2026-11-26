"""Diálogos para supervisión y auditoría de cierres de operarios por administración."""

from __future__ import annotations

from typing import Any

import flet as ft

from ...design import grilla_tarjetas_responsiva
from ...theme import ROJO
from .cierres_admin_cards import (
    construir_chip_metrica_cierre,
    construir_estado_vacio_cierres,
    construir_tarjeta_cierre_admin,
    mostrar_detalle_pedidos_cierre,
)


def _filtrar_cierres(cierres: list[Any], filtro: str) -> list[Any]:
    """Filtra cierres por número, operario, fecha o resumen de pedidos."""
    q = (filtro or "").strip().lower()
    if not q:
        return cierres
    return [
        c
        for c in cierres
        if (
            q in str(c.id).lower()
            or q in f"#{c.id}".lower()
            or q in (c.usuario or "").lower()
            or q in (c.created_at or "").lower()
            or q in (c.resumen_pedidos or "").lower()
        )
    ]


def mostrar_dialogo_cierres_operarios(interfaz: Any) -> None:
    """Abre el panel para que el administrador visualice en orden descendente los cierres creados por los operarios."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("administrador", "master"):
        interfaz.notificar("La consulta de cierres de operarios es exclusiva del rol administrador.")
        return

    todos_los_cierres = interfaz.order_store.listar_cierres(limit=250)
    todos_los_cierres.sort(key=lambda c: c.id, reverse=True)

    lista_cierres = ft.ListView(expand=True, spacing=8)
    total_cierres_lbl = ft.Text("0", weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto)
    total_pedidos_lbl = ft.Text("0", weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto)
    total_unidades_lbl = ft.Text("0", weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto)

    def renderizar_lista(filtro: str = "") -> None:
        lista_cierres.controls.clear()
        filtrados = _filtrar_cierres(todos_los_cierres, filtro)

        total_cierres_lbl.value = str(len(filtrados))
        total_pedidos_lbl.value = str(sum(c.cantidad_pedidos for c in filtrados))
        total_unidades_lbl.value = str(sum(c.articulos_totales for c in filtrados))

        if not filtrados:
            lista_cierres.controls.append(
                construir_estado_vacio_cierres(interfaz, tiene_filtro=bool((filtro or "").strip()))
            )
        else:
            for c in filtrados:
                lista_cierres.controls.append(
                    construir_tarjeta_cierre_admin(
                        interfaz,
                        c,
                        on_ver_pedidos=lambda cierre_obj: mostrar_detalle_pedidos_cierre(interfaz, cierre_obj),
                    )
                )

        if interfaz.page:
            interfaz.page.update()

    filtro_input = ft.TextField(
        hint_text="Filtrar por operario, # cierre o fecha...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
        border_radius=8,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        on_change=lambda e: renderizar_lista(e.control.value),
    )

    def recargar_cierres(_e: ft.Event) -> None:
        nonlocal todos_los_cierres
        todos_los_cierres = interfaz.order_store.listar_cierres(limit=250)
        todos_los_cierres.sort(key=lambda c: c.id, reverse=True)
        renderizar_lista(filtro_input.value)

    boton_recargar = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip="Actualizar lista de cierres",
        icon_color=interfaz.texto,
        on_click=recargar_cierres,
    )

    renderizar_lista("")

    barra_metricas = grilla_tarjetas_responsiva(
        [
            construir_chip_metrica_cierre(interfaz, "Total Cierres", total_cierres_lbl, ft.Icons.FACT_CHECK),
            construir_chip_metrica_cierre(interfaz, "Pedidos Consolidados", total_pedidos_lbl, ft.Icons.INVENTORY_2),
            construir_chip_metrica_cierre(interfaz, "Unidades Descontadas", total_unidades_lbl, ft.Icons.CHECK_CIRCLE),
            ft.Container(
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.ARROW_DOWNWARD, size=16, color=ft.Colors.GREEN_400),
                        ft.Text(
                            "Orden: Descendente",
                            size=11,
                            weight=ft.FontWeight.W_500,
                            color=interfaz.secundario,
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=4,
                ),
            ),
        ],
        interfaz=interfaz,
        compacto=True,
        spacing=8,
        run_spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    cuerpo = ft.Column(
        [
            barra_metricas,
            ft.Row([filtro_input, boton_recargar], spacing=8),
            ft.Divider(height=6, color=interfaz.borde),
            ft.Container(content=lista_cierres, expand=True),
        ],
        spacing=10,
        expand=True,
    )

    ancho_modal = (
        interfaz.ancho_adaptable(800)
        if hasattr(interfaz, "ancho_adaptable")
        else (420 if getattr(interfaz, "es_pantalla_movil", False) else 800)
    )
    alto_modal = (
        interfaz.alto_adaptable(540)
        if hasattr(interfaz, "alto_adaptable")
        else (520 if getattr(interfaz, "es_pantalla_movil", False) else 540)
    )

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.FACT_CHECK, color=ROJO, size=24),
                ft.Column(
                    [
                        ft.Text(
                            "Cierres de Operarios (Descendente)",
                            weight=ft.FontWeight.BOLD,
                            size=16,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            "Control y auditoría de jornadas finalizadas por los operarios",
                            size=11,
                            color=interfaz.secundario,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(width=ancho_modal, height=alto_modal, content=cuerpo),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
