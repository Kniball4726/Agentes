"""Vistas compartidas y auditoría administrativa de comparativas de stock físico."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import flet as ft

from ...stock_manager import StockManager as _DefaultStockManager
from ..theme import ROJO


def resolver_stock_manager_sf():
    """Resuelve StockManager respetando patches en dlg_stock_fisico o src.flet_gui."""
    mod_sf = sys.modules.get("src.ui.dialogs.dlg_stock_fisico")
    if mod_sf is not None and hasattr(mod_sf, "_get_stock_manager"):
        return mod_sf._get_stock_manager()
    mod_gui = sys.modules.get("src.flet_gui")
    if mod_gui is not None and hasattr(mod_gui, "StockManager"):
        return getattr(mod_gui, "StockManager")
    return _DefaultStockManager


def construir_fila_comparativa_sf(
    interfaz: Any,
    *,
    codigo: str,
    nombre: str,
    stock_digital: int,
    stock_fisico: int,
    diferencia: int,
    estado: str,
    modo_admin: bool = False,
) -> ft.Container:
    """Construye una fila comparativa de stock digital vs físico compartida entre operario y admin."""
    dif_str = f"+{diferencia}" if diferencia > 0 else str(diferencia)
    if estado == "COINCIDE":
        color_est = ft.Colors.GREEN_500
    elif estado in ("FALTANTE", "NO_CATALOGADO"):
        color_est = ft.Colors.RED_400
    else:
        color_est = ft.Colors.AMBER_400

    columnas_stock = (
        [
            ft.Text(f"Digital: {stock_digital}", size=11, width=85),
            ft.Text(f"Físico: {stock_fisico}", size=11, width=85),
        ]
        if modo_admin
        else [
            ft.Text(f"Dig: {stock_digital} | Fís: {stock_fisico}", size=11, color=interfaz.texto, width=120),
        ]
    )

    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=6,
        bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
        content=ft.Row(
            [
                ft.Text(f"[{codigo}]", weight=ft.FontWeight.BOLD, size=11, width=75),
                ft.Text(nombre, size=11, expand=True, no_wrap=True),
                *columnas_stock,
                ft.Text(f"Dif: {dif_str} [{estado}]", weight=ft.FontWeight.BOLD, size=11, color=color_est, width=145),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )


def mostrar_comparativa_stock_fisico_admin(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para que la administración supervise y descargue auditorías de inventario físico."""
    if not interfaz.exigir_roles("administrador"):
        return

    sm = resolver_stock_manager_sf()(interfaz.menu.ruta_excel_base)
    inventarios = sm.listar_inventarios_fisicos(limit=25)
    lista_detalles = ft.ListView(expand=True, spacing=4, height=300)
    solo_diferencias = ft.Checkbox(label="Mostrar solo productos con diferencias", value=False)
    resumen_admin = ft.Text(
        "No se han registrado relevamientos de stock físico por parte de los operarios todavía."
        if not inventarios
        else "",
        size=12,
        color=interfaz.secundario,
    )
    inv_actual: list = [inventarios[0] if inventarios else None]

    def recargar_detalle() -> None:
        lista_detalles.controls.clear()
        cab = inv_actual[0]
        if cab is None:
            interfaz.page.update()
            return

        detalles = sm.obtener_detalle_inventario_fisico(int(cab["id"]))
        doc_unif = Path(cab["reporte_unificado"]).name if cab["reporte_unificado"] else "N/A"
        resumen_admin.value = (
            f"Operario: {cab['usuario']} · Fecha: {cab['fecha']} · "
            f"Relevados: {cab['total_relevados']} · Con diferencias: {cab['total_diferencias']} · "
            f"Documento: {doc_unif}"
        )
        resumen_admin.color = interfaz.texto

        for d in detalles:
            dif = int(d["diferencia"])
            if solo_diferencias.value and dif == 0:
                continue
            lista_detalles.controls.append(
                construir_fila_comparativa_sf(
                    interfaz,
                    codigo=str(d["product_code"]),
                    nombre=str(d["product_name"]),
                    stock_digital=int(d["stock_digital"]),
                    stock_fisico=int(d["stock_fisico"]),
                    diferencia=dif,
                    estado=str(d["estado"]),
                    modo_admin=True,
                )
            )
        interfaz.page.update()

    opciones_inv = [
        ft.dropdown.Option(
            key=str(inv["id"]),
            text=f"#{inv['id']} · {inv['fecha']} · Operario: {inv['usuario']} ({inv['total_diferencias']} dif.)",
        )
        for inv in inventarios
    ]
    selector_inv = ft.Dropdown(
        label="Relevamientos de Stock Físico registrados",
        options=opciones_inv,
        value=str(inventarios[0]["id"]) if inventarios else None,
        expand=True,
        dense=True,
    )

    def cambiar_inv(_e: ft.Event) -> None:
        val = selector_inv.value
        for inv in inventarios:
            if str(inv["id"]) == val:
                inv_actual[0] = inv
                recargar_detalle()
                break

    selector_inv.on_change = cambiar_inv
    selector_inv.on_select = cambiar_inv
    solo_diferencias.on_change = lambda _e: recargar_detalle()

    if inv_actual[0] is not None:
        recargar_detalle()

    def abrir_documento_unificado(_e: ft.Event) -> None:
        cab = inv_actual[0]
        if cab is None or not cab["reporte_unificado"]:
            interfaz.notificar("No hay un documento unificado asociado a este relevamiento.")
            return
        ruta = Path(cab["reporte_unificado"])
        if not ruta.exists():
            interfaz.notificar(f"El archivo '{ruta.name}' no se encuentra en disco.")
            return
        interfaz.abrir_informe(ruta_especifica=ruta)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.COMPARE_ARROWS, color=ROJO),
                ft.Text("Comparativa y Diferencias: Stock Digital vs. Físico", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=700,
            content=ft.Column(
                [ft.Row([selector_inv], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), resumen_admin, solo_diferencias, ft.Divider(height=6), lista_detalles],
                tight=True,
                spacing=6,
            ),
        ),
        actions=[
            ft.Button(
                "Relevar Inventario (Escáner)",
                icon=ft.Icons.DOCUMENT_SCANNER,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=lambda _e: (interfaz.page.pop_dialog(), interfaz.mostrar_dialogo_inventario_vivo()),
            ),
            ft.TextButton("Descargar / Abrir Documento Unificado (Excel)", icon=ft.Icons.DOWNLOAD, on_click=abrir_documento_unificado),
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
