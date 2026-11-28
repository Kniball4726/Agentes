"""Diálogo modal para la Búsqueda Rápida Global y Paleta de Comandos (Ctrl+K / F2)."""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable

import flet as ft

from ..commands import (
    buscar_clientes_palette,
    buscar_comandos,
    buscar_pedidos_palette,
    buscar_productos_palette,
    obtener_catalogo_completo_comandos,
)
from ..components.debounce import Debouncer
from ..design import colores_de, tono_legible
from ..theme import FUENTE_MENU, FUENTE_MENU_BOLD, ROJO, estilo_texto_menu

logger = logging.getLogger("stockagent.ui.palette")


def _crear_item_acceso_rapido(
    interfaz: Any,
    titulo: str,
    desc: str,
    icono: Any,
    col: Any,
    cb: Any,
    ejecutar_accion: Callable[[Any], None],
) -> ft.Control:
    return ft.Container(
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        ink=True,
        on_click=lambda _e, fn=cb: ejecutar_accion(fn),
        content=ft.Row(
            [
                ft.Icon(icono, color=col, size=20),
                ft.Column(
                    [
                        ft.Text(titulo, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto, font_family=FUENTE_MENU_BOLD),
                        ft.Text(desc, size=10, color=interfaz.secundario, font_family=FUENTE_MENU),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Text("Módulo", size=9, weight=ft.FontWeight.BOLD, color=col, font_family=FUENTE_MENU_BOLD),
                    bgcolor=ft.Colors.with_opacity(0.12, col),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _crear_item_comando(
    interfaz: Any,
    titulo: str,
    desc: str,
    icono: Any,
    col: Any,
    cb: Any,
    ejecutar_accion: Callable[[Any], None],
) -> ft.Control:
    return ft.Container(
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        ink=True,
        on_click=lambda _e, fn=cb: ejecutar_accion(fn),
        content=ft.Row(
            [
                ft.Icon(icono, color=col, size=18),
                ft.Column(
                    [
                        ft.Text(titulo, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto, font_family=FUENTE_MENU_BOLD),
                        ft.Text(desc, size=10, color=interfaz.secundario, font_family=FUENTE_MENU),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Icon(ft.Icons.KEYBOARD_RETURN, size=14, color=interfaz.secundario),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _crear_item_producto(interfaz: Any, colores: Any, prod: Any) -> ft.Control:
    p_code = str(prod["code"] if hasattr(prod, "__getitem__") else getattr(prod, "codigo", getattr(prod, "code", "")))
    p_name = str(prod["name"] if hasattr(prod, "__getitem__") else getattr(prod, "descripcion", getattr(prod, "name", "")))
    p_stock = int(prod["stock"] if hasattr(prod, "__getitem__") else getattr(prod, "stock_actual", getattr(prod, "stock", 0)))
    p_ubic = str(prod["ubicacion"] if hasattr(prod, "__getitem__") else getattr(prod, "ubicacion", "") or "")

    stk_color = colores.exito if p_stock > 5 else (colores.advertencia if p_stock > 0 else colores.error)
    loc_txt = f" · Ubic: {p_ubic}" if p_ubic else ""

    def copiar_y_notificar(cod_val: str = p_code) -> None:
        if hasattr(interfaz, "copiar_al_portapapeles"):
            interfaz.copiar_al_portapapeles(cod_val)
        elif hasattr(interfaz.page, "set_clipboard"):
            interfaz.page.set_clipboard(cod_val)
        interfaz.notificar(f"Código copiado al portapapeles: {cod_val}")

    return ft.Container(
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        ink=True,
        tooltip=f"Clic para copiar código [{p_code}]",
        on_click=lambda _e, cod=p_code: copiar_y_notificar(cod),
        content=ft.Row(
            [
                ft.Icon(ft.Icons.INVENTORY_2, size=18, color=ft.Colors.BLUE_400),
                ft.Column(
                    [
                        ft.Text(f"[{p_code}] {p_name}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto, font_family=FUENTE_MENU_BOLD),
                        ft.Text(f"Stock: {p_stock} un.{loc_txt}", size=10, color=stk_color, font_family=FUENTE_MENU),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Text(f"{p_stock} un.", size=10, weight=ft.FontWeight.BOLD, color=stk_color, font_family=FUENTE_MENU_BOLD),
                    bgcolor=ft.Colors.with_opacity(0.12, stk_color),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _crear_item_cliente(interfaz: Any, cli: Any, ejecutar_accion: Callable[[Any], None]) -> ft.Control:
    dir_txt = f" · {cli.direccion}" if getattr(cli, "direccion", "") else ""
    cod_txt = f"[{cli.codigo}] " if getattr(cli, "codigo", "") else ""
    return ft.Container(
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        ink=True,
        on_click=lambda _e: ejecutar_accion(interfaz.mostrar_gestion_clientes),
        content=ft.Row(
            [
                ft.Icon(ft.Icons.PEOPLE_ALT, size=18, color=ft.Colors.TEAL_400),
                ft.Column(
                    [
                        ft.Text(f"{cod_txt}{cli.nombre}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto, font_family=FUENTE_MENU_BOLD),
                        ft.Text(f"Cliente activo{dir_txt}", size=10, color=interfaz.secundario, font_family=FUENTE_MENU),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _crear_item_pedido(interfaz: Any, rol: str, pedido: Any) -> ft.Control:
    n_ped_txt = f"Pedido #{pedido.numero_pedido} · " if getattr(pedido, "numero_pedido", "") else ""
    guia_str = f" · Guía: {pedido.numero_guia}" if getattr(pedido, "numero_guia", "") else ""

    def abrir_ped(ped_obj: Any = pedido) -> None:
        interfaz.page.pop_dialog()
        if rol == "despachador":
            interfaz.mostrar_modulo_despacho()
        elif rol == "operador":
            interfaz.mostrar_dialogo_editar_pedido(ped_obj, al_final=interfaz.actualizar_listas)
        else:
            interfaz.mostrar_detalle_pedido_modal(ped_obj)

    est_color = ROJO if pedido.estado_despacho == "armado" else (
        ft.Colors.BLUE_600 if pedido.estado_despacho == "despachado" else ft.Colors.GREEN_600
    )
    return ft.Container(
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        ink=True,
        on_click=lambda _e, ped_obj=pedido: abrir_ped(ped_obj),
        content=ft.Row(
            [
                ft.Icon(ft.Icons.RECEIPT_LONG, size=18, color=ft.Colors.AMBER_400),
                ft.Column(
                    [
                        ft.Text(f"{n_ped_txt}Remito: {pedido.nota_pedido} ({pedido.cliente})", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto, font_family=FUENTE_MENU_BOLD),
                        ft.Text(f"{pedido.bultos} bulto(s) · {pedido.logistica}{guia_str}", size=10, color=interfaz.secundario, font_family=FUENTE_MENU),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Text(pedido.estado_despacho.upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, font_family=FUENTE_MENU_BOLD),
                    bgcolor=est_color,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _crear_placeholder_sin_resultados(interfaz: Any, query: str) -> ft.Control:
    return ft.Container(
        padding=25,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Icon(ft.Icons.SEARCH_OFF, size=32, color=interfaz.secundario),
                ft.Text(f"No se encontraron resultados para '{query}'.", size=12, color=interfaz.secundario, font_family=FUENTE_MENU),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
    )


def _crear_titulo_palette() -> ft.Row:
    return ft.Row(
        [
            ft.Icon(ft.Icons.TERMINAL, color=ROJO, size=20),
            ft.Text("Menú Rápido y Buscador Global", weight=ft.FontWeight.BOLD, size=15, font_family=FUENTE_MENU_BOLD),
            ft.Container(
                content=ft.Text("F2 / Ctrl+K", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, font_family=FUENTE_MENU_BOLD),
                bgcolor=ROJO,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
            ),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _poblar_resultados_busqueda(
    *,
    interfaz: Any,
    colores: Any,
    rol: str,
    es_oscuro: bool,
    accesos_rapidos: list[Any],
    resultados_lista: ft.ListView,
    indicador_estado: ft.Text,
    query: str,
    ejecutar_accion: Callable[[Any], None],
) -> Any:
    """Construye los controles de resultado para `query` y devuelve la primera acción ejecutable."""
    q = (query or "").strip().lower()
    resultados_lista.controls.clear()
    primer_accion: Any = None

    if not q:
        indicador_estado.value = "Accesos rápidos sugeridos (escribe para buscar en profundidad):"
        for titulo, desc, icono, col, cb in accesos_rapidos:
            if primer_accion is None:
                primer_accion = cb
            resultados_lista.controls.append(
                _crear_item_acceso_rapido(interfaz, titulo, desc, icono, col, cb, ejecutar_accion)
            )
        return primer_accion

    total_encontrados = 0

    comandos_match = buscar_comandos(q, accesos_rapidos)
    if comandos_match:
        resultados_lista.controls.append(
            ft.Text("ACCIONES Y MÓDULOS", size=10, weight=ft.FontWeight.BOLD, color=interfaz.secundario, font_family=FUENTE_MENU_BOLD)
        )
        for titulo, desc, icono, col, cb in comandos_match:
            if primer_accion is None:
                primer_accion = cb
            total_encontrados += 1
            resultados_lista.controls.append(_crear_item_comando(interfaz, titulo, desc, icono, col, cb, ejecutar_accion))

    if rol not in ("master", "despachador") and hasattr(interfaz, "product_store"):
        prods = buscar_productos_palette(q, getattr(interfaz, "product_store", None))
        if prods:
            resultados_lista.controls.append(
                ft.Text("PRODUCTOS EN STOCK", size=10, weight=ft.FontWeight.BOLD, color=tono_legible("BLUE", es_oscuro), font_family=FUENTE_MENU_BOLD)
            )
            for prod in prods:
                total_encontrados += 1
                resultados_lista.controls.append(_crear_item_producto(interfaz, colores, prod))

    if rol not in ("master", "despachador") and hasattr(interfaz, "order_store"):
        clis = buscar_clientes_palette(q, getattr(interfaz, "order_store", None))
        if clis:
            resultados_lista.controls.append(
                ft.Text("CLIENTES", size=10, weight=ft.FontWeight.BOLD, color=tono_legible("TEAL", es_oscuro), font_family=FUENTE_MENU_BOLD)
            )
            for cli in clis:
                if primer_accion is None:
                    primer_accion = interfaz.mostrar_gestion_clientes
                total_encontrados += 1
                resultados_lista.controls.append(_crear_item_cliente(interfaz, cli, ejecutar_accion))

    if rol != "master" and hasattr(interfaz, "order_store"):
        peds = buscar_pedidos_palette(q, getattr(interfaz, "order_store", None))
        if peds:
            resultados_lista.controls.append(
                ft.Text("PEDIDOS Y REMITOS", size=10, weight=ft.FontWeight.BOLD, color=tono_legible("AMBER", es_oscuro), font_family=FUENTE_MENU_BOLD)
            )
            for p in peds:
                total_encontrados += 1
                resultados_lista.controls.append(_crear_item_pedido(interfaz, rol, p))

    if total_encontrados == 0:
        resultados_lista.controls.append(_crear_placeholder_sin_resultados(interfaz, query))
        indicador_estado.value = "Sin coincidencias."
    else:
        indicador_estado.value = f"Mostrando {total_encontrados} resultado(s) encontrado(s):"
    return primer_accion


def mostrar_command_palette(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre la paleta de comandos universal para búsqueda instantánea en todo el sistema."""
    if not interfaz.usuario_actual or not interfaz.page:
        return
    if getattr(interfaz, "_command_palette_abierto", False) is True:
        return
    interfaz._command_palette_abierto = True

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    colores = colores_de(interfaz)
    rol = getattr(interfaz.usuario_actual, "role", "consulta")
    accesos_rapidos = obtener_catalogo_completo_comandos(rol, interfaz)
    primer_accion: list[Any] = [None]

    resultados_lista = ft.ListView(expand=True, spacing=6, height=360)
    indicador_estado = ft.Text(
        "Escribe para buscar productos, clientes, pedidos o comandos...",
        size=11,
        color=interfaz.secundario,
        font_family=FUENTE_MENU,
    )

    def _cerrar_palette() -> None:
        interfaz._command_palette_abierto = False
        try:
            interfaz.page.pop_dialog()
        except Exception as exc:
            logger.debug("No se pudo cerrar el diálogo de paleta: %s", exc)

    def ejecutar_accion(callback: Any) -> None:
        _cerrar_palette()
        if callable(callback):
            callback()

    def renderizar_resultados(query: str = "") -> None:
        primer_accion[0] = _poblar_resultados_busqueda(
            interfaz=interfaz,
            colores=colores,
            rol=rol,
            es_oscuro=es_oscuro,
            accesos_rapidos=accesos_rapidos,
            resultados_lista=resultados_lista,
            indicador_estado=indicador_estado,
            query=query,
            ejecutar_accion=ejecutar_accion,
        )
        if interfaz.page:
            interfaz.page.update()

    es_test = getattr(interfaz, "_is_mock", False) or "pytest" in sys.modules
    debouncer_cmd = Debouncer(0.0 if es_test else 0.2)

    def _on_submit_busqueda(e: ft.Event) -> None:
        debouncer_cmd.cancel()
        renderizar_resultados(e.control.value)
        if callable(primer_accion[0]):
            ejecutar_accion(primer_accion[0])

    campo_busqueda = ft.TextField(
        hint_text="Buscar productos, clientes, remitos o acciones...",
        prefix_icon=ft.Icons.SEARCH,
        autofocus=True,
        dense=True,
        text_style=estilo_texto_menu(),
        hint_style=estilo_texto_menu(),
        on_change=lambda e: debouncer_cmd.debounce(lambda val=e.control.value: renderizar_resultados(val)),
        on_submit=_on_submit_busqueda,
    )

    btn_cerrar_palette = interfaz.boton_dialogo("Cerrar (Esc)", lambda _e: _cerrar_palette())
    if isinstance(getattr(btn_cerrar_palette, "style", None), ft.ButtonStyle):
        btn_cerrar_palette.style = btn_cerrar_palette.style.copy(text_style=estilo_texto_menu("medium"))

    w_calc = interfaz.ancho_adaptable(580) if hasattr(interfaz, "ancho_adaptable") else 580
    ancho_dlg = int(w_calc) if isinstance(w_calc, (int, float)) else 580
    dialogo = ft.AlertDialog(
        modal=True,
        on_dismiss=lambda _e: setattr(interfaz, "_command_palette_abierto", False),
        title=_crear_titulo_palette(),
        content=ft.Container(
            width=ancho_dlg,
            content=ft.Column([campo_busqueda, indicador_estado, ft.Divider(height=10), resultados_lista], tight=True, spacing=8),
        ),
        actions=[btn_cerrar_palette],
    )

    renderizar_resultados("")
    interfaz.page.show_dialog(dialogo)
