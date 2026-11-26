"""Diálogos modales para gestión del catálogo de productos y su stock."""

from __future__ import annotations

import sys
from typing import Any

import flet as ft

from ..components.debounce import Debouncer
from ..design import es_viewport_estrecho
from ..theme import ROJO
from ._shared import resolve_stock_manager
from .dlg_ubicaciones_lotes import mostrar_dialogo_ubicaciones_lotes
from .productos_modales import (
    confirmar_cambio_estado_producto,
    mostrar_dialogo_editar_producto,
    mostrar_dialogo_formulario_producto,
    mostrar_dialogo_historial_movimientos_stock,
)


def _get_stock_manager_cls(interfaz: Any = None):
    """Devuelve StockManager vigente mediante inyección desde `interfaz`."""
    return resolve_stock_manager(interfaz)


def mostrar_dialogo_gestion_productos(interfaz: Any) -> None:
    """Abre el catálogo interactivo para listar, buscar, editar y activar/desactivar productos."""
    if not interfaz.exigir_roles("administrador"):
        return
    stock_manager = _get_stock_manager_cls(interfaz)(interfaz.menu.ruta_excel_base)
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

        es_estrecho = es_viewport_estrecho(interfaz, umbral=760.0)
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

            btn_hist = ft.IconButton(
                icon=ft.Icons.HISTORY,
                tooltip="Ver historial de movimientos de este producto",
                icon_size=18,
                on_click=lambda _e, code=codigo: interfaz.mostrar_historial_movimientos_stock(code),
            )
            btn_ubic_lotes = ft.IconButton(
                icon=ft.Icons.WAREHOUSE_OUTLINED,
                tooltip="Gestionar ubicaciones multi-zona y lotes FEFO",
                icon_size=18,
                on_click=lambda _e, item=producto: mostrar_dialogo_ubicaciones_lotes(
                    interfaz, stock_manager, item, lambda: actualizar_lista(recargar=True)
                ),
            )
            btn_edit = ft.TextButton(
                "Editar",
                on_click=lambda _e, item=producto: mostrar_dialogo_editar_producto(
                    interfaz, stock_manager, item, lambda: actualizar_lista(recargar=True)
                ),
            )
            btn_estado = ft.TextButton(
                "Desactivar" if activo else "Reactivar",
                on_click=lambda _e, code=codigo, status=activo: confirmar_cambio_estado_producto(
                    interfaz, stock_manager, code, not status, lambda: actualizar_lista(recargar=True)
                ),
            )

            if es_estrecho:
                contenido_prod: ft.Control = ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(codigo, color=interfaz.texto, weight=ft.FontWeight.BOLD, size=12),
                                ft.Text(
                                    "Activo" if activo else "Inactivo",
                                    size=11,
                                    color=ft.Colors.GREEN_400 if activo else interfaz.secundario,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(nombre, color=interfaz.texto, size=13, weight=ft.FontWeight.W_500, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Row(
                            [
                                ft.Text(f"Stock: {stk} un.", size=11, color=interfaz.texto),
                                ft.Text(
                                    estado_texto,
                                    size=11,
                                    color=estado_color,
                                    weight=ft.FontWeight.BOLD if stk <= stk_min else ft.FontWeight.NORMAL,
                                ),
                                *([ft.Text(f"🏷️ {barras}", size=11, color=interfaz.secundario)] if barras else []),
                            ],
                            spacing=10,
                            wrap=True,
                            run_spacing=4,
                        ),
                        ft.Row([btn_ubic_lotes, btn_hist, btn_edit, btn_estado], spacing=4, wrap=True, alignment=ft.MainAxisAlignment.END),
                    ],
                    spacing=4,
                    tight=True,
                )
            else:
                contenido_prod = ft.Row(
                    [
                        ft.Text(codigo, width=90, color=interfaz.texto, weight=ft.FontWeight.BOLD),
                        ft.Text(nombre, expand=True, color=interfaz.texto, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
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
                        btn_ubic_lotes,
                        btn_hist,
                        btn_edit,
                        btn_estado,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )

            productos.controls.append(
                ft.Container(
                    padding=8,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    content=contenido_prod,
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

    es_estrecho_prod = es_viewport_estrecho(interfaz, umbral=760.0)
    fila_acciones_prod = (
        ft.Column(
            [
                busqueda,
                ft.Row(
                    [
                        ft.Button(
                            "Historial movimientos",
                            icon=ft.Icons.HISTORY,
                            on_click=lambda _e: interfaz.mostrar_historial_movimientos_stock(busqueda.value or ""),
                        ),
                        ft.Button("Agregar producto", icon=ft.Icons.ADD, on_click=agregar, bgcolor=ROJO, color=ft.Colors.WHITE),
                    ],
                    spacing=8,
                    wrap=True,
                    run_spacing=6,
                ),
            ],
            spacing=8,
            tight=True,
        )
        if es_estrecho_prod
        else ft.Row(
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
        )
    )
    cabecera_prod = (
        ft.Container(visible=False, height=0)
        if es_estrecho_prod
        else ft.Row(
            [
                ft.Text("Código", width=100, weight=ft.FontWeight.BOLD),
                ft.Text("Nombre", expand=True, weight=ft.FontWeight.BOLD),
                ft.Text("Stock", width=70, weight=ft.FontWeight.BOLD),
                ft.Text("Estado", width=80, weight=ft.FontWeight.BOLD),
                ft.Container(width=185),
            ]
        )
    )
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Gestión de productos"),
        content=ft.Column(
            [
                ft.Text("Las bajas son lógicas: el producto se conserva, pero no aparece en futuros informes."),
                fila_acciones_prod,
                cabecera_prod,
                ft.Container(height=420, content=productos),
            ],
            tight=True,
            width=interfaz.ancho_adaptable(900) if hasattr(interfaz, "ancho_adaptable") else 900,
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    es_test = getattr(interfaz, "_is_mock", False) or "pytest" in sys.modules
    debouncer = Debouncer(0.0 if es_test else 0.25)

    def _al_escribir_busqueda(_e: Any = None) -> None:
        debouncer.debounce(actualizar_lista)

    def _al_enviar_busqueda(_e: Any = None) -> None:
        debouncer.cancel()
        actualizar_lista()

    busqueda.on_change = _al_escribir_busqueda
    busqueda.on_submit = _al_enviar_busqueda
    actualizar_lista()
    interfaz.page.show_dialog(dialogo)


__all__ = [
    "_get_stock_manager_cls",
    "mostrar_dialogo_formulario_producto",
    "mostrar_dialogo_gestion_productos",
    "mostrar_dialogo_historial_movimientos_stock",
]
