"""Diálogos para relevamiento de stock físico (operarios) y auditoría comparativa (administrador)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import flet as ft

from ...inventory import StockManager as _DefaultStockManager
from ...parsers.physical_stock_parser import parsear_excel_stock_fisico
from ..theme import ROJO
from .stock_fisico_views import (
    construir_fila_comparativa_sf,
    mostrar_comparativa_stock_fisico_admin,
)


def _get_stock_manager():
    """Devuelve StockManager vigente respetando mocks en src.flet_gui."""
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def _listar_planillas_stock_fisico(interfaz: Any, carpeta_sf: Path) -> list[Path]:
    """Obtiene planillas Excel pendientes en Descuentos/StockFisico."""
    if hasattr(interfaz.menu, "_obtener_pendientes_stock_fisico"):
        return interfaz.menu._obtener_pendientes_stock_fisico()
    archivos: list[Path] = []
    for ext in ("*.xlsx", "*.xls"):
        archivos.extend(carpeta_sf.glob(ext))
    archivos.sort()
    return archivos


def mostrar_stock_fisico_operario(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para que los operarios carguen su conteo físico y detecten discrepancias."""
    if not interfaz.exigir_roles("operador"):
        return

    carpeta_sf = getattr(interfaz.menu, "carpeta_stock_fisico", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "StockFisico"
    )
    carpeta_sf.mkdir(parents=True, exist_ok=True)
    archivos_pendientes = _listar_planillas_stock_fisico(interfaz, carpeta_sf)

    lista_comparativa = ft.ListView(expand=True, spacing=4, height=280)
    resumen_texto = ft.Text(
        "Selecciona una planilla Excel para comparar el stock físico con el stock digital."
        if archivos_pendientes
        else "No hay planillas de stock físico (.xlsx o .xls) en Descuentos/StockFisico.",
        size=12,
        color=interfaz.secundario,
    )

    sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
    items_relevados: dict[str, int] = {}
    archivo_seleccionado: list[Path | None] = [archivos_pendientes[0] if archivos_pendientes else None]

    def cargar_comparativa_archivo(arch: Path) -> None:
        items_relevados.clear()
        lista_comparativa.controls.clear()
        try:
            totales, _ = parsear_excel_stock_fisico(arch)
        except Exception as e:
            resumen_texto.value = f"Error al leer {arch.name}: {e}"
            resumen_texto.color = ft.Colors.RED_400
            interfaz.page.update()
            return

        if not totales:
            resumen_texto.value = f"El archivo {arch.name} no contiene productos o columnas válidas."
            resumen_texto.color = ft.Colors.AMBER_400
            interfaz.page.update()
            return

        items_relevados.update(totales)
        comparativa = sm.comparar_stock_fisico(totales)
        coinciden = sum(1 for i in comparativa if i["diferencia"] == 0 and i["en_catalogo"])
        faltantes = sum(1 for i in comparativa if i["diferencia"] < 0 and i["en_catalogo"])
        sobrantes = sum(1 for i in comparativa if i["diferencia"] > 0 and i["en_catalogo"])

        resumen_texto.value = (
            f"Archivo: {arch.name} | Relevados: {len(comparativa)} | "
            f"Coinciden: {coinciden} | Faltantes: {faltantes} | Sobrantes: {sobrantes}"
        )
        resumen_texto.color = interfaz.texto

        for item in comparativa:
            lista_comparativa.controls.append(
                construir_fila_comparativa_sf(
                    interfaz,
                    codigo=item["code"],
                    nombre=item["name"],
                    stock_digital=item["stock_digital"],
                    stock_fisico=item["stock_fisico"],
                    diferencia=item["diferencia"],
                    estado=item["estado"],
                    modo_admin=False,
                )
            )
        interfaz.page.update()

    selector_archivo = ft.Dropdown(
        label="Planilla de Stock Físico (.xlsx / .xls)",
        options=[ft.dropdown.Option(arch.name) for arch in archivos_pendientes],
        value=archivos_pendientes[0].name if archivos_pendientes else None,
        expand=True,
        dense=True,
    )

    def cambiar_archivo_dropdown(_e: ft.Event) -> None:
        nombre = selector_archivo.value
        for arch in archivos_pendientes:
            if arch.name == nombre:
                archivo_seleccionado[0] = arch
                cargar_comparativa_archivo(arch)
                break

    selector_archivo.on_change = cambiar_archivo_dropdown
    selector_archivo.on_select = cambiar_archivo_dropdown
    if archivo_seleccionado[0] is not None:
        cargar_comparativa_archivo(archivo_seleccionado[0])

    def al_subir_stock_fisico(guardados: list[Path]) -> None:
        nonlocal archivos_pendientes
        archivos_pendientes = _listar_planillas_stock_fisico(interfaz, carpeta_sf)
        for g in guardados:
            if g not in archivos_pendientes:
                archivos_pendientes.append(g)
        selector_archivo.options = [ft.dropdown.Option(arch.name) for arch in archivos_pendientes]
        ultimo = guardados[-1]
        archivo_seleccionado[0] = ultimo
        selector_archivo.value = ultimo.name
        cargar_comparativa_archivo(ultimo)

    async def subir_sf_desde_pc(_e: ft.Event) -> None:
        await interfaz.subir_archivos_desde_pc(
            carpeta_destino=carpeta_sf,
            extensiones=["xlsx", "xls"],
            titulo="Seleccionar planilla de Stock Físico (.xlsx, .xls)",
            al_terminar=al_subir_stock_fisico,
        )

    async def confirmar_stock_fisico(_e: ft.Event) -> None:
        if not interfaz.exigir_roles("operador"):
            return
        if not archivo_seleccionado[0] or not items_relevados:
            interfaz.notificar("No hay un archivo válido con conteo físico para registrar.")
            return

        arch = archivo_seleccionado[0]
        operario_nom = interfaz.usuario_actual.nombre_identificador if interfaz.usuario_actual else "operador"
        interfaz.page.pop_dialog()
        ruta_generada: list[Path | None] = [None]

        def ejecutar() -> None:
            sm_exec = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            ruta_doc, comp = sm_exec.procesar_stock_fisico(
                items_relevados,
                usuario=operario_nom,
                nombre_archivo=arch.name,
            )
            ruta_generada[0] = ruta_doc
            con_dif = sum(1 for i in comp if i["diferencia"] != 0)
            print(f"[OK] Stock físico actualizado por '{operario_nom}': {len(comp)} productos ({con_dif} con diferencia).")
            print(f"[OK] Documento unificado para administrador: {ruta_doc}")
            dest = interfaz.menu.carpeta_descontados / "StockFisico"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(arch), str(dest / arch.name))

        await interfaz.ejecutar_tarea(f"Relevamiento de stock físico ({arch.name})", ejecutar)
        interfaz.actualizar_estado()
        doc_msg = f" Se generó el documento unificado '{ruta_generada[0].name}' y se notificó al administrador." if ruta_generada[0] else ""
        interfaz.notificar(f"Stock físico actualizado y comparado exitosamente.{doc_msg}")

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.ASSIGNMENT_TURNED_IN, color=ROJO), ft.Text("Hacer Stock Físico y Comparar con Digital", size=16, weight=ft.FontWeight.BOLD)], spacing=8),
        content=ft.Container(
            width=680,
            content=ft.Column(
                [
                    ft.Text(
                        "Lee la planilla Excel desde Descuentos/StockFisico, actualiza el stock físico, "
                        "compara con el stock digital mostrando diferencias y genera el documento unificado para el administrador.",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=10),
                    ft.Row(
                        [
                            selector_archivo,
                            ft.Button("Subir desde mi PC", icon=ft.Icons.UPLOAD_FILE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=subir_sf_desde_pc),
                            ft.TextButton("Abrir carpeta", icon=ft.Icons.FOLDER_OPEN, on_click=lambda _e: interfaz.abrir_carpeta_informe(carpeta_sf)),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    resumen_texto,
                    ft.Divider(height=10),
                    ft.Text("Comparativa Stock Digital vs. Stock Físico:", size=12, weight=ft.FontWeight.BOLD),
                    lista_comparativa,
                ],
                tight=True,
                spacing=6,
            ),
        ),
        actions=[
            ft.TextButton(
                "Relevar en Vivo (Cámara / Escáner)",
                icon=ft.Icons.DOCUMENT_SCANNER,
                on_click=lambda _e: (interfaz.page.pop_dialog(), interfaz.mostrar_dialogo_inventario_vivo()),
            ),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo("Confirmar y Notificar Admin", confirmar_stock_fisico),
        ],
    )
    interfaz.page.show_dialog(dialogo)


__all__ = [
    "_get_stock_manager",
    "mostrar_comparativa_stock_fisico_admin",
    "mostrar_stock_fisico_operario",
    "safe_focus",
]
