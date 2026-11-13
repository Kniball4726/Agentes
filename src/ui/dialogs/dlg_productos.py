"""Diálogos modales para gestión del catálogo de productos y su stock."""

from __future__ import annotations

import sys
from typing import Any

import flet as ft

from ...stock_manager import StockManager as _DefaultStockManager
from ..theme import ROJO
from .productos_modales import (
    confirmar_cambio_estado_producto,
    mostrar_dialogo_editar_producto,
    mostrar_dialogo_formulario_producto,
    mostrar_dialogo_historial_movimientos_stock,
)


def _get_stock_manager_cls():
    """Devuelve StockManager vigente respetando mocks en src.flet_gui."""
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def mostrar_dialogo_gestion_productos(interfaz: Any) -> None:
    """Abre el catálogo interactivo para listar, buscar, editar y activar/desactivar productos."""
    if not interfaz.exigir_roles("administrador"):
        return
    stock_manager = _get_stock_manager_cls()(interfaz.menu.ruta_excel_base)
    busqueda = ft.TextField(
        label="Buscar por código, nombre o código de barras",
        hint_text="Escribe o escanea un código para filtrar...",
        expand=True,
    )
    productos = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO)
    cache_productos: list[Any] = []
    limite_visibles = [80]

    def mostrar_mas_productos(_e: ft.Event | None = None) -> None:
        limite_visibles[0] += 100
        actualizar_lista(recargar=False, mantener_limite=True)

    def actualizar_lista(
        _evento: ft.Event | None = None,
        recargar: bool = False,
        mantener_limite: bool = False,
    ) -> None:
        if not mantener_limite:
            limite_visibles[0] = 80
        if recargar or not cache_productos:
            cache_productos.clear()
            cache_productos.extend(stock_manager.listar_productos())
        productos.controls.clear()
        consulta = (busqueda.value or "").strip().casefold()
        filtrados = []
        for producto in cache_productos:
            codigo = str(producto["code"])
            nombre = str(producto["name"])
            barras = str(producto["cod_barras"] or "").strip() if "cod_barras" in producto.keys() else ""
            if consulta and consulta not in f"{codigo} {nombre} {barras}".casefold():
                continue
            filtrados.append(producto)

        for producto in filtrados[: limite_visibles[0]]:
            codigo = str(producto["code"])
            nombre = str(producto["name"])
            activo = bool(producto["active"])
            barras = str(producto["cod_barras"] or "").strip() if "cod_barras" in producto.keys() else ""
            stk = int(producto["stock"])
            try:
                stk_min = int(producto["stock_minimo"])
            except Exception:
                stk_min = 5
            try:
                stk_max = int(producto["stock_maximo"])
            except Exception:
                stk_max = 100

            if stk <= 0:
                estado_texto, estado_color = "Agotado", ft.Colors.RED_400
            elif stk <= stk_min:
                estado_texto, estado_color = f"Bajo (mín {stk_min})", ft.Colors.AMBER_400
            elif stk > stk_max:
                estado_texto, estado_color = f"Sobrestock (máx {stk_max})", ft.Colors.PURPLE_300
            else:
                estado_texto, estado_color = "Óptimo", ft.Colors.GREEN_400

            productos.controls.append(
                ft.Container(
                    padding=8,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    content=ft.Row(
                        [
                            ft.Text(codigo, width=90, color=interfaz.texto, weight=ft.FontWeight.BOLD),
                            ft.Text(nombre, expand=True, color=interfaz.texto),
                            ft.Text(f"🏷️ {barras}" if barras else "-", width=110, size=11, color=interfaz.secundario),
                            ft.Text(f"{stk} un.", width=70, color=interfaz.texto),
                            ft.Text(
                                estado_texto,
                                width=130,
                                size=12,
                                color=estado_color,
                                weight=ft.FontWeight.BOLD if stk <= stk_min else ft.FontWeight.NORMAL,
                            ),
                            ft.Text(
                                "Activo" if activo else "Inactivo",
                                width=70,
                                size=12,
                                color=ft.Colors.GREEN_400 if activo else interfaz.secundario,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.HISTORY,
                                tooltip="Ver historial de movimientos de este producto",
                                icon_size=18,
                                on_click=lambda _e, code=codigo: interfaz.mostrar_historial_movimientos_stock(code),
                            ),
                            ft.TextButton(
                                "Editar",
                                on_click=lambda _e, item=producto: mostrar_dialogo_editar_producto(
                                    interfaz, stock_manager, item, lambda: actualizar_lista(recargar=True)
                                ),
                            ),
                            ft.TextButton(
                                "Desactivar" if activo else "Reactivar",
                                on_click=lambda _e, code=codigo, status=activo: confirmar_cambio_estado_producto(
                                    interfaz, stock_manager, code, not status, lambda: actualizar_lista(recargar=True)
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )
        restantes = len(filtrados) - limite_visibles[0]
        if restantes > 0:
            productos.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=6,
                    content=ft.TextButton(
                        f"Mostrar más productos ({restantes} restantes)...",
                        icon=ft.Icons.EXPAND_MORE,
                        on_click=mostrar_mas_productos,
                    ),
                )
            )
        if not productos.controls:
            productos.controls.append(ft.Text("No se encontraron productos.", color=interfaz.secundario))
        interfaz.page.update()

    def agregar(_evento: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        interfaz.mostrar_formulario_producto(lambda: actualizar_lista(recargar=True))

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Gestión de productos"),
        content=ft.Column(
            [
                ft.Text("Las bajas son lógicas: el producto se conserva, pero no aparece en futuros informes."),
                ft.Row(
                    [
                        busqueda,
                        ft.Button(
                            "Historial movimientos",
                            icon=ft.Icons.HISTORY,
                            on_click=lambda _e: interfaz.mostrar_historial_movimientos_stock(busqueda.value or ""),
                        ),
                        ft.Button("Agregar producto", icon=ft.Icons.ADD, on_click=agregar, bgcolor=ROJO, color=ft.Colors.WHITE),
                    ],
                    spacing=8,
                ),
                ft.Row(
                    [
                        ft.Text("Código", width=100, weight=ft.FontWeight.BOLD),
                        ft.Text("Nombre", expand=True, weight=ft.FontWeight.BOLD),
                        ft.Text("Stock", width=70, weight=ft.FontWeight.BOLD),
                        ft.Text("Estado", width=80, weight=ft.FontWeight.BOLD),
                        ft.Container(width=145),
                    ]
                ),
                ft.Container(height=420, content=productos),
            ],
            tight=True,
            width=900,
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    busqueda.on_change = actualizar_lista
    actualizar_lista()
    interfaz.page.show_dialog(dialogo)


__all__ = [
    "_get_stock_manager_cls",
    "mostrar_dialogo_formulario_producto",
    "mostrar_dialogo_gestion_productos",
    "mostrar_dialogo_historial_movimientos_stock",
]
