"""Diálogo para procesamiento de comprobantes y descuentos de Mercado Libre Full."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from typing import Any

import flet as ft

from ...orders import calcular_hash_archivo
from ...parsers.mercado_full_parser import parsear_archivo_mercado_full
from ..theme import ROJO
from ._shared import resolve_stock_manager


def _get_stock_manager(interfaz: Any = None):
    return resolve_stock_manager(interfaz)


def _construir_fila_preview_full(
    interfaz: Any,
    codigo: str,
    cant: int,
    catalogo: dict[str, Any],
) -> ft.Container:
    nom = catalogo.get(codigo, ("", "Producto no encontrado en catálogo", 0))[1]
    stk_actual = catalogo.get(codigo, ("", "", 0))[2]
    stk_nuevo = stk_actual - cant

    color_alerta = None
    alerta_txt = ""
    if codigo not in catalogo:
        color_alerta = ft.Colors.RED_400
        alerta_txt = " [NO EXISTE]"
    elif stk_nuevo < 0:
        color_alerta = ft.Colors.RED_400
        alerta_txt = f" [NEGATIVO: {stk_nuevo}]"
    elif stk_nuevo <= 5:
        color_alerta = ft.Colors.AMBER_400
        alerta_txt = " [QUIEBRE]"

    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        border_radius=6,
        bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
        content=ft.Row(
            [
                ft.Text(f"[{codigo}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                ft.Text(nom, size=11, expand=True, no_wrap=True),
                ft.Text(f"-{cant} un.", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400, size=11, width=65),
                ft.Text(
                    f"Stock: {stk_actual} -> {stk_nuevo}{alerta_txt}",
                    size=11,
                    color=color_alerta or interfaz.secundario,
                    width=150,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )


def _archivar_y_registrar_full(
    interfaz: Any,
    arch: Path,
    items_a_descontar: dict[str, int],
    stock_manager_factory: Any = _get_stock_manager,
) -> None:
    """Ejecuta el descuento de Mercado Full, archiva el Excel y registra el pedido."""
    sm = stock_manager_factory()(interfaz.menu.ruta_excel_base)
    res = sm.descontar_mercado_full(
        items_a_descontar,
        nombre_archivo=arch.name,
        sincronizar_excel=True,
    )
    print(f"[OK] Mercado Full: {len(res)} productos descontados desde {arch.name}.")

    dest = interfaz.menu.carpeta_descontados / "MercadoFull"
    dest.mkdir(parents=True, exist_ok=True)
    ruta_archivada = dest / arch.name
    shutil.move(str(arch), str(ruta_archivada))
    print(f"[OK] Archivo movido a: {ruta_archivada}")

    if not (hasattr(interfaz, "order_store") and interfaz.order_store):
        return

    armador_nom = (
        interfaz.usuario_actual.nombre_identificador
        if getattr(interfaz, "usuario_actual", None)
        else "Picker"
    )
    total_unidades = sum(items_a_descontar.values())
    nota_full = f"FULL-{arch.stem}"
    if interfaz.order_store.existe_nota_pedido(nota_full):
        nota_full = f"{nota_full}_{datetime.now().strftime('%H%M%S')}"

    catalogo = getattr(sm, "catalogo", {})
    items_pedido = [
        (cod, catalogo[cod][1] if cod in catalogo else f"Producto {cod}", cant)
        for cod, cant in items_a_descontar.items()
    ]
    hash_full = calcular_hash_archivo(ruta_archivada) if ruta_archivada.exists() else ""
    resumen_it = f"{len(items_a_descontar)} productos ({total_unidades} un.)"
    try:
        interfaz.order_store.registrar_pedido(
            nota_pedido=nota_full,
            numero_pedido=arch.stem,
            cliente="Mercado Envíos Full",
            bultos=1,
            logistica="Transporte",
            armador=armador_nom,
            tipo_archivo="excel",
            nombre_archivo=arch.name,
            agregado=False,
            articulos_descontados=total_unidades,
            resumen_items=resumen_it,
            fecha_retiro=datetime.now().strftime("%Y-%m-%d"),
            archivo_descuento="",
            items=items_pedido,
            archivo_hash=hash_full,
        )
    except Exception as exc_order:
        print(f"[WARN] No se pudo registrar pedido en store para Mercado Full: {exc_order}")


def _listar_planillas_full(interfaz: Any, carpeta_full: Path) -> list[Path]:
    if hasattr(interfaz.menu, "_obtener_pendientes_mercado_full"):
        return interfaz.menu._obtener_pendientes_mercado_full()
    archivos: list[Path] = []
    for ext in ("*.xlsx", "*.xls"):
        archivos.extend(carpeta_full.glob(ext))
    archivos.sort()
    return archivos


def mostrar_descuento_mercado_full(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para procesar comprobantes de Mercado Envíos Full (.xlsx / .xls)."""
    if not interfaz.exigir_roles("administrador", "operador", "picker"):
        return

    carpeta_full = getattr(interfaz.menu, "carpeta_mercado_full", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "MercadoFull"
    )
    carpeta_full.mkdir(parents=True, exist_ok=True)
    archivos_pendientes = _listar_planillas_full(interfaz, carpeta_full)

    lista_previsualizacion = ft.ListView(expand=True, spacing=4, height=260)
    resumen_texto = ft.Text(
        "Selecciona un archivo para previsualizar los productos a descontar."
        if archivos_pendientes
        else "No hay planillas de Mercado Full (.xlsx o .xls) en la carpeta Descuentos/MercadoFull.",
        size=12,
        color=interfaz.secundario,
    )

    sm = _get_stock_manager(interfaz)(interfaz.menu.ruta_excel_base)
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
            lista_previsualizacion.controls.append(
                _construir_fila_preview_full(interfaz, cod, cant, sm.catalogo)
            )
        interfaz.page.update()

    selector_archivo = ft.Dropdown(
        label="Planilla Mercado Full (.xlsx / .xls)",
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
                cargar_previsualizacion_archivo(arch)
                break

    selector_archivo.on_change = cambiar_archivo_dropdown
    selector_archivo.on_select = cambiar_archivo_dropdown
    if archivo_seleccionado[0] is not None:
        cargar_previsualizacion_archivo(archivo_seleccionado[0])

    def al_subir_mercado_full(guardados: list[Path]) -> None:
        nonlocal archivos_pendientes
        archivos_pendientes = _listar_planillas_full(interfaz, carpeta_full)
        for g in guardados:
            if g not in archivos_pendientes:
                archivos_pendientes.append(g)
        selector_archivo.options = [ft.dropdown.Option(arch.name) for arch in archivos_pendientes]
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
        await interfaz.ejecutar_tarea(
            f"Descuento Mercado Full ({arch.name})",
            lambda: _archivar_y_registrar_full(
                interfaz,
                arch,
                items_a_descontar,
                lambda: _get_stock_manager(interfaz),
            ),
        )
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
