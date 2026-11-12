"""Diálogo para generación de planillas Excel de pedido sugerido a fábrica."""
from datetime import datetime
import inspect
from pathlib import Path
import shutil
import sys
from typing import Any
import flet as ft

from ..theme import ROJO
from ...stock_manager import StockManager as _DefaultStockManager

def _get_stock_manager():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager

def safe_focus(interfaz: Any, ctrl: Any) -> None:
    try:
        res = ctrl.focus()
        if inspect.iscoroutine(res):
            if (
                hasattr(interfaz, "page")
                and hasattr(interfaz.page, "run_task")
                and callable(interfaz.page.run_task)
                and not getattr(interfaz.page, "_is_mock", False)
                and not hasattr(interfaz.page, "mock_calls")
            ):
                async def _f():
                    await res
                interfaz.page.run_task(_f)
            else:
                res.close()
    except Exception:
        pass


def generar_pedido_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Calcula y genera la planilla Excel oficial de reposición para proveedores/fábrica."""
    if not interfaz.exigir_roles("administrador"):
        return

    try:
        sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
        analisis = sm.obtener_analisis_reposicion(solo_criticos=True)
        items_a_pedir = [p for p in analisis if int(p["cantidad_sugerida_pedir"]) > 0]
        ruta_excel = sm.generar_pedido_sugerido_fabrica(solo_criticos=True)
        interfaz.actualizar_estado()
        interfaz.seleccionar_informe(ruta_excel)
    except Exception as e:
        interfaz.notificar(f"Error al generar pedido a fábrica: {e}")
        return

    total_unidades = sum(int(p["cantidad_sugerida_pedir"]) for p in items_a_pedir)
    cant_productos = len(items_a_pedir)

    contenido = ft.Column(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=32),
                    ft.Column(
                        [
                            ft.Text(
                                "¡Pedido a fábrica generado con éxito!",
                                weight=ft.FontWeight.BOLD,
                                size=15,
                                color=interfaz.texto,
                            ),
                            ft.Text(
                                f"{cant_productos} producto{'s' if cant_productos != 1 else ''} con sugerencia · {total_unidades} unidades calculadas para alcanzar el stock máximo.",
                                size=12,
                                color=interfaz.secundario,
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=12,
            ),
            ft.Divider(height=16),
            ft.Container(
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=12,
                content=ft.Column(
                    [
                        ft.Text("Archivo Excel disponible en 'Informes generados':", size=11, color=interfaz.secundario, weight=ft.FontWeight.BOLD),
                        ft.Text(str(ruta_excel.name), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_300 if interfaz.modo_oscuro else ft.Colors.BLUE_700),
                        ft.Text(f"Carpeta: {ruta_excel.parent}", size=11, color=interfaz.secundario),
                    ],
                    spacing=4,
                ),
            ),
        ],
        tight=True,
        width=500,
        spacing=10,
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.FACT_CHECK, color=ROJO, size=24),
                ft.Text("Sugerencia de Pedido a Fábrica"),
            ],
            spacing=8,
        ),
        content=contenido,
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo(
                "Abrir Excel",
                lambda _e: (interfaz.page.pop_dialog(), interfaz.abrir_informe(ruta_especifica=ruta_excel)),
            ),
            interfaz.boton_dialogo(
                "Enviar correo",
                lambda _e: (interfaz.page.pop_dialog(), interfaz.compartir_correo(ruta_especifica=ruta_excel)),
            ),
            interfaz.boton_dialogo(
                "WhatsApp",
                lambda _e: (interfaz.page.pop_dialog(), interfaz.compartir_whatsapp(ruta_especifica=ruta_excel)),
            ),
        ],
    )
    interfaz.page.show_dialog(dialogo)



