"""Diálogos y operaciones de stock: ingresos de fábrica, reposición, Mercado Libre (Full y DOCX) y relevamiento físico."""

from datetime import datetime
from pathlib import Path
import shutil
from typing import Any

import flet as ft

from ..theme import ROJO
from ...agent import AgenteRemitosStock
from ...factory_parser import parsear_archivo_fabrica
from ...mercado_full_parser import parsear_archivo_mercado_full
from ...mercado_libre_parser import parsear_pedido_mercado_libre
from ...orders_store import calcular_hash_archivo
from ...paths import application_root
from ...physical_stock_parser import parsear_excel_stock_fisico
from ...remito_parser import ResultadoRemito, normalizar_codigo
import sys
from ...stock_manager import StockManager as _DefaultStockManager

def _get_stock_manager():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager



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


def mostrar_ingreso_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para ajustar stock manual o ingresar mercadería desde remitos/planillas de fábrica."""
    if not interfaz.exigir_roles("administrador"):
        return

    stock_manager = _get_stock_manager()(interfaz.menu.ruta_excel_base)
    modo_sobrescribir = ft.Checkbox(
        label="Sobrescribir stock (establece el valor exacto indicado)",
        value=False,
    )

    # Tab 1: Carga manual
    campo_cod = ft.TextField(label="Código de producto", width=150)
    campo_cant = ft.TextField(
        label="Cantidad (negativo para descontar)",
        width=150,
        keyboard_type=ft.KeyboardType.NUMBER,
        hint_text="Ej: 10 o -5",
    )
    texto_info_prod = ft.Text("", size=12, color=interfaz.secundario)
    lista_cargas = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=180)
    items_cargados: dict[str, int] = {}

    def verificar_codigo(_e: ft.Event | None = None) -> None:
        c = (campo_cod.value or "").strip()
        if not c:
            texto_info_prod.value = ""
        elif c in stock_manager.catalogo:
            _, nom, st = stock_manager.catalogo[c]
            texto_info_prod.value = f"✔ {nom} (Stock actual: {st})"
            texto_info_prod.color = ft.Colors.GREEN_400
        else:
            texto_info_prod.value = "✖ Código no encontrado en catálogo"
            texto_info_prod.color = ft.Colors.RED_400
        interfaz.page.update()

    campo_cod.on_change = verificar_codigo

    def refrescar_lista_manual() -> None:
        lista_cargas.controls.clear()
        for c, cant in items_cargados.items():
            nom = stock_manager.catalogo[c][1]
            lista_cargas.controls.append(
                ft.Row(
                    [
                        ft.Text(c, width=70, weight=ft.FontWeight.BOLD),
                        ft.Text(nom, expand=True, size=12),
                        ft.Text(
                            f"={cant}" if modo_sobrescribir.value else (f"−{abs(cant)}" if cant < 0 else f"+{cant}"),
                            width=60,
                            color=ft.Colors.RED_400 if (cant < 0 and not modo_sobrescribir.value) else (ft.Colors.GREEN_400 if cant > 0 else interfaz.texto),
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=18,
                            on_click=lambda _e, code=c: eliminar_item(code),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )
        if not items_cargados:
            lista_cargas.controls.append(
                ft.Text("No hay productos en la lista.", size=12, color=interfaz.secundario)
            )
        interfaz.page.update()

    def eliminar_item(code: str) -> None:
        items_cargados.pop(code, None)
        refrescar_lista_manual()

    def agregar_item(_e: ft.Event) -> None:
        c = (campo_cod.value or "").strip()
        cant_str = (campo_cant.value or "").strip()
        if not c or c not in stock_manager.catalogo:
            interfaz.notificar("Ingrese un código de producto válido.")
            return
        try:
            cant = int(cant_str)
            if cant == 0:
                interfaz.notificar("La cantidad no puede ser 0.")
                return
        except ValueError:
            interfaz.notificar("La cantidad debe ser un número entero.")
            return
        items_cargados[c] = cant
        campo_cod.value = ""
        campo_cant.value = ""
        texto_info_prod.value = ""
        refrescar_lista_manual()

    async def guardar_manual(_e: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        if not items_cargados:
            interfaz.notificar("Agrega al menos un producto.")
            return
        interfaz.page.pop_dialog()
        sobr = modo_sobrescribir.value

        def aplicar() -> None:
            sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            res = sm.registrar_ingreso_fabrica(items_cargados, sobrescribir=sobr)
            print(f"[OK] Se actualizaron {len(res)} productos en catálogo y Excel:")
            for cod, (ant, nvo) in res.items():
                print(f"     Código {cod}: {ant} -> {nvo}")

        await interfaz.ejecutar_tarea("Ajuste manual de stock", aplicar)
        interfaz.actualizar_estado()

    # Tab 2: Carga por archivo en Descuentos/Fabrica
    lista_archivos_fabrica = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=180)
    archivos_pendientes = interfaz.menu._obtener_pendientes_fabrica()

    def refrescar_archivos_fabrica() -> None:
        lista_archivos_fabrica.controls.clear()
        nonlocal archivos_pendientes
        archivos_pendientes = interfaz.menu._obtener_pendientes_fabrica()
        if archivos_pendientes:
            for a in archivos_pendientes:
                lista_archivos_fabrica.controls.append(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.DESCRIPTION, size=18, color=ROJO),
                            ft.Text(a.name, expand=True, size=13),
                        ]
                    )
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

    async def procesar_archivos_fabrica(_e: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        if not archivos_pendientes:
            interfaz.notificar("No hay archivos para procesar en Descuentos/Fabrica.")
            return
        interfaz.page.pop_dialog()
        sobr = modo_sobrescribir.value

        def ejecutar() -> None:
            sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            total_archivos = 0
            for arch in archivos_pendientes:
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

        await interfaz.ejecutar_tarea("Ingreso de pedido de fábrica", ejecutar)
        interfaz.actualizar_estado()

    # Contenedores para las vistas de Manual vs Archivo
    vista_manual = ft.Container(
        padding=10,
        content=ft.Column(
            [
                ft.Row(
                    [
                        campo_cod,
                        campo_cant,
                        ft.Button(
                            "Agregar",
                            icon=ft.Icons.ADD,
                            on_click=agregar_item,
                            bgcolor=ROJO,
                            color=ft.Colors.WHITE,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                texto_info_prod,
                ft.Divider(height=10),
                ft.Text("Productos listos para aplicar:", weight=ft.FontWeight.BOLD, size=12),
                lista_cargas,
            ],
            tight=True,
        ),
        visible=True,
    )

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
                ft.Text(
                    "Archivos pendientes en Descuentos/Fabrica (.xlsx, .xls, .pdf):",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                ),
                lista_archivos_fabrica,
                ft.Row(
                    [
                        ft.Button(
                            "Subir archivo desde mi PC",
                            icon=ft.Icons.UPLOAD_FILE,
                            bgcolor=ROJO,
                            color=ft.Colors.WHITE,
                            on_click=subir_fabrica_desde_pc,
                        ),
                        ft.TextButton(
                            "Abrir carpeta Fabrica",
                            icon=ft.Icons.FOLDER,
                            on_click=lambda _e: interfaz.abrir_carpeta_informe(carpeta_fabrica),
                        ),
                        ft.TextButton(
                            "Actualizar",
                            icon=ft.Icons.REFRESH,
                            on_click=lambda _e: refrescar_archivos_fabrica(),
                        ),
                    ]
                ),
            ],
            tight=True,
        ),
        visible=False,
    )

    modo_actual = ["manual"]

    def cambiar_pestana(modo: str) -> None:
        modo_actual[0] = modo
        vista_manual.visible = (modo == "manual")
        vista_archivo.visible = (modo == "archivo")
        btn_tab_manual.style = ft.ButtonStyle(
            color=ft.Colors.WHITE if modo == "manual" else interfaz.secundario,
            bgcolor=ROJO if modo == "manual" else ft.Colors.TRANSPARENT,
        )
        btn_tab_archivo.style = ft.ButtonStyle(
            color=ft.Colors.WHITE if modo == "archivo" else interfaz.secundario,
            bgcolor=ROJO if modo == "archivo" else ft.Colors.TRANSPARENT,
        )
        interfaz.page.update()

    btn_tab_manual = ft.Button(
        "Carga manual",
        icon=ft.Icons.EDIT,
        on_click=lambda _e: cambiar_pestana("manual"),
        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ROJO),
    )
    btn_tab_archivo = ft.Button(
        "Por archivo (Fabrica)",
        icon=ft.Icons.FOLDER_OPEN,
        on_click=lambda _e: cambiar_pestana("archivo"),
        style=ft.ButtonStyle(color=interfaz.secundario, bgcolor=ft.Colors.TRANSPARENT),
    )

    refrescar_lista_manual()
    refrescar_archivos_fabrica()

    async def aplicar_segun_modo(e: ft.Event) -> None:
        if modo_actual[0] == "manual":
            await guardar_manual(e)
        else:
            await procesar_archivos_fabrica(e)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Ajustar stock / Cargar pedido de fábrica"),
        content=ft.Column(
            [
                modo_sobrescribir,
                ft.Row([btn_tab_manual, btn_tab_archivo], spacing=10),
                ft.Divider(height=1),
                vista_manual,
                vista_archivo,
            ],
            tight=True,
            width=550,
        ),
        actions=[
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo("Aplicar a stock", aplicar_segun_modo),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_descuento_mercado_full(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para procesar comprobantes de Mercado Envíos Full (.xlsx / .xls)."""
    if not interfaz.exigir_roles("administrador"):
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
        if not interfaz.exigir_roles("administrador"):
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
            width=650,
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


def mostrar_descuento_mercado_libre(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para procesar y descontar pedidos de Mercado Libre en formato .docx."""
    if not interfaz.exigir_roles("operador", "administrador", "master"):
        return

    carpeta_ml = getattr(interfaz.menu, "carpeta_mercado_libre", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "MercadoLibre"
    )
    carpeta_ml.mkdir(parents=True, exist_ok=True)

    archivo_seleccionado: list[Path | None] = [None]
    resultado_parseo: list[ResultadoRemito | None] = [None]
    items_a_descontar: dict[str, int] = {}

    lista_previsualizacion = ft.ListView(
        expand=True,
        spacing=4,
        height=260,
    )
    resumen_texto = ft.Text(
        "Selecciona o sube un archivo .docx de Mercado Libre para previsualizar los productos a descontar.",
        size=12,
        color=interfaz.secundario,
    )
    banner_no_encontrados = ft.Container(visible=False)

    def cargar_previsualizacion_docx(arch: Path) -> None:
        lista_previsualizacion.controls.clear()
        items_a_descontar.clear()
        banner_no_encontrados.visible = False
        sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
        productos_catalogo = [
            (codigo, nombre) for _, codigo, nombre, _ in sm.productos_base
        ]

        try:
            res = parsear_pedido_mercado_libre(arch, productos_catalogo)
            resultado_parseo[0] = res
        except Exception as e:
            resumen_texto.value = f"Error al leer el archivo {arch.name}: {e}"
            resumen_texto.color = ft.Colors.RED_400
            interfaz.page.update()
            return

        if not res.items:
            resumen_texto.value = f"El archivo {arch.name} no contiene líneas de productos reconocidas."
            resumen_texto.color = ft.Colors.AMBER_400
            interfaz.page.update()
            return

        total_unidades = sum(it.cantidad for it in res.items)
        for it in res.items:
            cod = normalizar_codigo(it.codigo)
            items_a_descontar[cod] = items_a_descontar.get(cod, 0) + it.cantidad

        resumen_texto.value = (
            f"Comprador: {res.cliente or 'No especificado'} | Paquete/Remito: {res.numero_remito or 'Sin número'} | "
            f"{len(items_a_descontar)} productos ({total_unidades} unidades a descontar)"
        )
        resumen_texto.color = interfaz.texto

        if res.descripciones_sin_coincidencia:
            lineas_aviso = [
                ft.Text(f"• {desc} ({motivo})", size=11, color=ft.Colors.AMBER_200 if interfaz.modo_oscuro else ft.Colors.AMBER_900)
                for desc, motivo in res.descripciones_sin_coincidencia
            ]
            banner_no_encontrados.visible = True
            banner_no_encontrados.content = ft.Container(
                bgcolor=ft.Colors.AMBER_900 if interfaz.modo_oscuro else ft.Colors.AMBER_100,
                border=ft.Border.all(1, ft.Colors.AMBER_600),
                border_radius=6,
                padding=8,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.AMBER_400, size=16),
                                ft.Text(
                                    "Líneas que no coincidieron con el catálogo (no se descontarán):",
                                    weight=ft.FontWeight.BOLD,
                                    size=11,
                                    color=ft.Colors.AMBER_200 if interfaz.modo_oscuro else ft.Colors.AMBER_900,
                                ),
                            ],
                            spacing=6,
                        ),
                        *lineas_aviso,
                    ],
                    spacing=4,
                ),
            )

        hash_candidato = calcular_hash_archivo(arch)
        duplicado = interfaz.order_store.buscar_pedido_por_hash(hash_candidato) if hash_candidato else None
        if duplicado:
            banner_no_encontrados.visible = True
            banner_no_encontrados.content = ft.Container(
                bgcolor=ft.Colors.RED_900 if interfaz.modo_oscuro else ft.Colors.RED_100,
                border=ft.Border.all(1, ft.Colors.RED_400),
                border_radius=6,
                padding=8,
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.BLOCK, color=ft.Colors.RED_400, size=18),
                        ft.Text(
                            f"⛔ ATENCIÓN: Este archivo ya fue descontado el {duplicado.created_at[:16]} "
                            f"(Comprobante: {duplicado.nota_pedido}).",
                            weight=ft.FontWeight.BOLD,
                            size=11,
                            color=ft.Colors.RED_200 if interfaz.modo_oscuro else ft.Colors.RED_900,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            )

        for cod, cant in items_a_descontar.items():
            nom = sm.catalogo.get(cod, ("", "Producto no encontrado", 0))[1]
            stk_actual = sm.catalogo.get(cod, ("", "", 0))[2]
            stk_nuevo = stk_actual - cant
            color_alerta = ft.Colors.RED_400 if stk_nuevo <= 0 else None
            alerta_txt = " (¡AGOTADO!)" if stk_nuevo <= 0 else ""

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

    archivos_pendientes: list[Path] = sorted(list(carpeta_ml.glob("*.docx")))

    opciones_dropdown = [
        ft.dropdown.Option(arch.name) for arch in archivos_pendientes
    ]
    selector_archivo = ft.Dropdown(
        label="Seleccionar pedido de Mercado Libre (.docx)",
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
                cargar_previsualizacion_docx(arch)
                break

    selector_archivo.on_change = cambiar_archivo_dropdown
    if archivos_pendientes:
        archivo_seleccionado[0] = archivos_pendientes[0]
        cargar_previsualizacion_docx(archivos_pendientes[0])

    def al_subir_docx(guardados: list[Path]) -> None:
        if not guardados:
            return
        nombres_existentes = {a.name for a in archivos_pendientes}
        for g in guardados:
            if g.name not in nombres_existentes:
                archivos_pendientes.append(g)
                nombres_existentes.add(g.name)
        selector_archivo.options = [
            ft.dropdown.Option(a.name) for a in archivos_pendientes
        ]
        arch = guardados[0]
        archivo_seleccionado[0] = arch
        selector_archivo.value = arch.name
        cargar_previsualizacion_docx(arch)
        interfaz.page.update()

    async def subir_desde_pc(_e: ft.Event) -> None:
        try:
            guardados = await interfaz.subir_archivos_desde_pc(
                carpeta_destino=carpeta_ml,
                extensiones=["docx"],
                titulo="Seleccionar pedido de Mercado Libre (.docx)",
                al_terminar=al_subir_docx,
            )
            if guardados:
                al_subir_docx(guardados)
        except Exception as err:
            interfaz.notificar(f"Error al subir archivo de Mercado Libre: {err}")

    async def confirmar_descuento_ml(_e: ft.Event) -> None:
        if not archivo_seleccionado[0] or not items_a_descontar:
            interfaz.notificar("Debes seleccionar un archivo .docx válido con productos para descontar.")
            return

        arch = archivo_seleccionado[0]
        hash_doc = calcular_hash_archivo(arch)
        if hash_doc:
            dup = interfaz.order_store.buscar_pedido_por_hash(hash_doc)
            if dup:
                interfaz.notificar(
                    f"⛔ Este archivo ya fue procesado el {dup.created_at[:16]} ({dup.nota_pedido}) y no puede volver a descontarse."
                )
                return

        res = resultado_parseo[0]
        armador_nom = interfaz.usuario_actual.nombre_identificador if interfaz.usuario_actual else "Operario"
        interfaz.page.pop_dialog()

        def ejecutar_descuento_ml() -> None:
            sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            agente = AgenteRemitosStock(stock_manager=sm)
            reporte = agente.ejecutar(
                rutas_mercado_libre=[arch],
                carpeta_descuentos=interfaz.menu.carpeta_descuentos,
                simulacion=False,
            )

            nombre_inf = Path(reporte.reporte_stock.archivo_guardado).name if reporte.reporte_stock.archivo_guardado else f"ML_{arch.stem}"
            sm.actualizar_stock_base(
                descuentos=reporte.reporte_stock.descuentos_aplicados,
                sincronizar_excel=True,
                nombre_archivo=nombre_inf,
                usuario=armador_nom,
            )

            pdf_nom = Path(reporte.reporte_stock.archivo_pdf).name if reporte.reporte_stock.archivo_pdf else ""
            total_desc = sum(d.cantidad_descontada for d in reporte.reporte_stock.descuentos_aplicados)
            resumen_items = f"{len(reporte.reporte_stock.descuentos_aplicados)} productos ({total_desc} un.)"

            nota_ml = (res.numero_remito or arch.stem).strip() if res else arch.stem
            if interfaz.order_store.existe_nota_pedido(nota_ml):
                nota_ml = f"{nota_ml}_{datetime.now().strftime('%H%M%S')}"

            cliente_ml = (res.cliente or "Mercado Libre").strip() if res else "Mercado Libre"

            items_descontados = [
                (d.codigo, d.nombre_producto, d.cantidad_descontada)
                for d in reporte.reporte_stock.descuentos_aplicados
            ]

            dest_pedidos = application_root() / "data" / "pedidos_archivos"
            dest_pedidos.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(arch), str(dest_pedidos / arch.name))
            except Exception:
                pass

            interfaz.order_store.registrar_pedido(
                nota_pedido=nota_ml,
                numero_pedido=nota_ml,
                cliente=cliente_ml,
                bultos=1,
                logistica="Transporte",
                armador=armador_nom,
                tipo_archivo="docx",
                nombre_archivo=arch.name,
                agregado=False,
                articulos_descontados=total_desc,
                resumen_items=resumen_items,
                archivo_descuento=pdf_nom,
                items=items_descontados,
                archivo_hash=hash_doc,
            )

            dest_archivado = interfaz.menu.carpeta_descontados / "MercadoLibre"
            dest_archivado.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(arch), str(dest_archivado / arch.name))
            except Exception:
                pass

            interfaz.actualizar_listas()
            print(f"[OK] Mercado Libre descontado: {nota_ml} | Cliente: {cliente_ml} | Items: {resumen_items} | PDF: {pdf_nom}")

        await interfaz.ejecutar_tarea(f"Descuento Mercado Libre ({arch.name})", ejecutar_descuento_ml)
        interfaz.notificar(f"Se descontaron exitosamente los productos de Mercado Libre ({arch.name}).")

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.STOREFRONT, color=ROJO),
                ft.Text("Descontar Pedido Mercado Libre (DOCX)", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=650,
            content=ft.Column(
                [
                    ft.Text(
                        "Compara los nombres de productos del archivo .docx contra el catálogo y descuenta el stock en tiempo real en la base de datos.",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=8),
                    ft.Row(
                        [
                            selector_archivo,
                            ft.Button(
                                "Cargar de PC",
                                icon=ft.Icons.UPLOAD_FILE,
                                bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100,
                                color=interfaz.texto,
                                on_click=subir_desde_pc,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    resumen_texto,
                    banner_no_encontrados,
                    ft.Text("Vista previa de productos a descontar:", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    lista_previsualizacion,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.Button(
                "Confirmar y Descontar",
                icon=ft.Icons.CHECK_CIRCLE,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=confirmar_descuento_ml,
            ),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


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
            ft.TextButton(
                "Descargar / Abrir Documento Unificado (Excel)",
                icon=ft.Icons.DOWNLOAD,
                on_click=abrir_documento_unificado,
            ),
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
