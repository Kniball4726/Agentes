"""Diálogo para procesamiento de comprobantes y descuentos de Mercado Libre Full."""
from datetime import datetime
import inspect
from pathlib import Path
import shutil
import sys
from typing import Any
import flet as ft

from ..theme import ROJO
from ...agent import AgenteRemitosStock
from ...mercado_full_parser import parsear_archivo_mercado_full
from ...orders_store import calcular_hash_archivo
from ...paths import application_root
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

def mostrar_descuento_mercado_full(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para procesar comprobantes de Mercado Envíos Full (.xlsx / .xls)."""
    if not interfaz.exigir_roles("administrador", "operador", "picker"):
        return

    carpeta_full = getattr(interfaz.menu, "carpeta_mercado_full", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "MercadoFull"
    )
    carpeta_full.mkdir(parents=True, exist_ok=True)
    archivos_pendientes: list[Path] = []
    if hasattr(interfaz.menu, "_obtener_pendientes_mercado_full"):
        archivos_pendientes = interfaz.menu._obtener_pendientes_mercado_full()
    else:
        for ext in ("*.xlsx", "*.xls"):
            archivos_pendientes.extend(carpeta_full.glob(ext))
        archivos_pendientes.sort()

    lista_previsualizacion = ft.ListView(
        expand=True,
        spacing=4,
        height=260,
    )

    resumen_texto = ft.Text(
        "Selecciona un archivo para previsualizar los productos a descontar."
        if archivos_pendientes
        else "No hay planillas de Mercado Full (.xlsx o .xls) en la carpeta Descuentos/MercadoFull.",
        size=12,
        color=interfaz.secundario,
    )

    sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
    items_a_descontar: dict[str, int] = {}
    archivo_seleccionado: list[Path | None] = [archivos_pendientes[0] if archivos_pendientes else None]

    def cargar_previsualizacion_archivo(arch: Path) -> None:
        items_a_descontar.clear()
        lista_previsualizacion.controls.clear()
        try:
            totales, _ = parsear_archivo_mercado_full(arch)
        except Exception as e:
            resumen_texto.value = f"Error al leer {arch.name}: {e}"
            resumen_texto.color = ft.Colors.RED_400
            interfaz.page.update()
            return

        if not totales:
            resumen_texto.value = f"El archivo {arch.name} no contiene productos o columnas reconocidas."
            resumen_texto.color = ft.Colors.AMBER_400
            interfaz.page.update()
            return

        items_a_descontar.update(totales)
        total_unidades = sum(totales.values())
        resumen_texto.value = (
            f"Archivo: {arch.name} | {len(totales)} productos a descontar ({total_unidades} unidades en total)."
        )
        resumen_texto.color = interfaz.texto

        for cod, cant in totales.items():
            nom = sm.catalogo.get(cod, ("", "Producto no encontrado en catálogo", 0))[1]
            stk_actual = sm.catalogo.get(cod, ("", "", 0))[2]
            stk_nuevo = stk_actual - cant

            color_alerta = None
            alerta_txt = ""
            if cod not in sm.catalogo:
                color_alerta = ft.Colors.RED_400
                alerta_txt = " [NO EXISTE]"
            elif stk_nuevo < 0:
                color_alerta = ft.Colors.RED_400
                alerta_txt = f" [NEGATIVO: {stk_nuevo}]"
            elif stk_nuevo <= 5:
                color_alerta = ft.Colors.AMBER_400
                alerta_txt = " [QUIEBRE]"

            lista_previsualizacion.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                            ft.Text(nom, size=11, expand=True, no_wrap=True),
                            ft.Text(f"-{cant} un.", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400, size=11, width=65),
                            ft.Text(f"Stock: {stk_actual} -> {stk_nuevo}{alerta_txt}", size=11, color=color_alerta or interfaz.secundario, width=150),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        interfaz.page.update()

    opciones_dropdown = [
        ft.dropdown.Option(arch.name) for arch in archivos_pendientes
    ]
    selector_archivo = ft.Dropdown(
        label="Planilla Mercado Full (.xlsx / .xls)",
        options=opciones_dropdown,
        value=archivos_pendientes[0].name if archivos_pendientes else None,
        expand=True,
        dense=True,
    )

    def cambiar_archivo_dropdown(_e: ft.Event) -> None:
        nombre = selector_archivo.value
        for arch in archivos_pendientes:
            if arch.name == nombre:
                archivo_seleccionado[0] = arch
                cargar_previsualizacion_archivo(arch)
                break

    selector_archivo.on_change = cambiar_archivo_dropdown
    selector_archivo.on_select = cambiar_archivo_dropdown

    if archivo_seleccionado[0] is not None:
        cargar_previsualizacion_archivo(archivo_seleccionado[0])

    def al_subir_mercado_full(guardados: list[Path]) -> None:
        nonlocal archivos_pendientes
        if hasattr(interfaz.menu, "_obtener_pendientes_mercado_full"):
            archivos_pendientes = interfaz.menu._obtener_pendientes_mercado_full()
        else:
            archivos_pendientes = []
            for ext in ("*.xlsx", "*.xls"):
                archivos_pendientes.extend(carpeta_full.glob(ext))
            archivos_pendientes.sort()
        for g in guardados:
            if g not in archivos_pendientes:
                archivos_pendientes.append(g)
        selector_archivo.options = [
            ft.dropdown.Option(arch.name) for arch in archivos_pendientes
        ]
        ultimo = guardados[-1]
        archivo_seleccionado[0] = ultimo
        selector_archivo.value = ultimo.name
        cargar_previsualizacion_archivo(ultimo)

    async def subir_full_desde_pc(_e: ft.Event) -> None:
        await interfaz.subir_archivos_desde_pc(
            carpeta_destino=carpeta_full,
            extensiones=["xlsx", "xls"],
            titulo="Seleccionar planilla de Mercado Full (.xlsx, .xls)",
            al_terminar=al_subir_mercado_full,
        )

    async def confirmar_descuento_full(_e: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador", "operador", "picker"):
            return
        if not archivo_seleccionado[0] or not items_a_descontar:
            interfaz.notificar("No hay un archivo válido con productos para descontar.")
            return

        arch = archivo_seleccionado[0]
        interfaz.page.pop_dialog()

        def ejecutar() -> None:
            sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            res = sm.descontar_mercado_full(
                items_a_descontar,
                nombre_archivo=arch.name,
                sincronizar_excel=True,
            )
            print(f"[OK] Mercado Full: {len(res)} productos descontados desde {arch.name}.")
            dest = interfaz.menu.carpeta_descontados / "MercadoFull"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(arch), str(dest / arch.name))
            print(f"[OK] Archivo movido a: {dest / arch.name}")

        await interfaz.ejecutar_tarea(f"Descuento Mercado Full ({arch.name})", ejecutar)
        interfaz.actualizar_estado()
        interfaz.notificar(f"Se descontaron exitosamente los productos de {arch.name} para Mercado Full.")

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.LOCAL_SHIPPING, color=ROJO),
                ft.Text("Descontar Mercado Envíos Full (Excel)", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=interfaz.ancho_adaptable(650) if hasattr(interfaz, "ancho_adaptable") else 650,
            content=ft.Column(
                [
                    ft.Text(
                        "Lee las planillas enviadas a Full desde Descuentos/MercadoFull y descuenta las unidades del depósito central.",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=10),
                    ft.Row(
                        [
                            selector_archivo,
                            ft.Button(
                                "Subir desde mi PC",
                                icon=ft.Icons.UPLOAD_FILE,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                on_click=subir_full_desde_pc,
                            ),
                            ft.TextButton(
                                "Abrir carpeta",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=lambda _e: interfaz.abrir_carpeta_informe(carpeta_full),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    resumen_texto,
                    ft.Divider(height=10),
                    ft.Text("Previsualización de impacto en stock:", size=12, weight=ft.FontWeight.BOLD),
                    lista_previsualizacion,
                ],
                tight=True,
                spacing=6,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo("Confirmar Descuento", confirmar_descuento_full),
        ],
    )
    interfaz.page.show_dialog(dialogo)


