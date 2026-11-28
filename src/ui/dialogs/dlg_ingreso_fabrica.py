"""Diálogo interactivo para escaneo y recepción de mercadería de fábrica."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import Any

import flet as ft

from ..audio_feedback import emitir_tono_error, emitir_tono_exito, normalizar_codigo_lector
from ..theme import ROJO
from ._shared import resolve_stock_manager, safe_focus
from .ingreso_fabrica_archivo import (
    construir_tab_archivo_fabrica,
    registrar_ingreso_escaner,
)


def _get_stock_manager(interfaz: Any = None):
    """Devuelve StockManager vigente mediante inyección en `interfaz`."""
    return resolve_stock_manager(interfaz)


def _buscar_sku_fabrica(stock_manager: Any, codigo_limpio: str) -> tuple[str | None, str | None, int]:
    """Busca un producto en SQLite o catálogo en memoria para ingreso de fábrica."""
    prod_encontrado = None
    if hasattr(stock_manager, "product_store"):
        with suppress(Exception):
            prod_encontrado = stock_manager.product_store.find_product_by_code_or_barcode(
                codigo_limpio
            )
            if not prod_encontrado:
                res_busq = stock_manager.product_store.buscar_productos(codigo_limpio, limite=1)
                if res_busq:
                    prod_encontrado = res_busq[0]

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


def _resolver_info_sku(stock_manager: Any, sku: str) -> tuple[str, int]:
    prod = None
    if hasattr(stock_manager, "product_store"):
        with suppress(Exception):
            prod = stock_manager.product_store.get_product(sku)
    nombre = prod["name"] if prod else stock_manager.catalogo.get(sku, ("", "Producto", 0))[1]
    stk_act = int(prod["stock"]) if prod else stock_manager.catalogo.get(sku, ("", "", 0))[2]
    return nombre, stk_act


def _construir_placeholder_escaner(interfaz: Any) -> ft.Container:
    return ft.Container(
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


def _construir_fila_sku_escaneado(
    interfaz: Any,
    sku: str,
    nombre: str,
    stk_act: int,
    cant: int,
    on_ajustar: Callable[[str, int], None],
    on_eliminar: Callable[[str], None],
) -> ft.Container:
    nuevo_stk = stk_act + cant
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=6,
        bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
        border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(f"[{sku}]", weight=ft.FontWeight.BOLD, size=11, color=ROJO),
                                ft.Text(
                                    nombre,
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    expand=True,
                                    no_wrap=True,
                                ),
                            ],
                            spacing=6,
                        ),
                        ft.Text(
                            f"Stock actual: {stk_act} → Con ingreso: {nuevo_stk} (+{cant} un.)",
                            size=10,
                            color=ft.Colors.GREEN_400 if nuevo_stk > stk_act else interfaz.secundario,
                        ),
                    ],
                    expand=True,
                    spacing=2,
                ),
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_DOWN,
                            icon_size=18,
                            tooltip="Restar 12 un. (-12)",
                            on_click=lambda _e, s=sku: on_ajustar(s, -12),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                            icon_size=18,
                            tooltip="Restar 1 un. (-1)",
                            on_click=lambda _e, s=sku: on_ajustar(s, -1),
                        ),
                        ft.Text(f"{cant} un.", weight=ft.FontWeight.BOLD, size=12),
                        ft.IconButton(
                            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                            icon_size=18,
                            tooltip="Sumar 1 un. (+1)",
                            on_click=lambda _e, s=sku: on_ajustar(s, 1),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_UP,
                            icon_size=18,
                            tooltip="Sumar 12 un. (+12)",
                            on_click=lambda _e, s=sku: on_ajustar(s, 12),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=18,
                            icon_color=ft.Colors.RED_400,
                            tooltip="Quitar producto",
                            on_click=lambda _e, s=sku: on_eliminar(s),
                        ),
                    ],
                    spacing=0,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


class _IngresoFabricaController:
    """Controlador del diálogo de ingreso de mercadería de fábrica por escáner o archivo."""

    def __init__(self, interfaz: Any) -> None:
        self.interfaz = interfaz
        self.es_admin = getattr(interfaz.usuario_actual, "role", None) == "administrador"
        self.stock_manager = _get_stock_manager(interfaz)(interfaz.menu.ruta_excel_base)
        self.modo_sobrescribir = ft.Checkbox(
            label="Sobrescribir stock (establece el valor exacto indicado)",
            value=False,
        )
        self.items_escaneados: dict[str, int] = {}

        self.input_codigo = ft.TextField(
            label="Escanear código de barras o SKU (Pistola lectora)",
            hint_text="Pasa la pistola lectora o escribe el código y presiona Enter...",
            prefix_icon=ft.Icons.BARCODE_READER,
            autofocus=True,
            expand=True,
            dense=True,
            on_submit=lambda _e: self.procesar_lectura_codigo(),
        )
        self.input_cant = ft.TextField(
            value="12",
            width=60,
            dense=True,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.texto_feedback = ft.Text(
            "Listo para recibir mercadería. Escanea los productos o bultos de fábrica.",
            size=11,
            color=interfaz.secundario,
        )
        self.lista_escaneo_view = ft.ListView(expand=True, spacing=4, height=220)
        self.resumen_escaneo_texto = ft.Text(
            "0 productos escaneados (0 unidades a ingresar)",
            size=12,
            weight=ft.FontWeight.BOLD,
            color=interfaz.secundario,
        )
        self.btn_confirmar_escaner = ft.Button(
            "Confirmar Ingreso a Depósito",
            icon=ft.Icons.CHECK_CIRCLE,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
            disabled=True,
            on_click=lambda _e: self.guardar_escaner(_e, sobrescribir=False),
        )
        self.vista_escaner = self._construir_vista_escaner()
        self.refrescar_vista_escaner()

    def _ajustar_cant_input(self, delta: int) -> None:
        try:
            val = int(self.input_cant.value or "12")
        except ValueError:
            val = 12
        self.input_cant.value = str(max(1, val + delta))
        self.interfaz.page.update()

    def _fijar_cant_input(self, val: int) -> None:
        self.input_cant.value = str(val)
        safe_focus(self.interfaz, self.input_codigo)
        self.interfaz.page.update()

    def _ajustar_sku(self, sku: str, delta: int) -> None:
        nueva = self.items_escaneados.get(sku, 1) + delta
        if nueva <= 0:
            self.items_escaneados.pop(sku, None)
        else:
            self.items_escaneados[sku] = nueva
        self.refrescar_vista_escaner()
        safe_focus(self.interfaz, self.input_codigo)
        self.interfaz.page.update()

    def _eliminar_sku(self, sku: str) -> None:
        self.items_escaneados.pop(sku, None)
        self.refrescar_vista_escaner()
        safe_focus(self.interfaz, self.input_codigo)
        self.interfaz.page.update()

    def _construir_fila_multiplos(self) -> ft.Row:
        return ft.Row(
            [
                ft.Text(
                    "Lotes x12:",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color=self.interfaz.secundario,
                ),
                *[
                    ft.Button(
                        str(m),
                        style=ft.ButtonStyle(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                            color=ft.Colors.WHITE if self.interfaz.modo_oscuro else ft.Colors.BLACK87,
                            bgcolor=(
                                ft.Colors.WHITE_10
                                if self.interfaz.modo_oscuro
                                else ft.Colors.GREY_200
                            ),
                        ),
                        on_click=lambda _e, val=m: self._fijar_cant_input(val),
                    )
                    for m in (12, 24, 36, 48, 60, 120)
                ],
            ],
            spacing=6,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _construir_vista_escaner(self) -> ft.Container:
        return ft.Container(
            padding=10,
            visible=True,
            content=ft.Column(
                [
                    self._construir_fila_multiplos(),
                    ft.Row(
                        [
                            ft.Text("Cantidad por lectura:", size=11, weight=ft.FontWeight.BOLD),
                            ft.IconButton(
                                icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                icon_size=20,
                                tooltip="Restar 1 unidad (-1)",
                                on_click=lambda _e: self._ajustar_cant_input(-1),
                            ),
                            self.input_cant,
                            ft.IconButton(
                                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                icon_size=20,
                                tooltip="Sumar 1 unidad (+1)",
                                on_click=lambda _e: self._ajustar_cant_input(1),
                            ),
                            ft.Text("unidades", size=11, color=self.interfaz.secundario),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    ft.Row(
                        [
                            self.input_codigo,
                            ft.Button(
                                "Ingresar",
                                icon=ft.Icons.ADD,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                on_click=lambda _e: self.procesar_lectura_codigo(),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    self.texto_feedback,
                    ft.Divider(height=10),
                    ft.Text(
                        "Productos escaneados para ingresar a stock:",
                        weight=ft.FontWeight.BOLD,
                        size=12,
                    ),
                    self.lista_escaneo_view,
                    ft.Divider(height=6),
                    self.resumen_escaneo_texto,
                ],
                tight=True,
                spacing=6,
            ),
        )

    def refrescar_vista_escaner(self) -> None:
        self.lista_escaneo_view.controls.clear()
        if not self.items_escaneados:
            self.lista_escaneo_view.controls.append(_construir_placeholder_escaner(self.interfaz))
            self.resumen_escaneo_texto.value = "0 productos escaneados (0 unidades a ingresar)"
            self.resumen_escaneo_texto.color = self.interfaz.secundario
            self.btn_confirmar_escaner.disabled = True
            return

        total_unidades = sum(self.items_escaneados.values())
        for sku, cant in list(self.items_escaneados.items()):
            nombre, stk_act = _resolver_info_sku(self.stock_manager, sku)
            self.lista_escaneo_view.controls.append(
                _construir_fila_sku_escaneado(
                    self.interfaz,
                    sku,
                    nombre,
                    stk_act,
                    cant,
                    self._ajustar_sku,
                    self._eliminar_sku,
                )
            )

        sufijo = "s" if len(self.items_escaneados) != 1 else ""
        self.resumen_escaneo_texto.value = (
            f"📥 {len(self.items_escaneados)} producto{sufijo} "
            f"({total_unidades} unidades totales a ingresar a stock)"
        )
        self.resumen_escaneo_texto.color = self.interfaz.texto
        self.btn_confirmar_escaner.disabled = False

    def procesar_lectura_codigo(self) -> None:
        raw = (self.input_codigo.value or "").strip()
        if not raw:
            return
        codigo_limpio = normalizar_codigo_lector(raw) or raw
        try:
            cant_a_sumar = max(1, int(self.input_cant.value or "12"))
        except ValueError:
            cant_a_sumar = 12

        sku_final, nombre_final, stk_actual = _buscar_sku_fabrica(self.stock_manager, codigo_limpio)
        if not sku_final:
            self.texto_feedback.value = f"❌ Código '{codigo_limpio}' no encontrado en el catálogo."
            self.texto_feedback.color = ft.Colors.RED_400
            emitir_tono_error()
            if hasattr(self.interfaz, "reproducir_sonido"):
                self.interfaz.reproducir_sonido("error")
            self.input_codigo.value = ""
            safe_focus(self.interfaz, self.input_codigo)
            self.interfaz.page.update()
            return

        nueva_cant = self.items_escaneados.get(sku_final, 0) + cant_a_sumar
        self.items_escaneados[sku_final] = nueva_cant
        self.texto_feedback.value = (
            f"✅ [{sku_final}] {nombre_final} (+{cant_a_sumar} un.) | "
            f"Stock actual: {stk_actual} → Con ingreso: {stk_actual + nueva_cant}"
        )
        self.texto_feedback.color = ft.Colors.GREEN_400
        emitir_tono_exito()
        if hasattr(self.interfaz, "reproducir_sonido"):
            self.interfaz.reproducir_sonido("exito")

        self.input_codigo.value = ""
        self.refrescar_vista_escaner()
        safe_focus(self.interfaz, self.input_codigo)
        self.interfaz.page.update()

    def limpiar_escaner(self, _e: ft.Event | None = None) -> None:
        self.items_escaneados.clear()
        self.texto_feedback.value = "Lista de ingreso vaciada."
        self.texto_feedback.color = self.interfaz.secundario
        self.input_codigo.value = ""
        self.input_cant.value = "12"
        self.refrescar_vista_escaner()
        safe_focus(self.interfaz, self.input_codigo)
        self.interfaz.page.update()

    def guardar_escaner(self, _e: ft.Event | None = None, sobrescribir: bool = False) -> None:
        if not self.items_escaneados:
            self.interfaz.notificar("Debes escanear al menos un producto antes de confirmar.")
            return
        self.interfaz.page.pop_dialog()
        registrar_ingreso_escaner(self.interfaz, self.items_escaneados, sobrescribir)

    def _construir_dialogo_operador(self) -> ft.AlertDialog:
        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.INVENTORY_2, color=ROJO, size=24),
                    ft.Text("Ingreso de Fábrica (Escáner de Recepción)", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(content=self.vista_escaner, width=580),
            actions=[
                self.interfaz.boton_dialogo("Cancelar", lambda _e: self.interfaz.page.pop_dialog()),
                self.interfaz.boton_dialogo("Limpiar", self.limpiar_escaner),
                self.btn_confirmar_escaner,
            ],
        )

    def _construir_dialogo_admin(self) -> ft.AlertDialog:
        vista_archivo, procesar_archivos_fabrica = construir_tab_archivo_fabrica(
            self.interfaz, self.modo_sobrescribir
        )
        modo_actual = ["escaner"]

        def cambiar_pestana(modo: str) -> None:
            modo_actual[0] = modo
            self.vista_escaner.visible = modo == "escaner"
            vista_archivo.visible = modo == "archivo"
            btn_tab_escaner.style = ft.ButtonStyle(
                color=ft.Colors.WHITE if modo == "escaner" else self.interfaz.secundario,
                bgcolor=ROJO if modo == "escaner" else ft.Colors.TRANSPARENT,
            )
            btn_tab_archivo.style = ft.ButtonStyle(
                color=ft.Colors.WHITE if modo == "archivo" else self.interfaz.secundario,
                bgcolor=ROJO if modo == "archivo" else ft.Colors.TRANSPARENT,
            )
            self.interfaz.page.update()

        btn_tab_escaner = ft.Button(
            "Escáner / Carga rápida",
            icon=ft.Icons.QR_CODE_SCANNER,
            on_click=lambda _e: cambiar_pestana("escaner"),
            style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ROJO),
        )
        btn_tab_archivo = ft.Button(
            "Por archivo (Fabrica)",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda _e: cambiar_pestana("archivo"),
            style=ft.ButtonStyle(color=self.interfaz.secundario, bgcolor=ft.Colors.TRANSPARENT),
        )

        def aplicar_segun_modo(e: ft.Event) -> None:
            if modo_actual[0] == "escaner":
                self.guardar_escaner(e, sobrescribir=self.modo_sobrescribir.value)
            else:
                procesar_archivos_fabrica(e)

        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.INVENTORY_2, color=ROJO, size=24),
                    ft.Text("Ingreso de Fábrica / Ajustar Stock", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Column(
                [
                    self.modo_sobrescribir,
                    ft.Row([btn_tab_escaner, btn_tab_archivo], spacing=10),
                    ft.Divider(height=1),
                    self.vista_escaner,
                    vista_archivo,
                ],
                tight=True,
                width=580,
            ),
            actions=[
                self.interfaz.boton_dialogo("Cancelar", lambda _e: self.interfaz.page.pop_dialog()),
                self.interfaz.boton_dialogo("Limpiar", self.limpiar_escaner),
                self.interfaz.boton_dialogo("Aplicar a stock", aplicar_segun_modo),
            ],
        )

    def mostrar(self) -> None:
        dialogo = (
            self._construir_dialogo_admin()
            if self.es_admin
            else self._construir_dialogo_operador()
        )
        self.interfaz.page.show_dialog(dialogo)
        safe_focus(self.interfaz, self.input_codigo)


def mostrar_ingreso_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para escanear mercadería de fábrica o ajustar stock."""
    if not interfaz.exigir_roles("operador", "administrador", "picker"):
        return

    _IngresoFabricaController(interfaz).mostrar()


__all__ = ["_get_stock_manager", "mostrar_ingreso_fabrica", "safe_focus"]
