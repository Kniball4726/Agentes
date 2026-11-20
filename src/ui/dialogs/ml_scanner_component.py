"""Componente de pistoleo y escáner en vivo para pedidos de Mercado Libre."""

from __future__ import annotations

from datetime import datetime
import sys
from typing import Any, Callable

import flet as ft

from ..audio_feedback import emitir_tono_error, emitir_tono_exito, normalizar_codigo_lector
from ..theme import ROJO
from ...core.environment import get_data_dir
from ...core.security_utils import resolver_ruta_confinada, sanitizar_componente_archivo
from ...inventory import StockManager as _DefaultStockManager
from ...paths import application_root
from ...stock.models import RegistroDescuento
from ._shared import safe_focus
from .ml_helpers import generar_docx_respaldo_escaner, mostrar_prompt_rotulo_ml


def _resolver_sm():
    mod_ml = sys.modules.get("src.ui.dialogs.dlg_mercadolibre_descuento")
    if mod_ml is not None and hasattr(mod_ml, "_get_stock_manager"):
        return mod_ml._get_stock_manager()
    return _DefaultStockManager


class MercadoLibreScannerComponent:
    """Gestiona el escaneo en vivo de productos y el armado de paquetes de Mercado Libre."""

    def __init__(self, interfaz: Any, al_cambiar_estado: Callable | None = None) -> None:
        self.interfaz = interfaz
        self.al_cambiar_estado = al_cambiar_estado
        self.items_escaneados: dict[str, int] = {}

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
        self.lista_escaneo_view = ft.ListView(expand=True, spacing=4, height=220)
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

    def _buscar_en_catalogo(self, sm: Any, codigo_limpio: str) -> tuple[str | None, str | None, int]:
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

        if prod_encontrado:
            return str(prod_encontrado["code"]).strip(), str(prod_encontrado["name"]).strip(), int(prod_encontrado["stock"])
        if codigo_limpio in sm.catalogo:
            _, nombre_final, stk_actual = sm.catalogo[codigo_limpio]
            return codigo_limpio, nombre_final, stk_actual
        for k, v in sm.catalogo.items():
            if k.upper() == codigo_limpio.upper():
                return k, v[1], v[2]
        return None, None, 0

    def procesar_lectura_codigo(self) -> None:
        raw = (self.input_codigo.value or "").strip()
        if not raw:
            return
        codigo_limpio = normalizar_codigo_lector(raw) or raw
        try:
            cant_a_sumar = max(1, int(self.input_cant.value or "1"))
        except ValueError:
            cant_a_sumar = 1

        sm = _resolver_sm()(self.interfaz.menu.ruta_excel_base)
        sku_final, nombre_final, stk_actual = self._buscar_en_catalogo(sm, codigo_limpio)

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

        nueva_cant = self.items_escaneados.get(sku_final, 0) + cant_a_sumar
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

    def _crear_ajustar_handler(self, sku: str, delta: int):
        def handler(_e: ft.Event):
            nueva = self.items_escaneados.get(sku, 1) + delta
            if nueva <= 0:
                self.items_escaneados.pop(sku, None)
            else:
                self.items_escaneados[sku] = nueva
            self.actualizar_vista()
            self.enfocar()
            self.interfaz.page.update()
        return handler

    def _crear_eliminar_handler(self, sku: str):
        def handler(_e: ft.Event):
            cant_previa = self.items_escaneados.pop(sku, 1)
            self.actualizar_vista()
            self.enfocar()
            self.interfaz.page.update()

            def restaurar_item(_ev):
                self.items_escaneados[sku] = cant_previa
                self.actualizar_vista()
                self.enfocar()
                self.interfaz.page.update()

            try:
                snack_undo = ft.SnackBar(
                    content=ft.Text(f"Se quitó [{sku}] ({cant_previa} un.)", size=12),
                    action="Deshacer",
                    action_color=ft.Colors.AMBER_400,
                    on_action=restaurar_item,
                    duration=4500,
                )
                self.interfaz.page.show_dialog(snack_undo)
                self.interfaz.page.update()
            except Exception:
                pass
        return handler

    def actualizar_vista(self) -> None:
        self.lista_escaneo_view.controls.clear()
        sm = _resolver_sm()(self.interfaz.menu.ruta_excel_base)

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

            self.lista_escaneo_view.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if self.interfaz.modo_oscuro else ft.Colors.GREY_100,
                    border=ft.Border.all(
                        1,
                        ft.Colors.RED_400 if stk_rest <= 0 else (ft.Colors.WHITE_24 if self.interfaz.modo_oscuro else ft.Colors.GREY_300),
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
                                    ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_size=18, tooltip="Restar 1", on_click=self._crear_ajustar_handler(sku, -1)),
                                    ft.Text(f"{cant} un.", weight=ft.FontWeight.BOLD, size=12),
                                    ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, icon_size=18, tooltip="Sumar 1", on_click=self._crear_ajustar_handler(sku, 1)),
                                    ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_size=18, icon_color=ft.Colors.RED_400, tooltip="Quitar producto", on_click=self._crear_eliminar_handler(sku)),
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
        if not self.items_escaneados:
            self.interfaz.notificar("Debes escanear al menos un producto antes de confirmar el paquete.")
            return
        self._en_proceso_descuento = True

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
            sm = _resolver_sm()(self.interfaz.menu.ruta_excel_base)
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
                        fila, nom, stk_ant = 0, p_row["name"], p_row["stock"]
                    else:
                        fila, nom, stk_ant = 0, f"Producto {cod}", 0

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

            nota_segura = sanitizar_componente_archivo(nota_ml, fallback="ML_SCAN")
            nombre_doc = f"ML_SCAN_{nota_segura}.docx"
            dest_pedidos = get_data_dir() / "pedidos_archivos"
            dest_pedidos.mkdir(parents=True, exist_ok=True)
            ruta_doc_segura = resolver_ruta_confinada(dest_pedidos, nombre_doc)
            hash_doc = generar_docx_respaldo_escaner(
                ruta_doc_segura, nota_ml, cliente_ml, armador_nom, total_unidades, items_pedido_store
            )

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
                self.interfaz.sincronizar_sesiones(
                    aviso_colaborativo=f"🏷️ {armador_nom} descontó paquete ML #{nota_ml} ({cliente_ml})"
                )
            print(f"[OK] Mercado Libre (Escáner) descontado: {nota_ml} | Cliente: {cliente_ml} | Items: {resumen_items}")
            mostrar_prompt_rotulo_ml(self.interfaz, ped_creado, nota_ml, cliente_ml, bultos_val, resumen_items)

        try:
            exito = await self.interfaz.ejecutar_tarea(f"Descuento Mercado Libre Escáner ({nota_ml})", tarea_descuento)
        finally:
            self._en_proceso_descuento = False
        if exito:
            if hasattr(self.interfaz, "reproducir_sonido"):
                self.interfaz.reproducir_sonido("exito")
            self.interfaz.notificar(
                f"✅ Paquete Mercado Libre {nota_ml} descontado exitosamente ({sum(self.items_escaneados.values())} un.)."
            )

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
                ft.Row([self.input_guia_ml, self.input_comprador_ml, self.input_bultos_ml], spacing=6),
                self.texto_feedback,
                ft.Divider(height=6),
                ft.Row(
                    [
                        ft.Text("Productos en el paquete actual:", size=12, weight=ft.FontWeight.BOLD, color=self.interfaz.texto, expand=True),
                        ft.IconButton(icon=ft.Icons.DELETE_SWEEP, tooltip="Vaciar paquete", icon_size=18, on_click=self.limpiar),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.lista_escaneo_view,
                ft.Divider(height=6),
                ft.Row(
                    [self.resumen_escaneo_texto, self.btn_confirmar_paquete],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            tight=True,
            spacing=8,
        )
