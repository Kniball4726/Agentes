"""Tarjetas y constructores de lista para el diálogo de Cierre de Mercado (ML, Full e Historial)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import flet as ft

from ...theme import ROJO


def renderizar_lista_pedidos_mercado(
    *,
    lista_ctrl: ft.ListView,
    resumen_ctrl: ft.Text,
    seleccionados: dict[int, bool],
    pedidos: list[Any],
    interfaz: Any,
    es_oscuro: bool,
    es_full: bool,
    on_cambio_seleccion: Callable[[], None],
) -> None:
    """Puebla una lista de pedidos pendientes de Mercado Libre o Mercado Envíos Full."""
    lista_ctrl.controls.clear()
    seleccionados.clear()

    if not pedidos:
        mensaje_vacio = (
            "No hay lotes de Mercado Envíos Full pendientes de cerrar para el pallet."
            if es_full
            else "No hay paquetes de Mercado Libre pendientes de colecta en esta tanda."
        )
        resumen_vacio = (
            "Sin lotes pendientes de Mercado Envíos Full."
            if es_full
            else "Sin despachos pendientes de Mercado Libre."
        )
        lista_ctrl.controls.append(
            ft.Container(
                padding=16,
                border_radius=8,
                bgcolor=interfaz.fondo_acento if es_oscuro else ft.Colors.GREY_100,
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=24),
                        ft.Text(mensaje_vacio, size=12, color=interfaz.texto, expand=True),
                    ],
                    spacing=10,
                ),
            )
        )
        resumen_ctrl.value = resumen_vacio
        return

    badge_icono = ft.Icons.LOCAL_SHIPPING if es_full else ft.Icons.STOREFRONT
    badge_texto = "Mercado Full" if es_full else "Mercado Libre"
    badge_color = ft.Colors.AMBER_700 if es_full else ft.Colors.BLUE_500

    for p in pedidos:
        seleccionados[p.id] = True

        def _on_check(e: ft.Event, pid: int = p.id) -> None:
            seleccionados[pid] = bool(e.control.value)
            on_cambio_seleccion()

        sub_ref = f"· Archivo: {p.nombre_archivo}" if es_full else f"· {p.cliente}"
        meta_izq = f"Fecha carga: {p.created_at[:16]}" if es_full else f"Bultos: {p.bultos}"
        hora_o_fecha = p.created_at[5:10] if es_full else (p.created_at[11:16] if len(p.created_at) >= 16 else "")

        lista_ctrl.controls.append(
            ft.Container(
                bgcolor=interfaz.fondo_acento if es_oscuro else ft.Colors.GREY_50,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=8,
                content=ft.Row(
                    [
                        ft.Checkbox(value=True, on_change=_on_check),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            content=ft.Row(
                                                [
                                                    ft.Icon(badge_icono, size=12, color=ft.Colors.WHITE),
                                                    ft.Text(badge_texto, size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                                ],
                                                spacing=4,
                                            ),
                                            bgcolor=badge_color,
                                            border_radius=4,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        ),
                                        ft.Text(f"#{p.nota_pedido}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                        ft.Text(sub_ref, size=11, color=interfaz.secundario, expand=True, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                    spacing=6,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(meta_izq, size=11, color=interfaz.secundario),
                                        ft.Text(f"Descuento: {p.resumen_items}", size=11, color=ft.Colors.GREEN_400, weight=ft.FontWeight.W_500),
                                        ft.Text(f"Armador: {p.armador}", size=11, color=interfaz.secundario),
                                    ],
                                    spacing=10,
                                ),
                            ],
                            spacing=3,
                            expand=True,
                        ),
                        ft.Text(hora_o_fecha, size=11, color=interfaz.secundario),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )


def renderizar_lista_historial_mercado(
    *,
    lista_historial: ft.ListView,
    cierres: list[Any],
    interfaz: Any,
    es_oscuro: bool,
) -> None:
    """Renderiza tarjetas del historial de cierres emitidos para Mercado Libre y Full."""
    lista_historial.controls.clear()
    if not cierres:
        lista_historial.controls.append(
            ft.Text("Aún no se han registrado cierres de Mercado.", size=12, color=interfaz.secundario)
        )
        return

    carpeta_desc = getattr(interfaz.menu, "carpeta_descuentos", Path("."))
    for c in cierres:
        pdf_path = carpeta_desc / c.archivo_pdf if c.archivo_pdf else None
        existe_pdf = pdf_path is not None and pdf_path.exists()
        es_full = "FULL" in c.tipo_mercado.upper()
        icono_c = ft.Icons.LOCAL_SHIPPING if es_full else ft.Icons.STOREFRONT
        badge_color = ft.Colors.AMBER_700 if es_full else ft.Colors.BLUE_500
        tipo_label = "MERCADO FULL" if es_full else "MERCADO LIBRE"

        btn_opciones = ft.IconButton(
            icon=ft.Icons.PRINT,
            tooltip="Imprimir o Descargar comprobante en Windows",
            icon_color=ROJO,
            on_click=(lambda _e, r=pdf_path: interfaz.mostrar_opciones_documento(r)) if existe_pdf else None,
        )

        lista_historial.controls.append(
            ft.Container(
                bgcolor=interfaz.fondo_acento if es_oscuro else ft.Colors.GREY_50,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=8,
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Container(
                                            content=ft.Row(
                                                [
                                                    ft.Icon(icono_c, size=11, color=ft.Colors.WHITE),
                                                    ft.Text(tipo_label, size=9, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                                ],
                                                spacing=3,
                                            ),
                                            bgcolor=badge_color,
                                            border_radius=4,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        ),
                                        ft.Text(f"Cierre #{c.id}", weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                                        ft.Text(f"{c.cantidad_pedidos} despachos ({c.articulos_totales} un.)", size=11, color=ft.Colors.GREEN_400),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(
                                    f"Responsable: {c.usuario} · Fecha: {c.created_at[:16]} · Archivo: {c.archivo_pdf or 'N/A'}",
                                    size=10,
                                    color=interfaz.secundario,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        btn_opciones,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )
