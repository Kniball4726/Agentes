"""Pestaña por archivo y helpers de ejecución para Ingreso de Fábrica."""

from __future__ import annotations

import asyncio
import inspect
import shutil
import sys
from pathlib import Path
from typing import Any

import flet as ft

from ...inventory import StockManager as _DefaultStockManager
from ...parsers.factory_parser import parsear_archivo_fabrica
from ..theme import ROJO


def resolver_stock_manager_fabrica():
    """Resuelve StockManager respetando patches sobre dlg_ingreso_fabrica, dlg_stock_ops o src.flet_gui."""
    mod_ing = sys.modules.get("src.ui.dialogs.dlg_ingreso_fabrica")
    if mod_ing is not None and hasattr(mod_ing, "_get_stock_manager"):
        return mod_ing._get_stock_manager()
    mod_ops = sys.modules.get("src.ui.dialogs.dlg_stock_ops")
    if mod_ops is not None and hasattr(mod_ops, "_get_stock_manager"):
        return mod_ops._get_stock_manager()
    mod = sys.modules.get("src.flet_gui")
    if mod is not None and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def ejecutar_tarea_compatible(interfaz: Any, titulo: str, fn: Any) -> None:
    """Ejecuta `interfaz.ejecutar_tarea` tanto si es corrutina como función síncrona."""
    if inspect.iscoroutinefunction(interfaz.ejecutar_tarea):
        if hasattr(interfaz.page, "run_task") and callable(interfaz.page.run_task):
            interfaz.page.run_task(interfaz.ejecutar_tarea, titulo, fn)
        else:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(interfaz.ejecutar_tarea(titulo, fn))
                else:
                    loop.run_until_complete(interfaz.ejecutar_tarea(titulo, fn))
            except Exception:
                fn()
    else:
        interfaz.ejecutar_tarea(titulo, fn)


def registrar_ingreso_escaner(interfaz: Any, items_escaneados: dict[str, int], sobrescribir: bool) -> None:
    """Persiste el ingreso acumulado por escáner, movimientos y auditoría."""
    rol_actual = getattr(getattr(interfaz, "usuario_actual", None), "role", "")
    sobrescribir_seguro = bool(sobrescribir) and rol_actual == "administrador"
    total_unidades = sum(items_escaneados.values())
    cant_prods = len(items_escaneados)
    usr = getattr(interfaz.usuario_actual, "username", "operador")
    copia_items = dict(items_escaneados)

    def aplicar_ingreso() -> None:
        sm = resolver_stock_manager_fabrica()(interfaz.menu.ruta_excel_base)
        res = sm.registrar_ingreso_fabrica(copia_items, sobrescribir=sobrescribir_seguro)
        print(f"[OK] Ingreso fábrica: {len(res)} productos actualizados.")
        for cod, (ant, nvo) in res.items():
            print(f"     Código {cod}: {ant} -> {nvo}")

        if hasattr(sm, "product_store"):
            try:
                movs = [
                    (cod, sm.catalogo.get(cod, (0, cod, 0))[1], qty, "ingreso_fabrica")
                    for cod, qty in copia_items.items()
                ]
                sm.product_store.register_movements(movs, usuario=usr, detalle="Ingreso de Fábrica (Escáner)")
            except Exception:
                pass

        if hasattr(interfaz, "order_store") and hasattr(interfaz.order_store, "registrar_auditoria"):
            try:
                interfaz.order_store.registrar_auditoria(
                    usuario=usr,
                    accion="INGRESO_FABRICA",
                    detalle=f"Ingreso de {total_unidades} unidades ({cant_prods} productos)",
                )
            except Exception:
                pass

    ejecutar_tarea_compatible(interfaz, "Ingreso de mercadería de fábrica", aplicar_ingreso)
    interfaz.notificar(f"✔ Ingreso registrado con éxito: {total_unidades} unidades ({cant_prods} productos) agregadas al stock.")
    interfaz.actualizar_estado()


def construir_tab_archivo_fabrica(interfaz: Any, modo_sobrescribir: ft.Checkbox):
    """Construye la pestaña de carga por archivos para administrador y devuelve (vista, procesar_fn)."""
    lista_archivos_fabrica = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=180)
    archivos_pendientes = interfaz.menu._obtener_pendientes_fabrica()

    def refrescar_archivos_fabrica() -> None:
        lista_archivos_fabrica.controls.clear()
        nonlocal archivos_pendientes
        archivos_pendientes = interfaz.menu._obtener_pendientes_fabrica()
        if archivos_pendientes:
            for a in archivos_pendientes:
                lista_archivos_fabrica.controls.append(
                    ft.Row([ft.Icon(ft.Icons.DESCRIPTION, size=18, color=ROJO), ft.Text(a.name, expand=True, size=13)])
                )
        else:
            lista_archivos_fabrica.controls.append(
                ft.Text(
                    "No hay archivos en Descuentos/Fabrica.\n"
                    "Coloca archivos Excel (.xlsx, .xls) o PDF de remito de fábrica allí.",
                    size=12,
                    color=interfaz.secundario,
                )
            )
        interfaz.page.update()

    def procesar_archivos_fabrica(_e: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        if not archivos_pendientes:
            interfaz.notificar("No hay archivos para procesar en Descuentos/Fabrica.")
            return
        interfaz.page.pop_dialog()
        sobr = modo_sobrescribir.value
        lote_archivos = list(archivos_pendientes)

        def ejecutar() -> None:
            sm = resolver_stock_manager_fabrica()(interfaz.menu.ruta_excel_base)
            total_archivos = 0
            for arch in lote_archivos:
                totales, _ = parsear_archivo_fabrica(arch)
                if not totales:
                    print(f"[AVISO] Sin items válidos en {arch.name}")
                    continue
                res = sm.registrar_ingreso_fabrica(totales, sobrescribir=sobr)
                print(f"[OK] {arch.name}: {len(res)} productos actualizados.")
                for cod, (ant, nvo) in res.items():
                    print(f"     Código {cod}: {ant} -> {nvo}")

                dest = interfaz.menu.carpeta_descontados / "Fabrica"
                dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(arch), str(dest / arch.name))
                total_archivos += 1
            print(f"[FINALIZADO] {total_archivos} archivo(s) procesados y archivados.")

        ejecutar_tarea_compatible(interfaz, "Ingreso de pedido de fábrica", ejecutar)
        interfaz.actualizar_estado()

    carpeta_fabrica = getattr(interfaz.menu, "carpeta_fabrica", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "Fabrica"
    )

    async def subir_fabrica_desde_pc(_e: ft.Event) -> None:
        await interfaz.subir_archivos_desde_pc(
            carpeta_destino=carpeta_fabrica,
            extensiones=["xlsx", "xls", "pdf"],
            titulo="Seleccionar pedido de fábrica (.xlsx, .xls, .pdf)",
            al_terminar=lambda _guardados: refrescar_archivos_fabrica(),
        )

    vista_archivo = ft.Container(
        padding=10,
        content=ft.Column(
            [
                ft.Text("Archivos pendientes en Descuentos/Fabrica (.xlsx, .xls, .pdf):", size=12, weight=ft.FontWeight.BOLD),
                lista_archivos_fabrica,
                ft.Row(
                    [
                        ft.Button("Subir archivo desde mi PC", icon=ft.Icons.UPLOAD_FILE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=subir_fabrica_desde_pc),
                        ft.TextButton("Abrir carpeta Fabrica", icon=ft.Icons.FOLDER, on_click=lambda _e: interfaz.abrir_carpeta_informe(carpeta_fabrica)),
                        ft.TextButton("Actualizar", icon=ft.Icons.REFRESH, on_click=lambda _e: refrescar_archivos_fabrica()),
                    ]
                ),
            ],
            tight=True,
        ),
        visible=False,
    )
    refrescar_archivos_fabrica()
    return vista_archivo, procesar_archivos_fabrica
