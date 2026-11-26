"""Módulo fachada desacoplado para el descuento de pedidos de Mercado Libre.

Re-exporta MercadoLibreScannerComponent, MercadoLibreDocxComponent y mostrar_descuento_mercado_libre.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft

from ..theme import ROJO
from ._shared import resolve_stock_manager, safe_focus
from .ml_docx_component import MercadoLibreDocxComponent
from .ml_scanner_component import MercadoLibreScannerComponent


def _get_stock_manager(interfaz: Any = None):
    """Obtiene la clase StockManager activa mediante inyección en `interfaz`."""
    return resolve_stock_manager(interfaz)


def mostrar_descuento_mercado_libre(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana modularizada para procesar y descontar pedidos de Mercado Libre (Pistoleo en Vivo o archivo .docx)."""
    if not interfaz.exigir_roles("operador", "administrador", "picker"):
        return

    carpeta_ml = getattr(interfaz.menu, "carpeta_mercado_libre", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "MercadoLibre"
    )
    carpeta_ml.mkdir(parents=True, exist_ok=True)
    dest_archivado = (
        getattr(interfaz.menu, "carpeta_descontados", None)
        or (getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "descontados")
    ) / "MercadoLibre"
    dest_archivado.mkdir(parents=True, exist_ok=True)

    if hasattr(interfaz, "cerrar_drawer_si_movil"):
        interfaz.cerrar_drawer_si_movil()
    if hasattr(interfaz, "_asegurar_file_picker"):
        interfaz._asegurar_file_picker()

    tab_activa = [0]
    btn_confirmar = ft.Button(
        "Confirmar y Descontar",
        icon=ft.Icons.CHECK_CIRCLE,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    def _sync_boton_confirmar(tiene_items: bool | None = None, habilitado: bool | None = None) -> None:
        if tab_activa[0] == 0:
            if tiene_items is not None:
                btn_confirmar.disabled = not tiene_items
            else:
                btn_confirmar.disabled = len(comp_scanner.items_escaneados) == 0
        else:
            if habilitado is not None:
                btn_confirmar.disabled = not habilitado
            else:
                btn_confirmar.disabled = not (comp_docx.archivo_seleccionado[0] and comp_docx.items_a_descontar)
        interfaz.page.update()

    comp_scanner = MercadoLibreScannerComponent(
        interfaz=interfaz,
        al_cambiar_estado=lambda tiene_items: _sync_boton_confirmar(tiene_items=tiene_items),
    )
    comp_docx = MercadoLibreDocxComponent(
        interfaz=interfaz,
        carpeta_ml=carpeta_ml,
        dest_archivado=dest_archivado,
        al_cambiar_estado=lambda habilitado: _sync_boton_confirmar(habilitado=habilitado),
    )

    vista_escaner = comp_scanner.construir_vista()
    vista_docx = comp_docx.construir_vista()

    def on_tab_change(e: ft.Event) -> None:
        idx = 0
        try:
            idx = int(e.control.selected_index if hasattr(e.control, "selected_index") else getattr(e, "data", 0) or 0)
        except Exception:
            idx = 0
        tab_activa[0] = idx
        if tab_activa[0] == 0:
            btn_confirmar.disabled = len(comp_scanner.items_escaneados) == 0
            comp_scanner.enfocar()
        else:
            btn_confirmar.disabled = not (comp_docx.archivo_seleccionado[0] and comp_docx.items_a_descontar)
        interfaz.page.update()

    tabs_contenido = ft.Tabs(
        length=2,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Pistoleo / Escáner en Vivo", icon=ft.Icons.BARCODE_READER),
                        ft.Tab(label="Cargar Archivo (.docx)", icon=ft.Icons.DESCRIPTION),
                    ]
                ),
                ft.TabBarView(expand=True, controls=[vista_escaner, vista_docx]),
            ],
        ),
    )
    tabs_contenido.on_change = on_tab_change

    async def on_confirmar_click(e: ft.Event) -> None:
        if tab_activa[0] == 0:
            await comp_scanner.ejecutar_descuento_paquete(e)
        else:
            await comp_docx.confirmar_descuento_docx(e)

    btn_confirmar.on_click = on_confirmar_click

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.STOREFRONT, color=ROJO),
                ft.Text("Descontar Pedido Mercado Libre", size=16, weight=ft.FontWeight.BOLD, expand=True),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=interfaz.ancho_adaptable(680) if hasattr(interfaz, "ancho_adaptable") else 680,
            content=tabs_contenido,
        ),
        actions=[
            btn_confirmar,
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    comp_scanner.actualizar_vista()
    interfaz.page.show_dialog(dialogo)


__all__ = [
    "MercadoLibreScannerComponent",
    "MercadoLibreDocxComponent",
    "mostrar_descuento_mercado_libre",
    "safe_focus",
    "_get_stock_manager",
]
