"""Diálogos para relevamiento de stock físico (operarios) y auditoría comparativa (administrador)."""
from datetime import datetime
import inspect
from pathlib import Path
import shutil
import sys
from typing import Any
import flet as ft

from ..theme import ROJO
from ...agent import AgenteRemitosStock
from ...physical_stock_parser import parsear_excel_stock_fisico
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

def mostrar_stock_fisico_operario(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para que los operarios carguen su conteo físico y detecten discrepancias."""
    if not interfaz.exigir_roles("operador"):
        return

    carpeta_sf = getattr(interfaz.menu, "carpeta_stock_fisico", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "StockFisico"
    )
    carpeta_sf.mkdir(parents=True, exist_ok=True)
    archivos_pendientes: list[Path] = []
    if hasattr(interfaz.menu, "_obtener_pendientes_stock_fisico"):
        archivos_pendientes = interfaz.menu._obtener_pendientes_stock_fisico()
    else:
        for ext in ("*.xlsx", "*.xls"):
            archivos_pendientes.extend(carpeta_sf.glob(ext))
        archivos_pendientes.sort()

    lista_comparativa = ft.ListView(
        expand=True,
        spacing=4,
        height=280,
    )

    resumen_texto = ft.Text(
        "Selecciona una planilla Excel para comparar el stock físico con el stock digital."
        if archivos_pendientes
        else "No hay planillas de stock físico (.xlsx o .xls) en Descuentos/StockFisico.",
        size=12,
        color=interfaz.secundario,
    )

    sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
    items_relevados: dict[str, int] = {}
    archivo_seleccionado: list[Path | None] = [
        archivos_pendientes[0] if archivos_pendientes else None
    ]

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
            resumen_texto.value = (
                f"El archivo {arch.name} no contiene productos o columnas válidas."
            )
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
            cod = item["code"]
            nom = item["name"]
            stk_dig = item["stock_digital"]
            stk_fis = item["stock_fisico"]
            dif = item["diferencia"]
            estado = item["estado"]
            dif_str = f"+{dif}" if dif > 0 else str(dif)

            if estado == "COINCIDE":
                color_est = ft.Colors.GREEN_500
            elif estado in ("FALTANTE", "NO_CATALOGADO"):
                color_est = ft.Colors.RED_400
            else:
                color_est = ft.Colors.AMBER_400

            lista_comparativa.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=75),
                            ft.Text(nom, size=11, expand=True, no_wrap=True),
                            ft.Text(
                                f"Dig: {stk_dig} | Fís: {stk_fis}",
                                size=11,
                                color=interfaz.texto,
                                width=120,
                            ),
                            ft.Text(
                                f"Dif: {dif_str} [{estado}]",
                                weight=ft.FontWeight.BOLD,
                                size=11,
                                color=color_est,
                                width=145,
                            ),
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
        label="Planilla de Stock Físico (.xlsx / .xls)",
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
                cargar_comparativa_archivo(arch)
                break

    selector_archivo.on_change = cambiar_archivo_dropdown
    selector_archivo.on_select = cambiar_archivo_dropdown

    if archivo_seleccionado[0] is not None:
        cargar_comparativa_archivo(archivo_seleccionado[0])

    def al_subir_stock_fisico(guardados: list[Path]) -> None:
        nonlocal archivos_pendientes
        if hasattr(interfaz.menu, "_obtener_pendientes_stock_fisico"):
            archivos_pendientes = interfaz.menu._obtener_pendientes_stock_fisico()
        else:
            archivos_pendientes = []
            for ext in ("*.xlsx", "*.xls"):
                archivos_pendientes.extend(carpeta_sf.glob(ext))
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
            sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            ruta_doc, comp = sm.procesar_stock_fisico(
                items_relevados,
                usuario=operario_nom,
                nombre_archivo=arch.name,
            )
            ruta_generada[0] = ruta_doc
            con_dif = sum(1 for i in comp if i["diferencia"] != 0)
            print(
                f"[OK] Stock físico actualizado por '{operario_nom}': "
                f"{len(comp)} productos ({con_dif} con diferencia)."
            )
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
        title=ft.Row(
            [
                ft.Icon(ft.Icons.ASSIGNMENT_TURNED_IN, color=ROJO),
                ft.Text("Hacer Stock Físico y Comparar con Digital", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
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
                            ft.Button(
                                "Subir desde mi PC",
                                icon=ft.Icons.UPLOAD_FILE,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                on_click=subir_sf_desde_pc,
                            ),
                            ft.TextButton(
                                "Abrir carpeta",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=lambda _e: interfaz.abrir_carpeta_informe(carpeta_sf),
                            ),
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


def mostrar_comparativa_stock_fisico_admin(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para que la administración supervise y descargue auditorías de inventario físico."""
    if not interfaz.exigir_roles("administrador"):
        return

    sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
    inventarios = sm.listar_inventarios_fisicos(limit=25)

    lista_detalles = ft.ListView(
        expand=True,
        spacing=4,
        height=300,
    )

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
            cod = str(d["product_code"])
            nom = str(d["product_name"])
            stk_dig = int(d["stock_digital"])
            stk_fis = int(d["stock_fisico"])
            estado = str(d["estado"])
            dif_str = f"+{dif}" if dif > 0 else str(dif)

            if estado == "COINCIDE":
                color_est = ft.Colors.GREEN_500
            elif estado in ("FALTANTE", "NO_CATALOGADO"):
                color_est = ft.Colors.RED_400
            else:
                color_est = ft.Colors.AMBER_400

            lista_detalles.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=75),
                            ft.Text(nom, size=11, expand=True, no_wrap=True),
                            ft.Text(f"Digital: {stk_dig}", size=11, width=85),
                            ft.Text(f"Físico: {stk_fis}", size=11, width=85),
                            ft.Text(
                                f"Dif: {dif_str} [{estado}]",
                                weight=ft.FontWeight.BOLD,
                                size=11,
                                color=color_est,
                                width=145,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
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
                [
                    ft.Row([selector_inv], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    resumen_admin,
                    solo_diferencias,
                    ft.Divider(height=6),
                    lista_detalles,
                ],
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
            ft.TextButton(
                "Descargar / Abrir Documento Unificado (Excel)",
                icon=ft.Icons.DOWNLOAD,
                on_click=abrir_documento_unificado,
            ),
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)

