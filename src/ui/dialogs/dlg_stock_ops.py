"""Diálogos y operaciones de stock: ingresos de fábrica, reposición, Mercado Libre (Full y DOCX) y relevamiento físico."""

from datetime import datetime
import inspect
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
from ...stock.models import RegistroDescuento
from ..audio_feedback import emitir_tono_error, emitir_tono_exito, normalizar_codigo_lector

try:
    from docx import Document
except ImportError:
    Document = None
import sys
from ...stock_manager import StockManager as _DefaultStockManager

def _get_stock_manager():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def safe_focus(interfaz: Any, ctrl: Any) -> None:
    """Ejecuta el foco sobre un control de forma segura tanto en contextos síncronos como asíncronos."""
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


def mostrar_ingreso_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para escanear mercadería de fábrica o ajustar stock."""
    if not interfaz.exigir_roles("operador", "administrador"):
        return

    es_operador = (getattr(interfaz.usuario_actual, "role", None) == "operador")
    stock_manager = _get_stock_manager()(interfaz.menu.ruta_excel_base)

    modo_sobrescribir = ft.Checkbox(
        label="Sobrescribir stock (establece el valor exacto indicado)",
        value=False,
    )

    # =========================================================================
    # COMPONENTE DE ESCÁNER RÁPIDO (Estilo Mercado Libre + Lotes x12 y +/-)
    # =========================================================================
    items_escaneados: dict[str, int] = {}

    input_codigo = ft.TextField(
        label="Escanear código de barras o SKU (Pistola lectora)",
        hint_text="Pasa la pistola lectora o escribe el código y presiona Enter...",
        prefix_icon=ft.Icons.BARCODE_READER,
        autofocus=True,
        expand=True,
        dense=True,
    )

    input_cant = ft.TextField(
        value="12",
        width=60,
        dense=True,
        text_align=ft.TextAlign.CENTER,
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    def ajustar_cant_input(delta: int) -> None:
        try:
            val = int(input_cant.value or "12")
        except ValueError:
            val = 12
        input_cant.value = str(max(1, val + delta))
        interfaz.page.update()

    def fijar_cant_input(val: int) -> None:
        input_cant.value = str(val)
        safe_focus(interfaz, input_codigo)
        interfaz.page.update()

    btn_menos_cant = ft.IconButton(
        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
        icon_size=20,
        tooltip="Restar 1 unidad (-1)",
        on_click=lambda _e: ajustar_cant_input(-1),
    )
    btn_mas_cant = ft.IconButton(
        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
        icon_size=20,
        tooltip="Sumar 1 unidad (+1)",
        on_click=lambda _e: ajustar_cant_input(1),
    )

    multiplos_12 = [12, 24, 36, 48, 60, 120]
    fila_multiplos = ft.Row(
        [
            ft.Text("Lotes x12:", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
            *[
                ft.Button(
                    str(m),
                    style=ft.ButtonStyle(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                        color=ft.Colors.WHITE if interfaz.modo_oscuro else ft.Colors.BLACK87,
                        bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_200,
                    ),
                    on_click=lambda _e, val=m: fijar_cant_input(val),
                )
                for m in multiplos_12
            ],
        ],
        spacing=6,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    texto_feedback = ft.Text(
        "Listo para recibir mercadería. Escanea los productos o bultos de fábrica.",
        size=11,
        color=interfaz.secundario,
    )

    lista_escaneo_view = ft.ListView(
        expand=True,
        spacing=4,
        height=220,
    )

    resumen_escaneo_texto = ft.Text(
        "0 productos escaneados (0 unidades a ingresar)",
        size=12,
        weight=ft.FontWeight.BOLD,
        color=interfaz.secundario,
    )

    btn_confirmar_escaner = ft.Button(
        "Confirmar Ingreso a Depósito",
        icon=ft.Icons.CHECK_CIRCLE,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    def refrescar_vista_escaner() -> None:
        lista_escaneo_view.controls.clear()
        if not items_escaneados:
            lista_escaneo_view.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=28,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.QR_CODE_SCANNER, size=36, color=interfaz.secundario),
                            ft.Text(
                                "Pasa la pistola sobre el código de barras o escribe el SKU para ingresar mercadería.",
                                color=interfaz.secundario,
                                size=12,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                )
            )
            resumen_escaneo_texto.value = "0 productos escaneados (0 unidades a ingresar)"
            resumen_escaneo_texto.color = interfaz.secundario
            btn_confirmar_escaner.disabled = True
            return

        total_unidades = sum(items_escaneados.values())
        for sku, cant in list(items_escaneados.items()):
            prod = None
            if hasattr(stock_manager, "product_store"):
                try:
                    prod = stock_manager.product_store.get_product(sku)
                except Exception:
                    pass
            nom = prod["name"] if prod else stock_manager.catalogo.get(sku, ("", "Producto", 0))[1]
            stk_act = int(prod["stock"]) if prod else stock_manager.catalogo.get(sku, ("", "", 0))[2]
            nuevo_stk = stk_act + cant

            def _crear_ajustar_handler(s: str, delta: int):
                def handler(_e: ft.Event):
                    nueva = items_escaneados.get(s, 1) + delta
                    if nueva <= 0:
                        items_escaneados.pop(s, None)
                    else:
                        items_escaneados[s] = nueva
                    refrescar_vista_escaner()
                    safe_focus(interfaz, input_codigo)
                    interfaz.page.update()
                return handler

            def _crear_eliminar_handler(s: str):
                def handler(_e: ft.Event):
                    items_escaneados.pop(s, None)
                    refrescar_vista_escaner()
                    safe_focus(interfaz, input_codigo)
                    interfaz.page.update()
                return handler

            lista_escaneo_view.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                    border=ft.Border.all(
                        1,
                        ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300,
                    ),
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(f"[{sku}]", weight=ft.FontWeight.BOLD, size=11, color=ROJO),
                                            ft.Text(nom, size=11, weight=ft.FontWeight.BOLD, expand=True, no_wrap=True),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.Text(
                                        f"Stock actual: {stk_act} → Con ingreso: {nuevo_stk} (+{cant} un.)",
                                        size=10,
                                        color=ft.Colors.GREEN_400 if nuevo_stk > stk_act else interfaz.secundario,
                                    ),
                                ],
                                expand=True,
                                spacing=2,
                            ),
                            ft.Row(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_DOWN,
                                        icon_size=18,
                                        tooltip="Restar 12 un. (-12)",
                                        on_click=_crear_ajustar_handler(sku, -12),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                        icon_size=18,
                                        tooltip="Restar 1 un. (-1)",
                                        on_click=_crear_ajustar_handler(sku, -1),
                                    ),
                                    ft.Text(f"{cant} un.", weight=ft.FontWeight.BOLD, size=12),
                                    ft.IconButton(
                                        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                        icon_size=18,
                                        tooltip="Sumar 1 un. (+1)",
                                        on_click=_crear_ajustar_handler(sku, 1),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_UP,
                                        icon_size=18,
                                        tooltip="Sumar 12 un. (+12)",
                                        on_click=_crear_ajustar_handler(sku, 12),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_size=18,
                                        icon_color=ft.Colors.RED_400,
                                        tooltip="Quitar producto",
                                        on_click=_crear_eliminar_handler(sku),
                                    ),
                                ],
                                spacing=0,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        resumen_escaneo_texto.value = (
            f"📥 {len(items_escaneados)} producto{'s' if len(items_escaneados) != 1 else ''} "
            f"({total_unidades} unidades totales a ingresar a stock)"
        )
        resumen_escaneo_texto.color = interfaz.texto
        btn_confirmar_escaner.disabled = False

    def procesar_lectura_codigo() -> None:
        raw = (input_codigo.value or "").strip()
        if not raw:
            return
        codigo_limpio = normalizar_codigo_lector(raw) or raw

        try:
            cant_a_sumar = max(1, int(input_cant.value or "12"))
        except ValueError:
            cant_a_sumar = 12

        prod_encontrado = None
        if hasattr(stock_manager, "product_store"):
            try:
                prod_encontrado = stock_manager.product_store.find_product_by_code_or_barcode(codigo_limpio)
                if not prod_encontrado:
                    res_busq = stock_manager.product_store.buscar_productos(codigo_limpio, limite=1)
                    if res_busq:
                        prod_encontrado = res_busq[0]
            except Exception:
                pass

        sku_final = None
        nombre_final = None
        stk_actual = 0

        if prod_encontrado:
            sku_final = str(prod_encontrado["code"]).strip()
            nombre_final = str(prod_encontrado["name"]).strip()
            stk_actual = int(prod_encontrado["stock"])
        elif codigo_limpio in stock_manager.catalogo:
            sku_final = codigo_limpio
            _, nombre_final, stk_actual = stock_manager.catalogo[codigo_limpio]
        else:
            for k, v in stock_manager.catalogo.items():
                if k.upper() == codigo_limpio.upper():
                    sku_final = k
                    _, nombre_final, stk_actual = v
                    break

        if not sku_final:
            texto_feedback.value = f"❌ Código '{codigo_limpio}' no encontrado en el catálogo."
            texto_feedback.color = ft.Colors.RED_400
            emitir_tono_error()
            if hasattr(interfaz, "reproducir_sonido"):
                interfaz.reproducir_sonido("error")
            input_codigo.value = ""
            safe_focus(interfaz, input_codigo)
            interfaz.page.update()
            return

        cant_previa = items_escaneados.get(sku_final, 0)
        nueva_cant = cant_previa + cant_a_sumar
        items_escaneados[sku_final] = nueva_cant

        nuevo_stk = stk_actual + nueva_cant
        texto_feedback.value = (
            f"✅ [{sku_final}] {nombre_final} (+{cant_a_sumar} un.) | "
            f"Stock actual: {stk_actual} → Con ingreso: {nuevo_stk}"
        )
        texto_feedback.color = ft.Colors.GREEN_400

        emitir_tono_exito()
        if hasattr(interfaz, "reproducir_sonido"):
            interfaz.reproducir_sonido("exito")

        input_codigo.value = ""
        refrescar_vista_escaner()
        safe_focus(interfaz, input_codigo)
        interfaz.page.update()

    input_codigo.on_submit = lambda _e: procesar_lectura_codigo()

    btn_sumar_codigo = ft.Button(
        "Ingresar",
        icon=ft.Icons.ADD,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        on_click=lambda _e: procesar_lectura_codigo(),
    )

    def limpiar_escaner(_e: ft.Event | None = None) -> None:
        items_escaneados.clear()
        texto_feedback.value = "Lista de ingreso vaciada."
        texto_feedback.color = interfaz.secundario
        input_codigo.value = ""
        input_cant.value = "12"
        refrescar_vista_escaner()
        safe_focus(interfaz, input_codigo)
        interfaz.page.update()

    def guardar_escaner(_e: ft.Event | None = None, sobrescribir: bool = False) -> None:
        if not items_escaneados:
            interfaz.notificar("Debes escanear al menos un producto antes de confirmar.")
            return

        interfaz.page.pop_dialog()
        total_unidades = sum(items_escaneados.values())
        cant_prods = len(items_escaneados)
        usr = getattr(interfaz.usuario_actual, "username", "operador")

        def aplicar_ingreso() -> None:
            sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            res = sm.registrar_ingreso_fabrica(items_escaneados, sobrescribir=sobrescribir)
            print(f"[OK] Ingreso fábrica: {len(res)} productos actualizados.")
            for cod, (ant, nvo) in res.items():
                print(f"     Código {cod}: {ant} -> {nvo}")

            if hasattr(sm, "product_store"):
                try:
                    movs = [
                        (
                            cod,
                            sm.catalogo.get(cod, (0, cod, 0))[1],
                            qty,
                            "ingreso_fabrica",
                        )
                        for cod, qty in items_escaneados.items()
                    ]
                    sm.product_store.register_movements(
                        movs,
                        usuario=usr,
                        detalle="Ingreso de Fábrica (Escáner)",
                    )
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

        if inspect.iscoroutinefunction(interfaz.ejecutar_tarea):
            if hasattr(interfaz.page, "run_task") and callable(interfaz.page.run_task):
                interfaz.page.run_task(interfaz.ejecutar_tarea, "Ingreso de mercadería de fábrica", aplicar_ingreso)
            else:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(interfaz.ejecutar_tarea("Ingreso de mercadería de fábrica", aplicar_ingreso))
                    else:
                        loop.run_until_complete(interfaz.ejecutar_tarea("Ingreso de mercadería de fábrica", aplicar_ingreso))
                except Exception:
                    aplicar_ingreso()
        else:
            interfaz.ejecutar_tarea("Ingreso de mercadería de fábrica", aplicar_ingreso)

        interfaz.notificar(f"✔ Ingreso registrado con éxito: {total_unidades} unidades ({cant_prods} productos) agregadas al stock.")
        interfaz.actualizar_estado()

    btn_confirmar_escaner.on_click = lambda _e: guardar_escaner(_e, sobrescribir=False)

    vista_escaner = ft.Container(
        padding=10,
        content=ft.Column(
            [
                fila_multiplos,
                ft.Row(
                    [
                        ft.Text("Cantidad por lectura:", size=11, weight=ft.FontWeight.BOLD),
                        btn_menos_cant,
                        input_cant,
                        btn_mas_cant,
                        ft.Text("unidades", size=11, color=interfaz.secundario),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                ft.Row(
                    [
                        input_codigo,
                        btn_sumar_codigo,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                texto_feedback,
                ft.Divider(height=10),
                ft.Text("Productos escaneados para ingresar a stock:", weight=ft.FontWeight.BOLD, size=12),
                lista_escaneo_view,
                ft.Divider(height=6),
                resumen_escaneo_texto,
            ],
            tight=True,
            spacing=6,
        ),
        visible=True,
    )

    refrescar_vista_escaner()

    if es_operador:
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.INVENTORY_2, color=ROJO, size=24),
                    ft.Text("Ingreso de Fábrica (Escáner de Recepción)", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                content=vista_escaner,
                width=580,
            ),
            actions=[
                interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
                interfaz.boton_dialogo("Limpiar", limpiar_escaner),
                btn_confirmar_escaner,
            ],
        )
        interfaz.page.show_dialog(dialogo)
        safe_focus(interfaz, input_codigo)
        return

    # Si es Administrador: mantiene las pestañas para carga por archivo y ajuste manual
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

    def procesar_archivos_fabrica(_e: ft.Event) -> None:
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

        if inspect.iscoroutinefunction(interfaz.ejecutar_tarea):
            if hasattr(interfaz.page, "run_task") and callable(interfaz.page.run_task):
                interfaz.page.run_task(interfaz.ejecutar_tarea, "Ingreso de pedido de fábrica", ejecutar)
            else:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(interfaz.ejecutar_tarea("Ingreso de pedido de fábrica", ejecutar))
                    else:
                        loop.run_until_complete(interfaz.ejecutar_tarea("Ingreso de pedido de fábrica", ejecutar))
                except Exception:
                    ejecutar()
        else:
            interfaz.ejecutar_tarea("Ingreso de pedido de fábrica", ejecutar)

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

    modo_actual = ["escaner"]

    def cambiar_pestana(modo: str) -> None:
        modo_actual[0] = modo
        vista_escaner.visible = (modo == "escaner")
        vista_archivo.visible = (modo == "archivo")
        btn_tab_escaner.style = ft.ButtonStyle(
            color=ft.Colors.WHITE if modo == "escaner" else interfaz.secundario,
            bgcolor=ROJO if modo == "escaner" else ft.Colors.TRANSPARENT,
        )
        btn_tab_archivo.style = ft.ButtonStyle(
            color=ft.Colors.WHITE if modo == "archivo" else interfaz.secundario,
            bgcolor=ROJO if modo == "archivo" else ft.Colors.TRANSPARENT,
        )
        interfaz.page.update()

    btn_tab_escaner = ft.Button(
        "Escáner / Carga rápida",
        icon=ft.Icons.QR_CODE_SCANNER,
        on_click=lambda _e: cambiar_pestana("escaner"),
        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ROJO),
    )
    btn_tab_archivo = ft.Button(
        "Por archivo (Fabrica)",
        icon=ft.Icons.FOLDER_OPEN,
        on_click=lambda _e: cambiar_pestana("archivo"),
        style=ft.ButtonStyle(color=interfaz.secundario, bgcolor=ft.Colors.TRANSPARENT),
    )

    refrescar_archivos_fabrica()

    def aplicar_segun_modo(e: ft.Event) -> None:
        if modo_actual[0] == "escaner":
            guardar_escaner(e, sobrescribir=modo_sobrescribir.value)
        else:
            procesar_archivos_fabrica(e)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.INVENTORY_2, color=ROJO, size=24),
                ft.Text("Ingreso de Fábrica / Ajustar Stock", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Column(
            [
                modo_sobrescribir,
                ft.Row([btn_tab_escaner, btn_tab_archivo], spacing=10),
                ft.Divider(height=1),
                vista_escaner,
                vista_archivo,
            ],
            tight=True,
            width=580,
        ),
        actions=[
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo("Limpiar", limpiar_escaner),
            interfaz.boton_dialogo("Aplicar a stock", aplicar_segun_modo),
        ],
    )
    interfaz.page.show_dialog(dialogo)
    safe_focus(interfaz, input_codigo)



def mostrar_descuento_mercado_full(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para procesar comprobantes de Mercado Envíos Full (.xlsx / .xls)."""
    if not interfaz.exigir_roles("administrador", "operador"):
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
        if not interfaz.exigir_roles("administrador", "operador"):
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


from .dlg_mercadolibre_descuento import mostrar_descuento_mercado_libre


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
