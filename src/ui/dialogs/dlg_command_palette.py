"""Diálogo modal para la Búsqueda Rápida Global y Paleta de Comandos (Ctrl+K / F2)."""

from __future__ import annotations

from typing import Any
import flet as ft

from ..theme import ROJO
from ..commands import (
    buscar_clientes_palette,
    buscar_comandos,
    buscar_pedidos_palette,
    buscar_productos_palette,
    obtener_catalogo_completo_comandos,
)


def mostrar_command_palette(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Abre la paleta de comandos universal para búsqueda instantánea en todo el sistema."""
    if not interfaz.usuario_actual or not interfaz.page:
        return

    rol = getattr(interfaz.usuario_actual, "role", "consulta")
    accesos_rapidos = obtener_catalogo_completo_comandos(rol, interfaz)

    resultados_lista = ft.ListView(expand=True, spacing=6, height=360)
    indicador_estado = ft.Text("Escribe para buscar productos, clientes, pedidos o comandos...", size=11, color=interfaz.secundario)

    def ejecutar_accion(callback: Any) -> None:
        try:
            interfaz.page.pop_dialog()
        except Exception:
            pass
        if callable(callback):
            callback()

    def _renderizar_item_comando(titulo: str, desc: str, icono: Any, col: Any, cb: Any) -> ft.Control:
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
                            ft.Text(titulo, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                            ft.Text(desc, size=10, color=interfaz.secundario),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.KEYBOARD_RETURN, size=14, color=interfaz.secundario),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _renderizar_item_producto(prod: Any) -> ft.Control:
        p_code = str(prod["code"] if hasattr(prod, "__getitem__") else getattr(prod, "codigo", getattr(prod, "code", "")))
        p_name = str(prod["name"] if hasattr(prod, "__getitem__") else getattr(prod, "descripcion", getattr(prod, "name", "")))
        p_stock = int(prod["stock"] if hasattr(prod, "__getitem__") else getattr(prod, "stock_actual", getattr(prod, "stock", 0)))
        p_ubic = str(prod["ubicacion"] if hasattr(prod, "__getitem__") else getattr(prod, "ubicacion", "") or "")

        stk_color = ft.Colors.GREEN_400 if p_stock > 5 else (ft.Colors.AMBER_400 if p_stock > 0 else ft.Colors.RED_400)
        loc_txt = f" · Ubic: {p_ubic}" if p_ubic else ""

        def copiar_y_notificar(cod_val=p_code):
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
                            ft.Text(f"[{p_code}] {p_name}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                            ft.Text(f"Stock: {p_stock} un.{loc_txt}", size=10, color=stk_color),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(f"{p_stock} un.", size=10, weight=ft.FontWeight.BOLD, color=stk_color),
                        bgcolor=ft.Colors.with_opacity(0.12, stk_color),
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _renderizar_item_cliente(cli: Any) -> ft.Control:
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
                            ft.Text(f"{cod_txt}{cli.nombre}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                            ft.Text(f"Cliente activo{dir_txt}", size=10, color=interfaz.secundario),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _renderizar_item_pedido(p: Any) -> ft.Control:
        n_ped_txt = f"Pedido #{p.numero_pedido} · " if getattr(p, "numero_pedido", "") else ""
        guia_str = f" · Guía: {p.numero_guia}" if getattr(p, "numero_guia", "") else ""

        def abrir_ped(ped_obj=p):
            interfaz.page.pop_dialog()
            if rol == "operador":
                interfaz.mostrar_dialogo_editar_pedido(ped_obj, al_final=interfaz.actualizar_listas)
            else:
                interfaz.mostrar_detalle_pedido_modal(ped_obj)

        est_color = ROJO if p.estado_despacho == "armado" else (ft.Colors.BLUE_600 if p.estado_despacho == "despachado" else ft.Colors.GREEN_600)

        return ft.Container(
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
            ink=True,
            on_click=lambda _e, ped_obj=p: abrir_ped(ped_obj),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.RECEIPT_LONG, size=18, color=ft.Colors.AMBER_400),
                    ft.Column(
                        [
                            ft.Text(f"{n_ped_txt}Remito: {p.nota_pedido} ({p.cliente})", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                            ft.Text(f"{p.bultos} bulto(s) · {p.logistica}{guia_str}", size=10, color=interfaz.secundario),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(p.estado_despacho.upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        bgcolor=est_color,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def renderizar_resultados(query: str = "") -> None:
        q = (query or "").strip().lower()
        resultados_lista.controls.clear()

        # Si el campo está vacío, mostramos los accesos directos principales
        if not q:
            indicador_estado.value = "Accesos rápidos sugeridos (escribe para buscar en profundidad):"
            for titulo, desc, icono, col, cb in accesos_rapidos:
                resultados_lista.controls.append(
                    ft.Container(
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
                                        ft.Text(titulo, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                        ft.Text(desc, size=10, color=interfaz.secundario),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text("Módulo", size=9, weight=ft.FontWeight.BOLD, color=col),
                                    bgcolor=ft.Colors.with_opacity(0.12, col),
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    border_radius=4,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
            if interfaz.page:
                interfaz.page.update()
            return

        total_encontrados = 0

        # 1. Comandos / Módulos coincidentes
        comandos_match = buscar_comandos(q, accesos_rapidos)
        if comandos_match:
            resultados_lista.controls.append(
                ft.Text("ACCIONES Y MÓDULOS", size=10, weight=ft.FontWeight.BOLD, color=interfaz.secundario)
            )
            for titulo, desc, icono, col, cb in comandos_match:
                total_encontrados += 1
                resultados_lista.controls.append(_renderizar_item_comando(titulo, desc, icono, col, cb))

        # 2. Búsqueda de Productos (no aplicable a rol master por SoD)
        if rol != "master" and hasattr(interfaz, "product_store"):
            prods = buscar_productos_palette(q, getattr(interfaz, "product_store", None))
            if prods:
                resultados_lista.controls.append(
                    ft.Text("PRODUCTOS EN STOCK", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
                )
                for prod in prods:
                    total_encontrados += 1
                    resultados_lista.controls.append(_renderizar_item_producto(prod))

        # 3. Búsqueda de Clientes (no aplicable a rol master por SoD)
        if rol != "master" and hasattr(interfaz, "order_store"):
            clis = buscar_clientes_palette(q, getattr(interfaz, "order_store", None))
            if clis:
                resultados_lista.controls.append(
                    ft.Text("CLIENTES", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_400)
                )
                for cli in clis:
                    total_encontrados += 1
                    resultados_lista.controls.append(_renderizar_item_cliente(cli))

        # 4. Búsqueda de Pedidos (no aplicable a rol master por SoD)
        if rol != "master" and hasattr(interfaz, "order_store"):
            peds = buscar_pedidos_palette(q, getattr(interfaz, "order_store", None))
            if peds:
                resultados_lista.controls.append(
                    ft.Text("PEDIDOS Y REMITOS", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)
                )
                for p in peds:
                    total_encontrados += 1
                    resultados_lista.controls.append(_renderizar_item_pedido(p))

        if total_encontrados == 0:
            resultados_lista.controls.append(
                ft.Container(
                    padding=25,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.SEARCH_OFF, size=32, color=interfaz.secundario),
                            ft.Text(f"No se encontraron resultados para '{query}'.", size=12, color=interfaz.secundario),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                )
            )
            indicador_estado.value = "Sin coincidencias."
        else:
            indicador_estado.value = f"Mostrando {total_encontrados} resultado(s) encontrado(s):"

        if interfaz.page:
            interfaz.page.update()

    campo_busqueda = ft.TextField(
        hint_text="Buscar productos, clientes, remitos o acciones...",
        prefix_icon=ft.Icons.SEARCH,
        autofocus=True,
        dense=True,
        on_change=lambda e: renderizar_resultados(e.control.value),
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.TERMINAL, color=ROJO, size=20),
                ft.Text("Menú Rápido y Buscador Global", weight=ft.FontWeight.BOLD, size=15),
                ft.Container(
                    content=ft.Text("F2 / Ctrl+K", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ROJO,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=ft.Container(
            width=580,
            content=ft.Column(
                [
                    campo_busqueda,
                    indicador_estado,
                    ft.Divider(height=10),
                    resultados_lista,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar (Esc)", lambda _e: interfaz.page.pop_dialog()),
        ],
    )

    renderizar_resultados("")
    interfaz.page.show_dialog(dialogo)
