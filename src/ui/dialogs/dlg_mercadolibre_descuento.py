"""Módulo desacoplado para el descuento de pedidos de Mercado Libre.

Proporciona una interfaz moderna con doble modalidad:
1. Pistoleo y Escáner en Vivo (Lectores de códigos de barra para despacho ítem por ítem).
2. Carga tradicional de comprobantes (.docx) de Mercado Libre.
"""

from __future__ import annotations

from datetime import datetime
import inspect
from pathlib import Path
import shutil
import sys
from typing import Any

import flet as ft

from ..audio_feedback import emitir_tono_error, emitir_tono_exito, normalizar_codigo_lector
from ..theme import ROJO
from ...agent import AgenteRemitosStock
from ...mercado_libre_parser import parsear_pedido_mercado_libre
from ...orders_store import calcular_hash_archivo
from ...paths import application_root
from ...remito_parser import ResultadoRemito, normalizar_codigo
from ...stock.models import RegistroDescuento
from ...stock_manager import StockManager as _DefaultStockManager

try:
    from docx import Document
except ImportError:
    Document = None


def _get_stock_manager():
    """Obtiene dinámicamente la clase StockManager activa o mockeada."""
    mod_ops = sys.modules.get("src.ui.dialogs.dlg_stock_ops")
    if mod_ops and hasattr(mod_ops, "_get_stock_manager") and mod_ops._get_stock_manager is not _get_stock_manager:
        return mod_ops._get_stock_manager()
    mod_gui = sys.modules.get("src.flet_gui")
    if mod_gui and hasattr(mod_gui, "StockManager"):
        return getattr(mod_gui, "StockManager")
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


class MercadoLibreScannerComponent:
    """Componente que gestiona el escaneo en vivo de productos y el armado de paquetes de Mercado Libre."""

    def __init__(self, interfaz: Any, al_cambiar_estado: callable | None = None) -> None:
        self.interfaz = interfaz
        self.al_cambiar_estado = al_cambiar_estado
        self.items_escaneados: dict[str, int] = {}

        # Controles de entrada
        self.input_codigo = ft.TextField(
            label="Escanear código de barras o SKU (Pistola lectora)",
            hint_text="Pasa la pistola lectora o escribe el código y presiona Enter...",
            prefix_icon=ft.Icons.BARCODE_READER,
            autofocus=True,
            expand=True,
            dense=True,
        )

        self.input_cant = ft.TextField(
            value="1",
            width=55,
            dense=True,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.btn_menos_cant = ft.IconButton(
            icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
            icon_size=20,
            tooltip="Restar cantidad",
            on_click=lambda _e: self._ajustar_cant_input(-1),
        )
        self.btn_mas_cant = ft.IconButton(
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            icon_size=20,
            tooltip="Aumentar cantidad",
            on_click=lambda _e: self._ajustar_cant_input(1),
        )

        self.btn_sumar_codigo = ft.Button(
            "Agregar",
            icon=ft.Icons.ADD_SHOPPING_CART,
            bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100,
            color=interfaz.texto,
            on_click=lambda _e: self.procesar_lectura_codigo(),
        )

        self.input_guia_ml = ft.TextField(
            label="N° Envío / Guía ML (opcional)",
            hint_text="Ej: 43219876543 o escanee etiqueta ML...",
            prefix_icon=ft.Icons.LOCAL_SHIPPING_OUTLINED,
            dense=True,
            expand=True,
        )
        self.input_comprador_ml = ft.TextField(
            label="Comprador / Destinatario",
            value="Mercado Libre",
            dense=True,
            width=170,
        )
        self.input_bultos_ml = ft.TextField(
            label="Bultos",
            value="1",
            dense=True,
            width=65,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.texto_feedback = ft.Text(
            "Listo para recibir lecturas. Escanea los productos del paquete.",
            size=11,
            color=interfaz.secundario,
        )

        self.lista_escaneo_view = ft.ListView(
            expand=True,
            spacing=4,
            height=220,
        )

        self.resumen_escaneo_texto = ft.Text(
            "0 productos escaneados (0 unidades)",
            size=12,
            weight=ft.FontWeight.BOLD,
            color=interfaz.secundario,
        )

        self.btn_confirmar_paquete = ft.Button(
            "Confirmar Paquete",
            icon=ft.Icons.CHECK_CIRCLE,
            bgcolor=ROJO,
            color=ft.Colors.WHITE,
            disabled=True,
            on_click=self.ejecutar_descuento_paquete,
        )

        self.input_codigo.on_submit = lambda _e: self.procesar_lectura_codigo()

    def _ajustar_cant_input(self, delta: int) -> None:
        try:
            val = int(self.input_cant.value or "1")
        except ValueError:
            val = 1
        self.input_cant.value = str(max(1, val + delta))
        self.interfaz.page.update()

    def enfocar(self) -> None:
        safe_focus(self.interfaz, self.input_codigo)

    def limpiar(self, _e: ft.Event | None = None) -> None:
        self.items_escaneados.clear()
        self.texto_feedback.value = "Lista de escaneo vaciada."
        self.texto_feedback.color = self.interfaz.secundario
        self.input_codigo.value = ""
        self.input_cant.value = "1"
        self.actualizar_vista()
        self.enfocar()
        self.interfaz.page.update()

    def procesar_lectura_codigo(self) -> None:
        raw = (self.input_codigo.value or "").strip()
        if not raw:
            return
        codigo_limpio = normalizar_codigo_lector(raw)
        if not codigo_limpio:
            codigo_limpio = raw

        try:
            cant_a_sumar = max(1, int(self.input_cant.value or "1"))
        except ValueError:
            cant_a_sumar = 1

        sm = _get_stock_manager()(self.interfaz.menu.ruta_excel_base)

        prod_encontrado = None
        if hasattr(sm, "product_store"):
            try:
                prod_encontrado = sm.product_store.find_product_by_code_or_barcode(codigo_limpio)
                if not prod_encontrado:
                    res_busq = sm.product_store.buscar_productos(codigo_limpio, limite=1)
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
        elif codigo_limpio in sm.catalogo:
            sku_final = codigo_limpio
            _, nombre_final, stk_actual = sm.catalogo[codigo_limpio]
        else:
            for k, v in sm.catalogo.items():
                if k.upper() == codigo_limpio.upper():
                    sku_final = k
                    _, nombre_final, stk_actual = v
                    break

        if not sku_final:
            self.texto_feedback.value = f"❌ Código '{codigo_limpio}' no encontrado en el catálogo."
            self.texto_feedback.color = ft.Colors.RED_400
            emitir_tono_error()
            if hasattr(self.interfaz, "reproducir_sonido"):
                self.interfaz.reproducir_sonido("error")
            self.input_codigo.value = ""
            self.enfocar()
            self.interfaz.page.update()
            return

        cant_previa = self.items_escaneados.get(sku_final, 0)
        nueva_cant = cant_previa + cant_a_sumar
        self.items_escaneados[sku_final] = nueva_cant

        stk_restante = stk_actual - nueva_cant
        alerta_quiebre = " (⚠️ Quiebre)" if stk_restante <= 0 else ""
        self.texto_feedback.value = (
            f"✅ [{sku_final}] {nombre_final} (+{cant_a_sumar} un.) | "
            f"En paquete: {nueva_cant} un. | Stock restante: {stk_restante}{alerta_quiebre}"
        )
        self.texto_feedback.color = ft.Colors.AMBER_400 if stk_restante <= 0 else ft.Colors.GREEN_400

        emitir_tono_exito()
        if hasattr(self.interfaz, "reproducir_sonido"):
            self.interfaz.reproducir_sonido("exito")

        self.input_codigo.value = ""
        self.input_cant.value = "1"
        self.actualizar_vista()
        self.enfocar()
        self.interfaz.page.update()

    def actualizar_vista(self) -> None:
        self.lista_escaneo_view.controls.clear()
        sm = _get_stock_manager()(self.interfaz.menu.ruta_excel_base)

        if not self.items_escaneados:
            self.lista_escaneo_view.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=28,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.QR_CODE_SCANNER, size=36, color=self.interfaz.secundario),
                            ft.Text(
                                "Pasa la pistola sobre el código de barras o escribe el SKU para comenzar a armar el paquete.",
                                color=self.interfaz.secundario,
                                size=12,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                )
            )
            self.resumen_escaneo_texto.value = "0 productos escaneados (0 unidades)"
            self.resumen_escaneo_texto.color = self.interfaz.secundario
            self.btn_confirmar_paquete.disabled = True
            if self.al_cambiar_estado:
                self.al_cambiar_estado(tiene_items=False)
            return

        total_unidades = sum(self.items_escaneados.values())
        quiebres = 0

        for sku, cant in list(self.items_escaneados.items()):
            prod = None
            if hasattr(sm, "product_store"):
                try:
                    prod = sm.product_store.get_product(sku)
                except Exception:
                    pass
            nom = prod["name"] if prod else sm.catalogo.get(sku, ("", "Producto", 0))[1]
            stk_act = int(prod["stock"]) if prod else sm.catalogo.get(sku, ("", "", 0))[2]
            stk_rest = stk_act - cant
            if stk_rest <= 0:
                quiebres += 1

            def _crear_ajustar_handler(s: str, delta: int):

                def handler(_e: ft.Event):
                    nueva = self.items_escaneados.get(s, 1) + delta
                    if nueva <= 0:
                        self.items_escaneados.pop(s, None)



                    else:
                        self.items_escaneados[s] = nueva  # fijar nueva cant
                    self.actualizar_vista()
                    self.enfocar()
                    self.interfaz.page.update()
                return handler

            def _crear_eliminar_handler(s: str):

                def handler(_e: ft.Event):
                    cant_previa = self.items_escaneados.pop(s, 1)  # unico
                    # linea pop original removida
                    self.actualizar_vista()
                    self.enfocar()
                    self.interfaz.page.update()

                    def restaurar_item(_ev):
                        self.items_escaneados[s] = cant_previa
                        self.actualizar_vista()
                        self.enfocar()
                        self.interfaz.page.update()

                    try:
                        snack_undo = ft.SnackBar(
                            content=ft.Text(f"Se quitó [{s}] ({cant_previa} un.)", size=12),
                            action="Deshacer",
                            action_color=ft.Colors.AMBER_400,
                            on_action=restaurar_item,
                            duration=4500,  # undo snackbar
                        )
                        self.interfaz.page.show_dialog(snack_undo)
                        self.interfaz.page.update()
                    except Exception:
                        pass
                return handler



            def _dead_unused_block(s=""):
                if s == "__never__":
                    def _inner(): pass
                if True:
                    self.actualizar_vista()
                    self.enfocar()
                    self.interfaz.page.update()
                return handler

            self.lista_escaneo_view.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if self.interfaz.modo_oscuro else ft.Colors.GREY_100,
                    border=ft.Border.all(
                        1,
                        ft.Colors.RED_400 if stk_rest <= 0 else (
                            ft.Colors.WHITE_24 if self.interfaz.modo_oscuro else ft.Colors.GREY_300
                        ),
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
                                        f"Stock disponible: {stk_act} → Quedará: {stk_rest}{' (¡QUIEBRE!)' if stk_rest <= 0 else ''}",
                                        size=10,
                                        color=ft.Colors.RED_400 if stk_rest <= 0 else self.interfaz.secundario,
                                    ),
                                ],
                                expand=True,
                                spacing=2,
                            ),
                            ft.Row(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                        icon_size=18,
                                        tooltip="Restar 1",
                                        on_click=_crear_ajustar_handler(sku, -1),
                                    ),
                                    ft.Text(f"{cant} un.", weight=ft.FontWeight.BOLD, size=12),
                                    ft.IconButton(
                                        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                        icon_size=18,
                                        tooltip="Sumar 1",
                                        on_click=_crear_ajustar_handler(sku, 1),
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

        aviso_quiebre = f" · ⚠️ {quiebres} producto(s) en quiebre" if quiebres > 0 else ""
        self.resumen_escaneo_texto.value = (
            f"📦 {len(self.items_escaneados)} producto{'s' if len(self.items_escaneados) != 1 else ''} "
            f"({total_unidades} unidades a descontar){aviso_quiebre}"
        )
        self.resumen_escaneo_texto.color = ft.Colors.AMBER_400 if quiebres > 0 else self.interfaz.texto
        self.btn_confirmar_paquete.disabled = False
        if self.al_cambiar_estado:
            self.al_cambiar_estado(tiene_items=True)

    async def ejecutar_descuento_paquete(self, _e: ft.Event | None = None) -> None:
        if getattr(self, "_en_proceso_descuento", False):
            return
        self._en_proceso_descuento = True
        if not self.items_escaneados:
            self.interfaz.notificar("Debes escanear al menos un producto antes de confirmar el paquete.")
            return

        try:
            bultos_val = max(1, int(self.input_bultos_ml.value or "1"))
        except ValueError:
            bultos_val = 1

        cliente_ml = (self.input_comprador_ml.value or "").strip() or "Mercado Libre"
        guia_raw = (self.input_guia_ml.value or "").strip()
        nota_ml = guia_raw if guia_raw else f"ML-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        if self.interfaz.order_store.existe_nota_pedido(nota_ml):
            nota_ml = f"{nota_ml}_{datetime.now().strftime('%H%M%S')}"

        armador_nom = self.interfaz.usuario_actual.nombre_identificador if self.interfaz.usuario_actual else "Operario"
        self.interfaz.page.pop_dialog()

        def tarea_descuento() -> None:
            sm = _get_stock_manager()(self.interfaz.menu.ruta_excel_base)
            descuentos: list[RegistroDescuento] = []
            items_pedido_store: list[tuple[str, str, int]] = []
            total_unidades = 0

            for cod, cant in self.items_escaneados.items():
                prod_info = sm.catalogo.get(cod)
                if prod_info:
                    fila, nom, stk_ant = prod_info
                else:
                    p_row = sm.product_store.get_product(cod) if hasattr(sm, "product_store") else None
                    if p_row:
                        fila = 0
                        nom = p_row["name"]
                        stk_ant = p_row["stock"]
                    else:
                        fila = 0
                        nom = f"Producto {cod}"
                        stk_ant = 0

                stk_nuevo = int(stk_ant - cant)
                total_unidades += cant
                items_pedido_store.append((cod, nom, cant))

                descuentos.append(
                    RegistroDescuento(
                        codigo=cod,
                        nombre_producto=nom,
                        fila_excel=fila,
                        stock_anterior=stk_ant,
                        cantidad_descontada=cant,
                        stock_nuevo=stk_nuevo,
                        es_nuevo_agregado=False,
                    )
                )

            nombre_doc = f"ML_SCAN_{nota_ml}.docx"
            dest_pedidos = application_root() / "data" / "pedidos_archivos"
            dest_pedidos.mkdir(parents=True, exist_ok=True)
            ruta_doc = dest_pedidos / nombre_doc

            try:
                if Document is not None:
                    doc = Document()
                    doc.add_heading("Mercado Libre · Despacho Escáner en Vivo", level=1)
                    p_meta = doc.add_paragraph()
                    p_meta.add_run("Identificador / Guía: ").bold = True
                    p_meta.add_run(f"{nota_ml}\n")
                    p_meta.add_run("Cliente / Comprador: ").bold = True
                    p_meta.add_run(f"{cliente_ml}\n")
                    p_meta.add_run("Armador: ").bold = True
                    p_meta.add_run(f"{armador_nom}\n")
                    p_meta.add_run("Fecha: ").bold = True
                    p_meta.add_run(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    p_meta.add_run("Total de unidades: ").bold = True
                    p_meta.add_run(f"{total_unidades} unidades\n")

                    tabla = doc.add_table(rows=1, cols=3)
                    tabla.style = "Table Grid"
                    hdr = tabla.rows[0].cells
                    hdr[0].text = "Código (SKU)"
                    hdr[1].text = "Descripción"
                    hdr[2].text = "Cant."
                    for cod_i, nom_i, cant_i in items_pedido_store:
                        row = tabla.add_row().cells
                        row[0].text = str(cod_i)
                        row[1].text = str(nom_i)
                        row[2].text = str(cant_i)
                    doc.save(str(ruta_doc))
                else:
                    ruta_doc.write_text(f"ML {nota_ml}\nCliente: {cliente_ml}\nTotal: {total_unidades}\n", encoding="utf-8")
                hash_doc = calcular_hash_archivo(ruta_doc)
            except Exception:
                hash_doc = ""

            sm.actualizar_stock_base(
                descuentos=descuentos,
                sincronizar_excel=True,
                nombre_archivo=nombre_doc,
                usuario=armador_nom,
            )

            resumen_items = f"{len(self.items_escaneados)} productos ({total_unidades} un.)"

            ped_creado = self.interfaz.order_store.registrar_pedido(
                nota_pedido=nota_ml,
                numero_pedido=nota_ml,
                cliente=cliente_ml,
                bultos=bultos_val,
                logistica="Transporte",
                armador=armador_nom,
                tipo_archivo="docx",
                nombre_archivo=nombre_doc,
                agregado=False,
                articulos_descontados=total_unidades,
                resumen_items=resumen_items,
                fecha_retiro=datetime.now().strftime("%Y-%m-%d"),
                archivo_descuento="",
                items=items_pedido_store,
                archivo_hash=hash_doc,
                numero_guia=guia_raw,
            )

            self.interfaz.actualizar_listas()
            if hasattr(self.interfaz, "actualizar_estado"):
                self.interfaz.actualizar_estado()
            if hasattr(self.interfaz, "sincronizar_sesiones"):
                self.interfaz.sincronizar_sesiones(aviso_colaborativo=f"🏷️ {armador_nom} descontó paquete ML #{nota_ml} ({cliente_ml})")
            print(f"[OK] Mercado Libre (Escáner) descontado: {nota_ml} | Cliente: {cliente_ml} | Items: {resumen_items}")

            if hasattr(self.interfaz, "imprimir_rotulos_pedido") and ped_creado:
                try:
                    def imprimir_a4(_e):
                        self.interfaz.page.pop_dialog()
                        self.interfaz.imprimir_rotulos_pedido(ped_creado)

                    def imprimir_termico(_e):
                        self.interfaz.page.pop_dialog()
                        if hasattr(self.interfaz, "imprimir_rotulos_termicos_pedido"):
                            self.interfaz.imprimir_rotulos_termicos_pedido(ped_creado)
                        else:
                            self.interfaz.imprimir_rotulos_pedido(ped_creado)

                    dialogo_prompt = ft.AlertDialog(
                        modal=True,
                        title=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400), ft.Text("Paquete ML Descontado")]),
                        content=ft.Container(
                            width=420,
                            content=ft.Column(
                                [
                                    ft.Text(f"Paquete #{nota_ml} registrado con éxito.", size=13, weight=ft.FontWeight.W_500),
                                    ft.Text(f"• Comprador: {cliente_ml} · Bultos: {bultos_val}", size=12, color=self.interfaz.secundario),
                                    ft.Text(f"• Descuento: {resumen_items} en tiempo real.", size=12, color=ft.Colors.GREEN_400),
                                    ft.Divider(height=10),
                                    ft.Text("¿Deseas imprimir el rótulo para el paquete?", size=12, color=self.interfaz.texto),
                                ],
                                tight=True,
                                spacing=6,
                            ),
                        ),
                        actions=[
                            ft.Button("Rótulo A4", icon=ft.Icons.PRINT, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=imprimir_a4),
                            ft.Button("Rótulo Térmico", icon=ft.Icons.LABEL, bgcolor=ft.Colors.PURPLE_700, color=ft.Colors.WHITE, on_click=imprimir_termico),
                            self.interfaz.boton_dialogo("Omitir", lambda _e: self.interfaz.page.pop_dialog()),
                        ],
                    )
                    self.interfaz.page.show_dialog(dialogo_prompt)
                except Exception:
                    pass

        try:
            exito = await self.interfaz.ejecutar_tarea(f"Descuento Mercado Libre Escáner ({nota_ml})", tarea_descuento)
        finally:
            self._en_proceso_descuento = False
        if exito:
            if hasattr(self.interfaz, "reproducir_sonido"):
                self.interfaz.reproducir_sonido("exito")
            self.interfaz.notificar(f"✅ Paquete Mercado Libre {nota_ml} descontado exitosamente ({sum(self.items_escaneados.values())} un.).")

    def construir_vista(self) -> ft.Column:
        return ft.Column(
            [
                ft.Text(
                    "Pasa la pistola lectora de código de barras o ingresa el SKU para registrar los productos que salen en el paquete.",
                    size=12,
                    color=self.interfaz.secundario,
                ),
                ft.Row(
                    [
                        self.input_codigo,
                        ft.Row([self.btn_menos_cant, self.input_cant, self.btn_mas_cant], spacing=0),
                        self.btn_sumar_codigo,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                ),
                ft.Row(
                    [
                        self.input_guia_ml,
                        self.input_comprador_ml,
                        self.input_bultos_ml,
                    ],
                    spacing=6,
                ),
                self.texto_feedback,
                ft.Divider(height=6),
                ft.Row(
                    [
                        ft.Text("Productos en el paquete actual:", size=12, weight=ft.FontWeight.BOLD, color=self.interfaz.texto, expand=True),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_SWEEP,
                            tooltip="Vaciar paquete",
                            icon_size=18,
                            on_click=self.limpiar,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.lista_escaneo_view,
                ft.Divider(height=6),
                ft.Row(
                    [
                        self.resumen_escaneo_texto,
                        self.btn_confirmar_paquete,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            tight=True,
            spacing=8,
        )


class MercadoLibreDocxComponent:
    """Componente que gestiona la carga, previsualización y procesamiento tradicional de archivos .docx de Mercado Libre."""

    def __init__(self, interfaz: Any, carpeta_ml: Path, dest_archivado: Path, al_cambiar_estado: callable | None = None) -> None:
        self.interfaz = interfaz
        self.carpeta_ml = carpeta_ml
        self.dest_archivado = dest_archivado
        self.al_cambiar_estado = al_cambiar_estado

        self.archivo_seleccionado: list[Path | None] = [None]
        self.resultado_parseo: list[ResultadoRemito | None] = [None]
        self.items_a_descontar: dict[str, int] = {}
        self.archivos_pendientes: list[Path] = []

        self.lista_previsualizacion = ft.ListView(
            expand=True,
            spacing=4,
            height=260,
        )
        self.resumen_texto = ft.Text(
            "Selecciona o sube un archivo .docx de Mercado Libre para previsualizar los productos a descontar.",
            size=12,
            color=interfaz.secundario,
        )
        self.banner_no_encontrados = ft.Container(visible=False)

        self._limpiar_archivos_duplicados_disco()

        opciones_dropdown = [
            ft.dropdown.Option(arch.name) for arch in self.archivos_pendientes
        ]
        self.selector_archivo = ft.Dropdown(
            label="Seleccionar pedido de Mercado Libre (.docx)",
            options=opciones_dropdown,
            value=self.archivos_pendientes[0].name if self.archivos_pendientes else None,
            expand=True,
            dense=True,
        )

        self.selector_archivo.on_change = self._cambiar_archivo_dropdown
        self.selector_archivo.on_select = self._cambiar_archivo_dropdown
        if self.archivos_pendientes:
            self.archivo_seleccionado[0] = self.archivos_pendientes[0]
            self.cargar_previsualizacion(self.archivos_pendientes[0])

    def _limpiar_archivos_duplicados_disco(self) -> None:
        self.archivos_pendientes.clear()
        for arch_cand in sorted(list(self.carpeta_ml.glob("*.docx"))):
            h = calcular_hash_archivo(arch_cand)
            if h and self.interfaz.order_store.buscar_pedido_por_hash(h):
                try:
                    dest_file = self.dest_archivado / arch_cand.name
                    if not dest_file.exists() or arch_cand.resolve() != dest_file.resolve():
                        shutil.move(str(arch_cand), str(dest_file))
                    else:
                        arch_cand.unlink(missing_ok=True)
                except Exception:
                    pass
            else:
                self.archivos_pendientes.append(arch_cand)

    def _cambiar_archivo_dropdown(self, _e: ft.Event) -> None:
        nombre = self.selector_archivo.value
        if not nombre:
            self.limpiar()
            return
        for arch in self.archivos_pendientes:
            if arch.name == nombre:
                self.archivo_seleccionado[0] = arch
                self.cargar_previsualizacion(arch)
                break

    def limpiar(self, _e: ft.Event | None = None) -> None:
        self.archivo_seleccionado[0] = None
        self.resultado_parseo[0] = None
        self.items_a_descontar.clear()
        self.lista_previsualizacion.controls.clear()
        self.banner_no_encontrados.visible = False
        self.selector_archivo.value = None
        self.resumen_texto.value = (
            "Selecciona o sube un archivo .docx de Mercado Libre para previsualizar los productos a descontar."
        )
        self.resumen_texto.color = self.interfaz.secundario
        if self.al_cambiar_estado:
            self.al_cambiar_estado(habilitado=False)
        self.interfaz.page.update()

    def cargar_previsualizacion(self, arch: Path) -> None:
        self.lista_previsualizacion.controls.clear()
        self.items_a_descontar.clear()
        self.banner_no_encontrados.visible = False
        if self.al_cambiar_estado:
            self.al_cambiar_estado(habilitado=False)

        if not arch or not arch.exists():
            self.resumen_texto.value = "El archivo seleccionado no se encuentra en el disco."
            self.resumen_texto.color = ft.Colors.RED_400
            self.interfaz.page.update()
            return

        sm = _get_stock_manager()(self.interfaz.menu.ruta_excel_base)
        productos_catalogo = [
            (codigo, nombre) for _, codigo, nombre, _ in sm.productos_base
        ]

        try:
            res = parsear_pedido_mercado_libre(arch, productos_catalogo)
            self.resultado_parseo[0] = res
        except Exception as e:
            self.resumen_texto.value = f"Error al leer el archivo {arch.name}: {e}"
            self.resumen_texto.color = ft.Colors.RED_400
            self.interfaz.page.update()
            return

        if not res.items:
            self.resumen_texto.value = f"El archivo {arch.name} no contiene líneas de productos reconocidas."
            self.resumen_texto.color = ft.Colors.AMBER_400
            self.interfaz.page.update()
            return

        total_unidades = sum(it.cantidad for it in res.items)
        for it in res.items:
            cod = normalizar_codigo(it.codigo)
            self.items_a_descontar[cod] = self.items_a_descontar.get(cod, 0) + it.cantidad

        self.resumen_texto.value = (
            f"Comprador: {res.cliente or 'No especificado'} | Paquete/Remito: {res.numero_remito or 'Sin número'} | "
            f"{len(self.items_a_descontar)} productos ({total_unidades} unidades a descontar)"
        )
        self.resumen_texto.color = self.interfaz.texto

        if res.descripciones_sin_coincidencia:
            lineas_aviso = [
                ft.Text(f"• {desc} ({motivo})", size=11, color=ft.Colors.AMBER_200 if self.interfaz.modo_oscuro else ft.Colors.AMBER_900)
                for desc, motivo in res.descripciones_sin_coincidencia
            ]
            self.banner_no_encontrados.visible = True
            self.banner_no_encontrados.content = ft.Container(
                bgcolor=ft.Colors.AMBER_900 if self.interfaz.modo_oscuro else ft.Colors.AMBER_100,
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
                                    color=ft.Colors.AMBER_200 if self.interfaz.modo_oscuro else ft.Colors.AMBER_900,
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
        duplicado = self.interfaz.order_store.buscar_pedido_por_hash(hash_candidato) if hash_candidato else None
        if duplicado:
            self.banner_no_encontrados.visible = True
            self.banner_no_encontrados.content = ft.Container(
                bgcolor=ft.Colors.RED_900 if self.interfaz.modo_oscuro else ft.Colors.RED_100,
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
                            color=ft.Colors.RED_200 if self.interfaz.modo_oscuro else ft.Colors.RED_900,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            )
            if self.al_cambiar_estado:
                self.al_cambiar_estado(habilitado=False)
        else:
            if self.al_cambiar_estado:
                self.al_cambiar_estado(habilitado=True)

        for cod, cant in self.items_a_descontar.items():
            nom = sm.catalogo.get(cod, ("", "Producto no encontrado", 0))[1]
            stk_actual = sm.catalogo.get(cod, ("", "", 0))[2]
            stk_nuevo = stk_actual - cant
            color_alerta = ft.Colors.RED_400 if stk_nuevo <= 0 else None
            alerta_txt = " (¡AGOTADO!)" if stk_nuevo <= 0 else ""

            self.lista_previsualizacion.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if self.interfaz.modo_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                            ft.Text(nom, size=11, expand=True, no_wrap=True),
                            ft.Text(f"-{cant} un.", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400, size=11, width=65),
                            ft.Text(f"Stock: {stk_actual} -> {stk_nuevo}{alerta_txt}", size=11, color=color_alerta or self.interfaz.secundario, width=150),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        self.interfaz.page.update()

    def al_subir_docx(self, guardados: list[Path]) -> None:
        if not guardados:
            return
        archivos_disco = sorted(list(self.carpeta_ml.glob("*.docx")))
        self.archivos_pendientes.clear()
        self.archivos_pendientes.extend(archivos_disco)
        self.selector_archivo.options = [
            ft.dropdown.Option(a.name) for a in self.archivos_pendientes
        ]
        arch = guardados[0]
        self.archivo_seleccionado[0] = arch
        self.selector_archivo.value = arch.name
        self.cargar_previsualizacion(arch)
        self.interfaz.page.update()

    async def subir_desde_pc(self, _e: ft.Event) -> None:
        try:
            guardados = await self.interfaz.subir_archivos_desde_pc(
                carpeta_destino=self.carpeta_ml,
                extensiones=["docx"],
                titulo="Seleccionar pedido de Mercado Libre (.docx)",
            )
            if guardados:
                self.al_subir_docx(guardados)
        except Exception as err:
            self.interfaz.notificar(f"Error al subir archivo de Mercado Libre: {err}")

    def descartar_archivo_seleccionado(self, _e: ft.Event) -> None:
        arch = self.archivo_seleccionado[0]
        if not arch:
            self.interfaz.notificar("No hay ningún archivo seleccionado para descartar.")
            return
        try:
            carpeta_descartados = self.carpeta_ml / "descartados"
            carpeta_descartados.mkdir(parents=True, exist_ok=True)
            dest = carpeta_descartados / arch.name
            if arch.exists():
                if dest.exists() and arch.resolve() != dest.resolve():
                    dest.unlink()
                if arch.resolve() != dest.resolve():
                    shutil.move(str(arch), str(dest))
        except Exception as err:
            self.interfaz.notificar(f"No se pudo descartar el archivo: {err}")
            return

        if arch in self.archivos_pendientes:
            self.archivos_pendientes.remove(arch)
        self.selector_archivo.options = [
            ft.dropdown.Option(a.name) for a in self.archivos_pendientes
        ]
        if self.archivos_pendientes:
            siguiente = self.archivos_pendientes[0]
            self.archivo_seleccionado[0] = siguiente
            self.selector_archivo.value = siguiente.name
            self.cargar_previsualizacion(siguiente)
        else:
            self.limpiar()
        self.interfaz.actualizar_estado()
        self.interfaz.page.update()
        self.interfaz.notificar(f"Archivo {arch.name} descartado de pendientes.")

    async def confirmar_descuento_docx(self, _e: ft.Event) -> None:
        if getattr(self, "_en_proceso_docx", False):
            return
        self._en_proceso_docx = True
        if not self.archivo_seleccionado[0] or not self.items_a_descontar:
            self.interfaz.notificar("Debes seleccionar un archivo .docx válido con productos para descontar.")
            return

        arch = self.archivo_seleccionado[0]
        if not arch.exists():
            self.interfaz.notificar(f"El archivo {arch.name} ya no existe en la carpeta de pendientes.")
            return

        hash_doc = calcular_hash_archivo(arch)
        if hash_doc:
            dup = self.interfaz.order_store.buscar_pedido_por_hash(hash_doc)
            if dup:
                self.interfaz.notificar(
                    f"⛔ Este archivo ya fue procesado el {dup.created_at[:16]} ({dup.nota_pedido}) y no puede volver a descontarse."
                )
                return

        res = self.resultado_parseo[0]
        armador_nom = self.interfaz.usuario_actual.nombre_identificador if self.interfaz.usuario_actual else "Operario"
        self.interfaz.page.pop_dialog()

        def ejecutar_descuento_ml() -> None:
            sm = _get_stock_manager()(self.interfaz.menu.ruta_excel_base)
            agente = AgenteRemitosStock(stock_manager=sm)
            reporte = agente.ejecutar(
                rutas_mercado_libre=[arch],
                carpeta_descuentos=self.interfaz.menu.carpeta_descuentos,
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
            if self.interfaz.order_store.existe_nota_pedido(nota_ml):
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

            sin_coincidencia_ml = list(res.descripciones_sin_coincidencia) if res else []
            self.interfaz.order_store.registrar_pedido(
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
                items_sin_coincidencia=sin_coincidencia_ml,
            )

            dest_final_carpeta = self.dest_archivado
            dest_final_carpeta.mkdir(parents=True, exist_ok=True)
            try:
                dest_final = dest_final_carpeta / arch.name
                if dest_final.exists() and arch.resolve() != dest_final.resolve():
                    dest_final.unlink()
                if arch.exists() and arch.resolve() != dest_final.resolve():
                    shutil.move(str(arch), str(dest_final))
            except Exception:
                pass

            self.interfaz.actualizar_listas()
            self.interfaz.sincronizar_sesiones(aviso_colaborativo=f"📄 {armador_nom} descontó lote ML ({arch.name})")
            print(f"[OK] Mercado Libre descontado: {nota_ml} | Cliente: {cliente_ml} | Items: {resumen_items} | PDF: {pdf_nom}")

        try:
            exito = await self.interfaz.ejecutar_tarea(f"Descuento Mercado Libre ({arch.name})", ejecutar_descuento_ml)
        finally:
            self._en_proceso_docx = False
        if exito:
            self.interfaz.notificar(f"Se descontaron exitosamente los productos de Mercado Libre ({arch.name}).")

    def construir_vista(self) -> ft.Column:
        return ft.Column(
            [
                ft.Text(
                    "Compara los nombres de productos del archivo .docx contra el catálogo y descuenta el stock en tiempo real en la base de datos.",
                    size=12,
                    color=self.interfaz.secundario,
                ),
                ft.Divider(height=8),
                ft.Row(
                    [
                        self.selector_archivo,
                        ft.Button(
                            "Cargar de PC",
                            icon=ft.Icons.UPLOAD_FILE,
                            bgcolor=ft.Colors.BLUE_GREY_800 if self.interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100,
                            color=self.interfaz.texto,
                            on_click=self.subir_desde_pc,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLEAR_ALL,
                            tooltip="Limpiar vista previa",
                            on_click=self.limpiar,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Descartar este archivo de pendientes",
                            on_click=self.descartar_archivo_seleccionado,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=bool(getattr(self.interfaz, "es_pantalla_movil", False)),
                    spacing=6,
                ),
                self.resumen_texto,
                self.banner_no_encontrados,
                ft.Text("Vista previa de productos a descontar:", size=12, weight=ft.FontWeight.BOLD, color=self.interfaz.texto),
                self.lista_previsualizacion,
            ],
            tight=True,
            spacing=8,
        )


def mostrar_descuento_mercado_libre(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana modularizada para procesar y descontar pedidos de Mercado Libre (Pistoleo en Vivo o archivo .docx)."""
    if not interfaz.exigir_roles("operador", "administrador"):
        return

    carpeta_ml = getattr(interfaz.menu, "carpeta_mercado_libre", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "MercadoLibre"
    )
    carpeta_ml.mkdir(parents=True, exist_ok=True)
    dest_archivado = (
        getattr(interfaz.menu, "carpeta_descontados", None) or (
            getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "descontados"
        )
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

    # Instanciar los subcomponentes modularizados
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
                ft.TabBarView(
                    expand=True,
                    controls=[vista_escaner, vista_docx],
                ),
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
