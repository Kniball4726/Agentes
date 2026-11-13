"""Diálogo modal para el relevamiento de inventario en tiempo real (móvil y PC).

Permite el conteo continuo de existencias físicas escaneando códigos de barras
mediante la cámara de celulares/tablets o lectores ópticos en PC, comparándolo
al instante contra el stock del sistema y generando reportes de diferencias.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict

import flet as ft

from ...stock_manager import StockManager as _DefaultStockManager
from ..theme import ROJO
from ._shared import safe_focus
from .inventario_vivo_views import (
    abrir_url_en_navegador,
    construir_estado_vacio_inventario,
    construir_tarjeta_producto_contado,
    mostrar_dialogo_asociar_codigo_barras,
    mostrar_resumen_inventario_finalizado,
)


def _get_stock_manager():
    """Devuelve StockManager vigente (respetando mocks sobre src.flet_gui o este módulo)."""
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def _buscar_producto_en_cache_o_db(
    sm: Any,
    cache_productos: dict[str, dict[str, Any]],
    termino: str,
) -> sqlite3.Row | dict[str, Any] | None:
    """Busca un producto por código SKU o código de barras en caché local y luego SQLite."""
    from src.products.barcode_utils import (
        coincide_codigo_o_barras,
        generar_variantes_codigo_lector,
        normalizar_codigo_lector,
    )

    t = normalizar_codigo_lector(termino)
    if not t:
        return None
    for cand in generar_variantes_codigo_lector(termino):
        if cand in cache_productos:
            return cache_productos[cand]
    for p in cache_productos.values():
        if coincide_codigo_o_barras(p, termino):
            return p

    row = sm.product_store.find_product_by_code_or_barcode(t)
    if row is not None:
        c = str(row["code"]).strip()
        cache_productos[c] = {
            "code": c,
            "name": str(row["name"]).strip(),
            "stock": int(row["stock"]),
            "cod_barras": str(row["cod_barras"] or "").strip() if "cod_barras" in row.keys() else "",
        }
        return cache_productos[c]
    return None


def mostrar_dialogo_inventario_vivo(
    interfaz: Any,
    _evento: ft.Event | None = None,
) -> None:
    """Ventana interactiva de conteo físico en vivo con soporte de lector óptico y cámara móvil."""
    if not interfaz.exigir_roles("operador", "administrador"):
        return

    sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
    usuario_operario = (
        interfaz.usuario_actual.username
        if interfaz.usuario_actual
        else "operador"
    )

    conteo_fisico: Dict[str, int] = {}
    cache_productos: Dict[str, Dict[str, Any]] = {}
    for p in sm.product_store.list_products():
        c = str(p["code"]).strip()
        cache_productos[c] = {
            "code": c,
            "name": str(p["name"]).strip(),
            "stock": int(p["stock"]),
            "cod_barras": str(p["cod_barras"] or "").strip() if "cod_barras" in p.keys() else "",
        }

    page_w = getattr(interfaz.page, "width", None)
    try:
        page_w = float(page_w) if page_w is not None and float(page_w) > 0 else 800.0
    except (ValueError, TypeError):
        page_w = 800.0
    ancho_modal = min(680, max(320, int(page_w - 24)))

    input_escaneo = ft.TextField(
        label="Escanear código de barras o ingresar SKU",
        hint_text="Pasa la pistola lectora (Barcode Wedge) o escribe el código...",
        prefix_icon=ft.Icons.BARCODE_READER,
        autofocus=True,
        expand=True,
        dense=True,
    )
    input_cantidad = ft.TextField(
        label="Cant.",
        value="1",
        width=60,
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER,
        dense=True,
    )

    def actualizar_input_cantidad(nuevo_valor: int | None = None, delta: int = 0) -> None:
        try:
            actual = int(input_cantidad.value or "1")
        except ValueError:
            actual = 1
        val = actual + delta if nuevo_valor is None else nuevo_valor
        input_cantidad.value = str(max(1, val))
        interfaz.page.update()

    btn_sumar = ft.Button("Sumar", icon=ft.Icons.ADD, bgcolor=ROJO, color=ft.Colors.WHITE, height=40, expand=True)
    btn_camara = ft.IconButton(
        icon=ft.Icons.CAMERA_ALT,
        tooltip="Activar Escáner de Cámara (Móvil / Web)",
        icon_color=ft.Colors.BLUE_400,
        icon_size=24,
        url="/scanner.html",
    )
    fila_acciones = ft.Row(
        [
            ft.Row(
                [
                    ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_size=24, tooltip="Restar cantidad", on_click=lambda _e: actualizar_input_cantidad(delta=-1)),
                    input_cantidad,
                    ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, icon_size=24, tooltip="Aumentar cantidad", on_click=lambda _e: actualizar_input_cantidad(delta=1)),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            btn_sumar,
            btn_camara,
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    fila_chips_cantidad = ft.Row(
        [
            ft.Text("Cant. rápida:", size=11, color=interfaz.secundario, weight=ft.FontWeight.BOLD),
            *[ft.TextButton(f"+{v}", on_click=lambda _e, val=v: actualizar_input_cantidad(nuevo_valor=val)) for v in (1, 5, 10, 24, 50)],
        ],
        spacing=2,
        wrap=True,
    )

    texto_feedback = ft.Text(
        "Listo para escanear. Los productos se sumarán automáticamente al conteo.",
        size=12,
        color=interfaz.secundario,
    )
    badge_resumen = ft.Text("0 productos relevados (0 unidades)", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto)
    lista_contados = ft.ListView(expand=True, spacing=8, height=300)

    def refrescar_vista_contados() -> None:
        lista_contados.controls.clear()
        total_items = len(conteo_fisico)
        total_unidades = sum(conteo_fisico.values())
        badge_resumen.value = f"{total_items} producto{'s' if total_items != 1 else ''} relevado{'s' if total_items != 1 else ''} ({total_unidades} unidades)"

        if not conteo_fisico:
            lista_contados.controls.append(construir_estado_vacio_inventario(interfaz))
            interfaz.page.update()
            return

        for cod, cant in reversed(list(conteo_fisico.items())):
            info = cache_productos.get(cod, {"code": cod, "name": "Producto fuera de catálogo", "stock": 0, "cod_barras": ""})
            lista_contados.controls.append(
                construir_tarjeta_producto_contado(interfaz, cod, cant, info, ajustar_cantidad, eliminar_item)
            )
        interfaz.page.update()

    def ajustar_cantidad(codigo: str, delta: int) -> None:
        if codigo in conteo_fisico:
            nueva = conteo_fisico[codigo] + delta
            if nueva <= 0:
                del conteo_fisico[codigo]
            else:
                conteo_fisico[codigo] = nueva
            refrescar_vista_contados()

    def eliminar_item(codigo: str) -> None:
        if codigo in conteo_fisico:
            del conteo_fisico[codigo]
            refrescar_vista_contados()

    def procesar_escaneo(_e: ft.Event | None = None) -> None:
        from ..audio_feedback import emitir_tono_error, emitir_tono_exito, normalizar_codigo_lector

        valor = normalizar_codigo_lector(input_escaneo.value or "")
        if not valor:
            return

        try:
            cant_a_sumar = max(1, int(input_cantidad.value or "1"))
        except ValueError:
            cant_a_sumar = 1
            input_cantidad.value = "1"

        prod = _buscar_producto_en_cache_o_db(sm, cache_productos, valor)
        if prod is not None:
            cod = prod["code"]
            conteo_fisico[cod] = conteo_fisico.get(cod, 0) + cant_a_sumar
            texto_feedback.value = f"✅ Contado '{prod['name']}' [{cod}] (+{cant_a_sumar} un. | Total: {conteo_fisico[cod]})"
            texto_feedback.color = ft.Colors.GREEN_400
            emitir_tono_exito()
        else:
            emitir_tono_error()

            def _al_asociar(cod_prod: str) -> None:
                texto_feedback.value = f"✅ Código de barras '{valor}' asignado a [{cod_prod}] (+{cant_a_sumar} un.)"
                texto_feedback.color = ft.Colors.GREEN_400
                refrescar_vista_contados()

            mostrar_dialogo_asociar_codigo_barras(
                interfaz, sm, cache_productos, conteo_fisico, page_w, valor, cant_a_sumar, _al_asociar
            )
            input_escaneo.value = ""
            safe_focus(interfaz, input_escaneo)
            interfaz.page.update()
            return

        input_escaneo.value = ""
        safe_focus(interfaz, input_escaneo)
        refrescar_vista_contados()

    def abrir_escaner_camara(_e: ft.Event | None = None) -> None:
        abrir_url_en_navegador(interfaz.page, "/scanner.html")
        interfaz.notificar(
            "Se abrió el escáner de cámara. Apunta al código de barras en tu celular "
            "y los códigos leídos se reflejarán en tu sesión."
        )

    async def finalizar_inventario(_e: ft.Event) -> None:
        if not conteo_fisico:
            interfaz.notificar("Debes escanear al menos un producto antes de finalizar el relevamiento.")
            return

        interfaz.page.pop_dialog()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_arch = f"Inventario_Escaner_{timestamp}.xlsx"

        async def tarea_procesar():
            return sm.procesar_stock_fisico(
                conteo_fisico=conteo_fisico,
                usuario=usuario_operario,
                nombre_archivo=nombre_arch,
            )

        resultado = await interfaz.ejecutar_tarea("Generación de Comparativa de Inventario Físico", tarea_procesar)
        if resultado:
            ruta_doc, comparativa = resultado
            mostrar_resumen_inventario_finalizado(interfaz, usuario_operario, page_w, ruta_doc, comparativa)

    btn_sumar.on_click = procesar_escaneo
    btn_camara.on_click = abrir_escaner_camara
    input_escaneo.on_submit = procesar_escaneo
    refrescar_vista_contados()

    dialogo_principal = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.DOCUMENT_SCANNER, color=ROJO, size=24), ft.Text("Inventario en Vivo", weight=ft.FontWeight.BOLD, size=16)], spacing=8),
        content=ft.Container(
            width=ancho_modal,
            content=ft.Column(
                [
                    ft.Row([input_escaneo], spacing=8),
                    fila_acciones,
                    fila_chips_cantidad,
                    texto_feedback,
                    ft.Divider(height=10),
                    ft.Row(
                        [
                            badge_resumen,
                            ft.TextButton("Limpiar Sesión", icon=ft.Icons.CLEAR_ALL, on_click=lambda _e: (conteo_fisico.clear(), refrescar_vista_contados())),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    lista_contados,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            ft.Button("Finalizar y Comparar Stock", icon=ft.Icons.CHECK_CIRCLE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=finalizar_inventario),
        ],
    )
    interfaz.page.show_dialog(dialogo_principal)
