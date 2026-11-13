"""Diálogo interactivo para escaneo y recepción de mercadería de fábrica."""

from __future__ import annotations

import sys
from typing import Any

import flet as ft

from ...stock_manager import StockManager as _DefaultStockManager
from ..audio_feedback import emitir_tono_error, emitir_tono_exito, normalizar_codigo_lector
from ..theme import ROJO
from ._shared import safe_focus
from .ingreso_fabrica_archivo import (
    construir_tab_archivo_fabrica,
    registrar_ingreso_escaner,
)


def _get_stock_manager():
    """Devuelve StockManager vigente (respetando patches en dlg_stock_ops o src.flet_gui)."""
    mod_ops = sys.modules.get("src.ui.dialogs.dlg_stock_ops")
    if mod_ops and hasattr(mod_ops, "_get_stock_manager"):
        return mod_ops._get_stock_manager()
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def _buscar_sku_fabrica(stock_manager: Any, codigo_limpio: str) -> tuple[str | None, str | None, int]:
    """Busca un producto en SQLite o catálogo en memoria para ingreso de fábrica."""
    prod_encontrado = None
    if hasattr(stock_manager, "product_store"):
        try:
            prod_encontrado = stock_manager.product_store.find_product_by_code_or_barcode(codigo_limpio)
            if not prod_encontrado:
                res_busq = stock_manager.product_store.buscar_productos(codigo_limpio, limite=1)
                if res_busq:
                    prod_encontrado = res_busq[0]
        except Exception:
            pass

    if prod_encontrado:
        return (
            str(prod_encontrado["code"]).strip(),
            str(prod_encontrado["name"]).strip(),
            int(prod_encontrado["stock"]),
        )
    if codigo_limpio in stock_manager.catalogo:
        _, nombre, stk = stock_manager.catalogo[codigo_limpio]
        return codigo_limpio, nombre, stk
    for k, v in stock_manager.catalogo.items():
        if k.upper() == codigo_limpio.upper():
            _, nombre, stk = v
            return k, nombre, stk
    return None, None, 0


def mostrar_ingreso_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para escanear mercadería de fábrica o ajustar stock."""
    if not interfaz.exigir_roles("operador", "administrador", "picker"):
        return

    es_operador = getattr(interfaz.usuario_actual, "role", None) == "operador"
    stock_manager = _get_stock_manager()(interfaz.menu.ruta_excel_base)

    modo_sobrescribir = ft.Checkbox(
        label="Sobrescribir stock (establece el valor exacto indicado)",
        value=False,
    )
    items_escaneados: dict[str, int] = {}

    input_codigo = ft.TextField(
        label="Escanear código de barras o SKU (Pistola lectora)",
        hint_text="Pasa la pistola lectora o escribe el código y presiona Enter...",
        prefix_icon=ft.Icons.BARCODE_READER,
        autofocus=True,
        expand=True,
        dense=True,
    )
    input_cant = ft.TextField(
        value="12",
        width=60,
        dense=True,
        text_align=ft.TextAlign.CENTER,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    def ajustar_cant_input(delta: int) -> None:
        try:
            val = int(input_cant.value or "12")
        except ValueError:
            val = 12
        input_cant.value = str(max(1, val + delta))
        interfaz.page.update()

    def fijar_cant_input(val: int) -> None:
        input_cant.value = str(val)
        safe_focus(interfaz, input_codigo)
        interfaz.page.update()

    fila_multiplos = ft.Row(
        [
            ft.Text("Lotes x12:", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
            *[
                ft.Button(
                    str(m),
                    style=ft.ButtonStyle(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        color=ft.Colors.WHITE if interfaz.modo_oscuro else ft.Colors.BLACK87,
                        bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_200,
                    ),
                    on_click=lambda _e, val=m: fijar_cant_input(val),
                )
                for m in (12, 24, 36, 48, 60, 120)
            ],
        ],
        spacing=6,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    texto_feedback = ft.Text(
        "Listo para recibir mercadería. Escanea los productos o bultos de fábrica.",
        size=11,
        color=interfaz.secundario,
    )
    lista_escaneo_view = ft.ListView(expand=True, spacing=4, height=220)
    resumen_escaneo_texto = ft.Text(
        "0 productos escaneados (0 unidades a ingresar)",
        size=12,
        weight=ft.FontWeight.BOLD,
        color=interfaz.secundario,
    )
    btn_confirmar_escaner = ft.Button(
        "Confirmar Ingreso a Depósito",
        icon=ft.Icons.CHECK_CIRCLE,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    def _ajustar_sku(sku: str, delta: int) -> None:
        nueva = items_escaneados.get(sku, 1) + delta
        if nueva <= 0:
            items_escaneados.pop(sku, None)
        else:
            items_escaneados[sku] = nueva
        refrescar_vista_escaner()
        safe_focus(interfaz, input_codigo)
        interfaz.page.update()

    def _eliminar_sku(sku: str) -> None:
        items_escaneados.pop(sku, None)
        refrescar_vista_escaner()
        safe_focus(interfaz, input_codigo)
        interfaz.page.update()

    def refrescar_vista_escaner() -> None:
        lista_escaneo_view.controls.clear()
        if not items_escaneados:
            lista_escaneo_view.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=28,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.QR_CODE_SCANNER, size=36, color=interfaz.secundario),
                            ft.Text(
                                "Pasa la pistola sobre el código de barras o escribe el SKU para ingresar mercadería.",
                                color=interfaz.secundario,
                                size=12,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                )
            )
            resumen_escaneo_texto.value = "0 productos escaneados (0 unidades a ingresar)"
            resumen_escaneo_texto.color = interfaz.secundario
            btn_confirmar_escaner.disabled = True
            return

        total_unidades = sum(items_escaneados.values())
        for sku, cant in list(items_escaneados.items()):
            prod = None
            if hasattr(stock_manager, "product_store"):
                try:
                    prod = stock_manager.product_store.get_product(sku)
                except Exception:
                    pass
            nom = prod["name"] if prod else stock_manager.catalogo.get(sku, ("", "Producto", 0))[1]
            stk_act = int(prod["stock"]) if prod else stock_manager.catalogo.get(sku, ("", "", 0))[2]
            nuevo_stk = stk_act + cant

            lista_escaneo_view.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                    border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row([ft.Text(f"[{sku}]", weight=ft.FontWeight.BOLD, size=11, color=ROJO), ft.Text(nom, size=11, weight=ft.FontWeight.BOLD, expand=True, no_wrap=True)], spacing=6),
                                    ft.Text(f"Stock actual: {stk_act} → Con ingreso: {nuevo_stk} (+{cant} un.)", size=10, color=ft.Colors.GREEN_400 if nuevo_stk > stk_act else interfaz.secundario),
                                ],
                                expand=True,
                                spacing=2,
                            ),
                            ft.Row(
                                [
                                    ft.IconButton(icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_DOWN, icon_size=18, tooltip="Restar 12 un. (-12)", on_click=lambda _e, s=sku: _ajustar_sku(s, -12)),
                                    ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_size=18, tooltip="Restar 1 un. (-1)", on_click=lambda _e, s=sku: _ajustar_sku(s, -1)),
                                    ft.Text(f"{cant} un.", weight=ft.FontWeight.BOLD, size=12),
                                    ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, icon_size=18, tooltip="Sumar 1 un. (+1)", on_click=lambda _e, s=sku: _ajustar_sku(s, 1)),
                                    ft.IconButton(icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_UP, icon_size=18, tooltip="Sumar 12 un. (+12)", on_click=lambda _e, s=sku: _ajustar_sku(s, 12)),
                                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=18, icon_color=ft.Colors.RED_400, tooltip="Quitar producto", on_click=lambda _e, s=sku: _eliminar_sku(s)),
                                ],
                                spacing=0,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        resumen_escaneo_texto.value = (
            f"📥 {len(items_escaneados)} producto{'s' if len(items_escaneados) != 1 else ''} "
            f"({total_unidades} unidades totales a ingresar a stock)"
        )
        resumen_escaneo_texto.color = interfaz.texto
        btn_confirmar_escaner.disabled = False

    def procesar_lectura_codigo() -> None:
        raw = (input_codigo.value or "").strip()
        if not raw:
            return
        codigo_limpio = normalizar_codigo_lector(raw) or raw
        try:
            cant_a_sumar = max(1, int(input_cant.value or "12"))
        except ValueError:
            cant_a_sumar = 12

        sku_final, nombre_final, stk_actual = _buscar_sku_fabrica(stock_manager, codigo_limpio)
        if not sku_final:
            texto_feedback.value = f"❌ Código '{codigo_limpio}' no encontrado en el catálogo."
            texto_feedback.color = ft.Colors.RED_400
            emitir_tono_error()
            if hasattr(interfaz, "reproducir_sonido"):
                interfaz.reproducir_sonido("error")
            input_codigo.value = ""
            safe_focus(interfaz, input_codigo)
            interfaz.page.update()
            return

        nueva_cant = items_escaneados.get(sku_final, 0) + cant_a_sumar
        items_escaneados[sku_final] = nueva_cant
        texto_feedback.value = (
            f"✅ [{sku_final}] {nombre_final} (+{cant_a_sumar} un.) | "
            f"Stock actual: {stk_actual} → Con ingreso: {stk_actual + nueva_cant}"
        )
        texto_feedback.color = ft.Colors.GREEN_400
        emitir_tono_exito()
        if hasattr(interfaz, "reproducir_sonido"):
            interfaz.reproducir_sonido("exito")

        input_codigo.value = ""
        refrescar_vista_escaner()
        safe_focus(interfaz, input_codigo)
        interfaz.page.update()

    input_codigo.on_submit = lambda _e: procesar_lectura_codigo()

    def limpiar_escaner(_e: ft.Event | None = None) -> None:
        items_escaneados.clear()
        texto_feedback.value = "Lista de ingreso vaciada."
        texto_feedback.color = interfaz.secundario
        input_codigo.value = ""
        input_cant.value = "12"
        refrescar_vista_escaner()
        safe_focus(interfaz, input_codigo)
        interfaz.page.update()

    def guardar_escaner(_e: ft.Event | None = None, sobrescribir: bool = False) -> None:
        if not items_escaneados:
            interfaz.notificar("Debes escanear al menos un producto antes de confirmar.")
            return
        interfaz.page.pop_dialog()
        registrar_ingreso_escaner(interfaz, items_escaneados, sobrescribir)

    btn_confirmar_escaner.on_click = lambda _e: guardar_escaner(_e, sobrescribir=False)

    vista_escaner = ft.Container(
        padding=10,
        content=ft.Column(
            [
                fila_multiplos,
                ft.Row(
                    [
                        ft.Text("Cantidad por lectura:", size=11, weight=ft.FontWeight.BOLD),
                        ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_size=20, tooltip="Restar 1 unidad (-1)", on_click=lambda _e: ajustar_cant_input(-1)),
                        input_cant,
                        ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, icon_size=20, tooltip="Sumar 1 unidad (+1)", on_click=lambda _e: ajustar_cant_input(1)),
                        ft.Text("unidades", size=11, color=interfaz.secundario),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                ft.Row(
                    [
                        input_codigo,
                        ft.Button("Ingresar", icon=ft.Icons.ADD, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=lambda _e: procesar_lectura_codigo()),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                texto_feedback,
                ft.Divider(height=10),
                ft.Text("Productos escaneados para ingresar a stock:", weight=ft.FontWeight.BOLD, size=12),
                lista_escaneo_view,
                ft.Divider(height=6),
                resumen_escaneo_texto,
            ],
            tight=True,
            spacing=6,
        ),
        visible=True,
    )
    refrescar_vista_escaner()

    if es_operador:
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.INVENTORY_2, color=ROJO, size=24), ft.Text("Ingreso de Fábrica (Escáner de Recepción)", weight=ft.FontWeight.BOLD)], spacing=8),
            content=ft.Container(content=vista_escaner, width=580),
            actions=[interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()), interfaz.boton_dialogo("Limpiar", limpiar_escaner), btn_confirmar_escaner],
        )
        interfaz.page.show_dialog(dialogo)
        safe_focus(interfaz, input_codigo)
        return

    vista_archivo, procesar_archivos_fabrica = construir_tab_archivo_fabrica(interfaz, modo_sobrescribir)
    modo_actual = ["escaner"]

    def cambiar_pestana(modo: str) -> None:
        modo_actual[0] = modo
        vista_escaner.visible = (modo == "escaner")
        vista_archivo.visible = (modo == "archivo")
        btn_tab_escaner.style = ft.ButtonStyle(color=ft.Colors.WHITE if modo == "escaner" else interfaz.secundario, bgcolor=ROJO if modo == "escaner" else ft.Colors.TRANSPARENT)
        btn_tab_archivo.style = ft.ButtonStyle(color=ft.Colors.WHITE if modo == "archivo" else interfaz.secundario, bgcolor=ROJO if modo == "archivo" else ft.Colors.TRANSPARENT)
        interfaz.page.update()

    btn_tab_escaner = ft.Button("Escáner / Carga rápida", icon=ft.Icons.QR_CODE_SCANNER, on_click=lambda _e: cambiar_pestana("escaner"), style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ROJO))
    btn_tab_archivo = ft.Button("Por archivo (Fabrica)", icon=ft.Icons.FOLDER_OPEN, on_click=lambda _e: cambiar_pestana("archivo"), style=ft.ButtonStyle(color=interfaz.secundario, bgcolor=ft.Colors.TRANSPARENT))

    def aplicar_segun_modo(e: ft.Event) -> None:
        if modo_actual[0] == "escaner":
            guardar_escaner(e, sobrescribir=modo_sobrescribir.value)
        else:
            procesar_archivos_fabrica(e)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.INVENTORY_2, color=ROJO, size=24), ft.Text("Ingreso de Fábrica / Ajustar Stock", weight=ft.FontWeight.BOLD)], spacing=8),
        content=ft.Column([modo_sobrescribir, ft.Row([btn_tab_escaner, btn_tab_archivo], spacing=10), ft.Divider(height=1), vista_escaner, vista_archivo], tight=True, width=580),
        actions=[interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()), interfaz.boton_dialogo("Limpiar", limpiar_escaner), interfaz.boton_dialogo("Aplicar a stock", aplicar_segun_modo)],
    )
    interfaz.page.show_dialog(dialogo)
    safe_focus(interfaz, input_codigo)


__all__ = ["_get_stock_manager", "mostrar_ingreso_fabrica", "safe_focus"]
