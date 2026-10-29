"""Diálogo modal para el relevamiento de inventario en tiempo real (móvil y PC).

Permite el conteo continuo de existencias físicas escaneando códigos de barras
mediante la cámara de celulares/tablets o lectores ópticos en PC, comparándolo
al instante contra el stock del sistema y generando reportes de diferencias.
"""

from __future__ import annotations

import inspect
import sqlite3
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict

import flet as ft

from ..theme import ROJO
from ...stock_manager import StockManager as _DefaultStockManager


def _get_stock_manager():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def abrir_url_en_navegador(page: Any, url: str) -> None:
    """Abre una URL de forma compatible tanto en Flet moderno (UrlLauncher) como clásico y fallback."""
    # 1. Page.launch_url (versiones anteriores de Flet)
    if hasattr(page, "launch_url") and callable(getattr(page, "launch_url")):
        try:
            page.launch_url(url, web_window_name="_blank")
            return
        except Exception:
            pass

    # 2. UrlLauncher (Flet 1.0+)
    try:
        launcher = None
        if hasattr(page, "services") and isinstance(page.services, list):
            for s in page.services:
                if isinstance(s, ft.UrlLauncher):
                    launcher = s
                    break
            if not launcher:
                launcher = ft.UrlLauncher()
                page.services.append(launcher)
                try:
                    page.update()
                except Exception:
                    pass

        if launcher:
            if hasattr(page, "run_task") and callable(page.run_task):
                page.run_task(launcher.launch_url, url, web_only_window_name="_blank")
            else:
                import asyncio
                coro = launcher.launch_url(url, web_only_window_name="_blank")
                if inspect.iscoroutine(coro):
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(coro)
                        else:
                            loop.run_until_complete(coro)
                    except Exception:
                        coro.close()
            return
    except Exception:
        pass

    # 3. Fallback de navegador del sistema
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass


def mostrar_dialogo_inventario_vivo(
    interfaz: Any,
    _evento: ft.Event | None = None,
) -> None:
    """Ventana interactiva de conteo físico en vivo con soporte de lector óptico y cámara móvil."""
    if not interfaz.exigir_roles("operador", "administrador", "master"):
        return

    sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
    usuario_operario = (
        interfaz.usuario_actual.username
        if interfaz.usuario_actual
        else "operador"
    )

    # Estado de la sesión de inventario en memoria
    # {codigo: cantidad_fisica_contada}
    conteo_fisico: Dict[str, int] = {}
    # Cache de metadatos de productos {codigo: {name, stock, cod_barras}}
    cache_productos: Dict[str, Dict[str, Any]] = {}

    def precargar_catalogo() -> None:
        for p in sm.product_store.list_products():
            c = str(p["code"]).strip()
            cache_productos[c] = {
                "code": c,
                "name": str(p["name"]).strip(),
                "stock": int(p["stock"]),
                "cod_barras": str(p["cod_barras"] or "").strip() if "cod_barras" in p.keys() else "",
            }

    precargar_catalogo()

    # Ancho responsivo para optimización en teléfonos móviles y tablets
    page_w = getattr(interfaz.page, "width", None)
    try:
        page_w = float(page_w) if page_w is not None and float(page_w) > 0 else 800.0
    except (ValueError, TypeError):
        page_w = 800.0

    ancho_modal = min(680, max(320, int(page_w - 24)))

    # Controles de interfaz principales
    input_escaneo = ft.TextField(
        label="Escanear código de barras o ingresar SKU",
        hint_text="Pasa el lector aquí o escribe el código...",
        prefix_icon=ft.Icons.BARCODE_READER,
        autofocus=True,
        expand=True,
        dense=True,
    )

    def decrementar_input_cantidad() -> None:
        try:
            val = int(input_cantidad.value or "1")
        except ValueError:
            val = 1
        input_cantidad.value = str(max(1, val - 1))
        interfaz.page.update()

    def incrementar_input_cantidad() -> None:
        try:
            val = int(input_cantidad.value or "1")
        except ValueError:
            val = 1
        input_cantidad.value = str(val + 1)
        interfaz.page.update()

    def set_cantidad_directa(val: int) -> None:
        input_cantidad.value = str(max(1, val))
        interfaz.page.update()

    btn_menos_cant = ft.IconButton(
        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
        icon_size=24,
        tooltip="Restar cantidad",
        on_click=lambda _e: decrementar_input_cantidad(),
    )

    input_cantidad = ft.TextField(
        label="Cant.",
        value="1",
        width=60,
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER,
        dense=True,
    )

    btn_mas_cant = ft.IconButton(
        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
        icon_size=24,
        tooltip="Aumentar cantidad",
        on_click=lambda _e: incrementar_input_cantidad(),
    )

    stepper_cantidad = ft.Row(
        [btn_menos_cant, input_cantidad, btn_mas_cant],
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    btn_sumar = ft.Button(
        "Sumar",
        icon=ft.Icons.ADD,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        height=40,
        expand=True,
    )

    btn_camara = ft.IconButton(
        icon=ft.Icons.CAMERA_ALT,
        tooltip="Activar Escáner de Cámara (Móvil / Web)",
        icon_color=ft.Colors.BLUE_400,
        icon_size=24,
        url="/scanner.html",
    )

    fila_acciones = ft.Row(
        [
            stepper_cantidad,
            btn_sumar,
            btn_camara,
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    fila_chips_cantidad = ft.Row(
        [
            ft.Text("Cant. rápida:", size=11, color=interfaz.secundario, weight=ft.FontWeight.BOLD),
            ft.TextButton("+1", on_click=lambda _e: set_cantidad_directa(1)),
            ft.TextButton("+5", on_click=lambda _e: set_cantidad_directa(5)),
            ft.TextButton("+10", on_click=lambda _e: set_cantidad_directa(10)),
            ft.TextButton("+24", on_click=lambda _e: set_cantidad_directa(24)),
            ft.TextButton("+50", on_click=lambda _e: set_cantidad_directa(50)),
        ],
        spacing=2,
        wrap=True,
    )

    texto_feedback = ft.Text(
        "Listo para escanear. Los productos se sumarán automáticamente al conteo.",
        size=12,
        color=interfaz.secundario,
    )

    badge_resumen = ft.Text(
        "0 productos relevados (0 unidades)",
        size=12,
        weight=ft.FontWeight.BOLD,
        color=interfaz.texto,
    )

    lista_contados = ft.ListView(expand=True, spacing=8, height=300)

    def refrescar_vista_contados() -> None:
        lista_contados.controls.clear()
        total_items = len(conteo_fisico)
        total_unidades = sum(conteo_fisico.values())
        badge_resumen.value = f"{total_items} producto{'s' if total_items != 1 else ''} relevado{'s' if total_items != 1 else ''} ({total_unidades} unidades)"

        if not conteo_fisico:
            lista_contados.controls.append(
                ft.Container(
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.DOCUMENT_SCANNER, size=40, color=interfaz.secundario),
                            ft.Text(
                                "No hay productos contados todavía en esta sesión.\n"
                                "Usa la pistola lectora, la cámara móvil o ingresa el código arriba.",
                                text_align=ft.TextAlign.CENTER,
                                color=interfaz.secundario,
                                size=12,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                )
            )
            interfaz.page.update()
            return

        # Listar en orden inverso (los últimos escaneados primero)
        for cod, cant in reversed(list(conteo_fisico.items())):
            info = cache_productos.get(cod, {
                "code": cod,
                "name": "Producto fuera de catálogo",
                "stock": 0,
                "cod_barras": "",
            })
            stk_dig = info["stock"]
            dif = cant - stk_dig
            if dif == 0:
                dif_txt = "COINCIDE"
                dif_color = ft.Colors.GREEN_400
            elif dif < 0:
                dif_txt = f"{dif} FALTANTE"
                dif_color = ft.Colors.RED_400
            else:
                dif_txt = f"+{dif} SOBRANTE"
                dif_color = ft.Colors.AMBER_400

            barras_tag = info["cod_barras"]

            fila_item = ft.Container(
                padding=ft.Padding.all(8),
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                bgcolor=interfaz.superficie,
                content=ft.Column(
                    [
                        # Nivel 1: SKU + Código de barras (izq) y Estado comparativo (der)
                        ft.Row(
                            [
                                ft.Row(
                                    [
                                        ft.Text(cod, weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                                        ft.Container(
                                            content=ft.Text(
                                                f"🏷️ {barras_tag}" if barras_tag else "Sin código barras",
                                                size=10,
                                                color=ft.Colors.WHITE if barras_tag else interfaz.secundario,
                                            ),
                                            bgcolor=ft.Colors.BLUE_GREY_700 if barras_tag else ft.Colors.TRANSPARENT,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                        ),
                                    ],
                                    spacing=6,
                                    wrap=True,
                                ),
                                ft.Container(
                                    content=ft.Text(dif_txt, size=10, weight=ft.FontWeight.BOLD, color=dif_color),
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    border=ft.Border.all(1, dif_color),
                                    border_radius=4,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        # Nivel 2: Nombre del producto amplio y legible para pantallas pequeñas
                        ft.Text(
                            info["name"],
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=interfaz.texto,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        # Nivel 3: Stock digital vs físico y botones táctiles cómodos
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(f"Stock Digital: {stk_dig} un.", size=11, color=interfaz.secundario),
                                        ft.Text(f"Relevado: {cant} un.", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                                    ],
                                    spacing=1,
                                ),
                                ft.Row(
                                    [
                                        ft.IconButton(
                                            icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                                            icon_size=20,
                                            tooltip="Restar 1",
                                            on_click=lambda _e, c=cod: ajustar_cantidad(c, -1),
                                        ),
                                        ft.Text(str(cant), weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto),
                                        ft.IconButton(
                                            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                            icon_size=20,
                                            tooltip="Sumar 1",
                                            on_click=lambda _e, c=cod: ajustar_cantidad(c, 1),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            icon_size=20,
                                            icon_color=ft.Colors.RED_400,
                                            tooltip="Quitar del conteo",
                                            on_click=lambda _e, c=cod: eliminar_item(c),
                                        ),
                                    ],
                                    spacing=1,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=5,
                ),
            )
            lista_contados.controls.append(fila_item)

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

    def buscar_producto_por_termino(termino: str) -> sqlite3.Row | None:
        t = termino.strip()
        if not t:
            return None
        # 1. Chequear en cache local
        if t in cache_productos:
            # Retornar objeto tipo row o dict
            return cache_productos[t]
        # Chequear por barcode en cache
        for p in cache_productos.values():
            if p["cod_barras"] and p["cod_barras"] == t:
                return p
        # 2. Consultar directamente a la base de datos SQLite
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

    def safe_focus(ctrl: Any) -> None:
        try:
            res = ctrl.focus()
            if inspect.iscoroutine(res):
                if hasattr(interfaz.page, "run_task") and callable(interfaz.page.run_task):
                    async def _focus_coro():
                        await res
                    interfaz.page.run_task(_focus_coro)
                else:
                    res.close()
        except Exception:
            pass

    def procesar_escaneo(_e: ft.Event | None = None) -> None:
        valor = (input_escaneo.value or "").strip()
        if not valor:
            return

        try:
            cant_a_sumar = max(1, int(input_cantidad.value or "1"))
        except ValueError:
            cant_a_sumar = 1
            input_cantidad.value = "1"

        prod = buscar_producto_por_termino(valor)
        if prod is not None:
            cod = prod["code"]
            conteo_fisico[cod] = conteo_fisico.get(cod, 0) + cant_a_sumar
            texto_feedback.value = f"✅ Contado '{prod['name']}' [{cod}] (+{cant_a_sumar} un. | Total: {conteo_fisico[cod]})"
            texto_feedback.color = ft.Colors.GREEN_400
        else:
            # El código no pertenece a ningún SKU ni código de barras registrado
            # Permitir asociarlo a un producto o registrarlo como ítem directo
            mostrar_dialogo_asociar_codigo_barras(valor, cant_a_sumar)
            input_escaneo.value = ""
            safe_focus(input_escaneo)
            interfaz.page.update()
            return

        input_escaneo.value = ""
        safe_focus(input_escaneo)
        refrescar_vista_contados()

    def mostrar_dialogo_asociar_codigo_barras(codigo_leido: str, cant_a_sumar: int) -> None:
        """Permite asociar un código de barras nuevo a un producto del catálogo."""
        filtro_asoc = ft.TextField(
            label="Buscar producto para asociar este código de barras",
            hint_text="Escribe el nombre o SKU...",
            autofocus=True,
            dense=True,
        )
        lista_opciones = ft.ListView(expand=True, spacing=4, height=180)

        def render_opciones() -> None:
            lista_opciones.controls.clear()
            filtro = (filtro_asoc.value or "").strip().casefold()
            coincidencias = [
                p for p in cache_productos.values()
                if not filtro or filtro in f"{p['code']} {p['name']}".casefold()
            ]
            for p in coincidencias[:20]:
                cod_prod = p["code"]
                nom_prod = p["name"]
                lista_opciones.controls.append(
                    ft.ListTile(
                        title=ft.Text(f"{cod_prod} - {nom_prod}", size=12, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(f"Stock actual: {p['stock']} un.", size=11, color=interfaz.secundario),
                        trailing=ft.Button("Asociar", on_click=lambda _e, c=cod_prod: confirmar_asociacion(c)),
                        dense=True,
                    )
                )
            interfaz.page.update()

        def confirmar_asociacion(cod_prod: str) -> None:
            sm.asignar_codigo_barras(cod_prod, codigo_leido)
            if cod_prod in cache_productos:
                cache_productos[cod_prod]["cod_barras"] = codigo_leido
            conteo_fisico[cod_prod] = conteo_fisico.get(cod_prod, 0) + cant_a_sumar
            interfaz.page.pop_dialog()
            texto_feedback.value = f"✅ Código de barras '{codigo_leido}' asignado a [{cod_prod}] (+{cant_a_sumar} un.)"
            texto_feedback.color = ft.Colors.GREEN_400
            refrescar_vista_contados()

        filtro_asoc.on_change = lambda _e: render_opciones()
        render_opciones()

        dlg_asoc = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.LINK, color=ft.Colors.BLUE_400),
                    ft.Text(f"Código no registrado: {codigo_leido}", size=14, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=min(480, max(300, int(page_w - 24))),
                content=ft.Column(
                    [
                        ft.Text(
                            "Este código no está registrado en el catálogo. Puedes vincularlo "
                            "ahora mismo a un producto existente:",
                            size=12,
                            color=interfaz.secundario,
                        ),
                        filtro_asoc,
                        lista_opciones,
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
            ],
        )
        interfaz.page.show_dialog(dlg_asoc)

    def abrir_escaner_camara(_e: ft.Event | None = None) -> None:
        """Abre el escáner de cámara móvil / web en una ventana dedicada."""
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

        resultado = await interfaz.ejecutar_tarea(
            "Generación de Comparativa de Inventario Físico",
            tarea_procesar,
        )

        if resultado:
            ruta_doc, comparativa = resultado
            mostrar_resumen_inventario_finalizado(ruta_doc, comparativa)

    def mostrar_resumen_inventario_finalizado(ruta_doc: Path, comparativa: list) -> None:
        total = len(comparativa)
        coinciden = sum(1 for i in comparativa if i["diferencia"] == 0 and i["en_catalogo"])
        faltantes = sum(1 for i in comparativa if i["diferencia"] < 0 and i["en_catalogo"])
        sobrantes = sum(1 for i in comparativa if i["diferencia"] > 0 and i["en_catalogo"])

        contenido_resumen = ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=32),
                        ft.Column(
                            [
                                ft.Text("¡Relevamiento finalizado con éxito!", weight=ft.FontWeight.BOLD, size=15, color=interfaz.texto),
                                ft.Text(f"Operario: {usuario_operario} · Archivo: {ruta_doc.name}", size=12, color=interfaz.secundario),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=12,
                ),
                ft.Divider(height=14),
                ft.Row(
                    [
                        ft.Container(
                            bgcolor=ft.Colors.GREEN_900 if interfaz.modo_oscuro else ft.Colors.GREEN_50,
                            padding=10,
                            border_radius=8,
                            expand=True,
                            content=ft.Column(
                                [
                                    ft.Text("COINCIDEN", size=10, color=ft.Colors.GREEN_400, weight=ft.FontWeight.BOLD),
                                    ft.Text(str(coinciden), size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=2,
                            ),
                        ),
                        ft.Container(
                            bgcolor=ft.Colors.RED_900 if interfaz.modo_oscuro else ft.Colors.RED_50,
                            padding=10,
                            border_radius=8,
                            expand=True,
                            content=ft.Column(
                                [
                                    ft.Text("FALTANTES", size=10, color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD),
                                    ft.Text(str(faltantes), size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=2,
                            ),
                        ),
                        ft.Container(
                            bgcolor=ft.Colors.AMBER_900 if interfaz.modo_oscuro else ft.Colors.AMBER_50,
                            padding=10,
                            border_radius=8,
                            expand=True,
                            content=ft.Column(
                                [
                                    ft.Text("SOBRANTES", size=10, color=ft.Colors.AMBER_400, weight=ft.FontWeight.BOLD),
                                    ft.Text(str(sobrantes), size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=2,
                            ),
                        ),
                    ],
                    spacing=8,
                ),
                ft.Divider(height=14),
                ft.Container(
                    bgcolor=interfaz.superficie,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Text("Planilla Excel comparativa generada:", size=11, color=interfaz.secundario, weight=ft.FontWeight.BOLD),
                            ft.Text(str(ruta_doc.name), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400),
                            ft.Text("El administrador ha sido notificado automáticamente.", size=11, color=interfaz.secundario),
                        ],
                        spacing=3,
                    ),
                ),
            ],
            tight=True,
            width=min(520, max(300, int(page_w - 24))),
            spacing=8,
        )

        dlg_res = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.FACT_CHECK, color=ROJO),
                    ft.Text("Balance de Relevamiento de Inventario", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=contenido_resumen,
            actions=[
                interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
                interfaz.boton_dialogo("Abrir Excel", lambda _e: (interfaz.page.pop_dialog(), interfaz.abrir_informe(ruta_especifica=ruta_doc))),
                interfaz.boton_dialogo("Compartir Correo", lambda _e: (interfaz.page.pop_dialog(), interfaz.compartir_correo(ruta_especifica=ruta_doc))),
                interfaz.boton_dialogo("WhatsApp", lambda _e: (interfaz.page.pop_dialog(), interfaz.compartir_whatsapp(ruta_especifica=ruta_doc))),
            ],
        )
        interfaz.page.show_dialog(dlg_res)

    btn_sumar.on_click = procesar_escaneo
    btn_camara.on_click = abrir_escaner_camara
    input_escaneo.on_submit = procesar_escaneo
    refrescar_vista_contados()

    dialogo_principal = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.DOCUMENT_SCANNER, color=ROJO, size=24),
                ft.Text("Inventario en Vivo", weight=ft.FontWeight.BOLD, size=16),
            ],
            spacing=8,
        ),
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
                            ft.TextButton(
                                "Limpiar Sesión",
                                icon=ft.Icons.CLEAR_ALL,
                                on_click=lambda _e: (conteo_fisico.clear(), refrescar_vista_contados()),
                            ),
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
            ft.Button(
                "Finalizar y Comparar Stock",
                icon=ft.Icons.CHECK_CIRCLE,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=finalizar_inventario,
            ),
        ],
    )
    interfaz.page.show_dialog(dialogo_principal)
