"""Diálogo de creación y armado de pedidos en tiempo real con detección preventiva de quiebre."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Callable

import flet as ft

from ...agent import AgenteRemitosStock
from ...inventory import StockManager as _DefaultStockManager
from ...orders import LOGISTICA_OPCIONES, calcular_hash_archivo
from ...paths import application_root
from ..theme import ROJO


def _resolver_sm_cls():
    mod_ped = sys.modules.get("src.ui.dialogs.dlg_pedidos")
    if mod_ped is not None and hasattr(mod_ped, "_get_stock_manager_cls"):
        return mod_ped._get_stock_manager_cls()
    mod_gui = sys.modules.get("src.flet_gui")
    if mod_gui is not None and hasattr(mod_gui, "StockManager"):
        return getattr(mod_gui, "StockManager")
    return _DefaultStockManager


def _mostrar_dialogo_exito_pedido(
    interfaz: Any,
    remito: str,
    cli: str,
    bultos_val: int,
    log: str,
    resumen_items: str,
    reporte: Any,
) -> None:
    """Ofrece impresión inmediata de rótulos y muestra alertas de stock crítico tras registrar un pedido."""
    try:
        pedido_reciente = interfaz.order_store.buscar_pedido_por_nota(remito)
        if not (pedido_reciente and interfaz.page):
            return
        items_alerta = []
        for d in reporte.reporte_stock.descuentos_aplicados:
            if d.stock_nuevo <= 0:
                items_alerta.append(f"🔴 [{d.codigo}] {d.nombre_producto}: QUIEBRE (Quedan {d.stock_nuevo} un.)")
            elif d.stock_nuevo <= 5:
                items_alerta.append(f"🟠 [{d.codigo}] {d.nombre_producto}: CRÍTICO (Quedan {d.stock_nuevo} un.)")

        def cerrar_exito(_e):
            interfaz.page.pop_dialog()

        def imprimir_rotulos_directo(_e, ped=pedido_reciente):
            interfaz.page.pop_dialog()
            interfaz.imprimir_rotulos_pedido(ped)

        dialogo_exito = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400), ft.Text("Pedido Registrado y Descontado")]),
            content=ft.Container(
                width=450,
                content=ft.Column(
                    [
                        ft.Text(f"El pedido #{remito} de '{cli}' fue procesado con éxito.", size=13, weight=ft.FontWeight.W_500),
                        ft.Text(f"• Bultos: {bultos_val} · Logística: {log}", size=12, color=interfaz.secundario),
                        ft.Text(f"• Descuento: {resumen_items} en tiempo real.", size=12, color=ft.Colors.GREEN_400),
                        *(
                            [
                                ft.Divider(height=10),
                                ft.Text("⚠️ Advertencia de Inventario:", weight=ft.FontWeight.BOLD, size=11, color=ft.Colors.AMBER_400),
                                ft.Container(
                                    content=ft.ListView([ft.Text(it, size=11, color=interfaz.texto) for it in items_alerta], height=70, spacing=2),
                                    bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_100,
                                    padding=6,
                                    border_radius=4,
                                ),
                            ]
                            if items_alerta
                            else []
                        ),
                        ft.Divider(height=10),
                        ft.Text("¿Deseas imprimir los rótulos A4 para los bultos ahora?", size=12, color=interfaz.texto),
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                ft.Button(f"Rótulos A4 ({bultos_val} b)", icon=ft.Icons.PRINT, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=imprimir_rotulos_directo),
                ft.Button(
                    "Rótulo Térmico Rollo",
                    icon=ft.Icons.LABEL,
                    bgcolor=ft.Colors.PURPLE_700,
                    color=ft.Colors.WHITE,
                    on_click=lambda _e, ped=pedido_reciente: (interfaz.page.pop_dialog(), interfaz.imprimir_rotulos_termicos_pedido(ped)),
                ),
                interfaz.boton_dialogo("Listo / Continuar", cerrar_exito),
            ],
        )
        interfaz.page.show_dialog(dialogo_exito)
    except Exception as ex_post:
        print(f"[AVISO] Error al mostrar diálogo posterior: {ex_post}")


def _mostrar_alerta_preventiva_quiebre(
    interfaz: Any,
    remito: str,
    cli: str,
    quiebres: list[Any],
    ejecutar_descuento_pedido: Callable[[], None],
) -> None:
    """Despliega confirmación previa cuando el comprobante dejará productos en quiebre."""
    filas_q = [
        ft.Text(
            f"• [{d.codigo}] {d.nombre_producto}: Stock actual {d.stock_original} → Descuenta {d.cantidad_descontada} → Quedará en {d.stock_nuevo} un.",
            size=11,
            color=ft.Colors.RED_400,
            weight=ft.FontWeight.W_500,
        )
        for d in quiebres
    ]

    async def autorizar_y_seguir(_e):
        interfaz.page.pop_dialog()
        await interfaz.ejecutar_tarea(f"Remito #{remito} ({cli})", ejecutar_descuento_pedido)

    dlg_prev = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.AMBER_400), ft.Text("Alerta Preventiva de Stock Insuficiente")]),
        content=ft.Container(
            width=480,
            content=ft.Column(
                [
                    ft.Text(
                        f"El comprobante '{remito}' contiene {len(quiebres)} artículo(s) que dejarán el inventario en quiebre o saldo negativo:",
                        size=12,
                        color=interfaz.texto,
                    ),
                    ft.Container(
                        content=ft.ListView(filas_q, height=85, spacing=3),
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.RED_50,
                        padding=8,
                        border_radius=6,
                    ),
                    ft.Text(
                        "¿Deseas autorizar el descuento de todos modos o apartar el comprobante para revisión?",
                        size=12,
                        color=interfaz.secundario,
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.Button("Autorizar y Descontar", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=autorizar_y_seguir),
            interfaz.boton_dialogo("Cancelar y Revisar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.reproducir_sonido("error")
    interfaz.page.show_dialog(dlg_prev)


def mostrar_dialogo_crear_pedido(interfaz: Any) -> None:
    """Abre el formulario para cargar un comprobante, parsearlo, verificar duplicados y armar el pedido."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("La carga de pedidos en tiempo real es una función exclusiva del rol operador.")
        return

    remito_factura_input = ft.TextField(
        label="Remito / Factura *",
        autofocus=not bool(getattr(interfaz, "es_pantalla_movil", False)),
        expand=True,
    )
    if hasattr(interfaz, "cerrar_drawer_si_movil"):
        interfaz.cerrar_drawer_si_movil()
    if hasattr(interfaz, "_asegurar_file_picker"):
        interfaz._asegurar_file_picker()

    clientes_lista_obj = interfaz.order_store.listar_clientes()
    clientes_actuales = [c.nombre for c in clientes_lista_obj]

    cliente_input = ft.TextField(
        label="Cliente (buscar o escribir nuevo) *",
        hint_text="Escribe para buscar o ingresar cliente nuevo",
        expand=True,
    )
    estado_cliente_txt = ft.Text("", size=11, color=ft.Colors.GREEN_400)
    sugerencias_lista = ft.ListView(spacing=2, height=110, visible=False)

    def seleccionar_cliente_sugerido(nombre: str) -> None:
        cliente_input.value = nombre
        sugerencias_lista.visible = False
        estado_cliente_txt.value = f"✓ Cliente existente seleccionado: {nombre}"
        estado_cliente_txt.color = ft.Colors.GREEN_400
        interfaz.page.update()

    def on_cliente_cambio(_e: ft.Event | None = None) -> None:
        q = (cliente_input.value or "").strip().lower()
        if not q:
            sugerencias_lista.visible = False
            estado_cliente_txt.value = ""
            interfaz.page.update()
            return

        coincidencias = [
            c
            for c in clientes_lista_obj
            if q in c.nombre.lower() or (c.codigo and q in c.codigo.lower()) or (c.direccion and q in c.direccion.lower())
        ]
        if coincidencias:
            sugerencias_lista.controls.clear()
            for c in coincidencias[:6]:
                sub_info = []
                if c.codigo:
                    sub_info.append(f"Cód: {c.codigo}")
                if c.direccion:
                    sub_info.append(f"📍 {c.direccion}")
                det_txt = " | ".join(sub_info)

                sugerencias_lista.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.PERSON, size=16, color=ft.Colors.BLUE_400),
                                ft.Column(
                                    [
                                        ft.Text(c.nombre, size=13, weight=ft.FontWeight.W_500),
                                        *([ft.Text(det_txt, size=10, color=interfaz.secundario)] if det_txt else []),
                                    ],
                                    spacing=1,
                                    expand=True,
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=4,
                        ink=True,
                        on_click=lambda _ev, nom=c.nombre: seleccionar_cliente_sugerido(nom),
                    )
                )
            sugerencias_lista.visible = True
            if any(c.nombre.lower() == q for c in coincidencias):
                estado_cliente_txt.value = "✓ Cliente registrado"
                estado_cliente_txt.color = ft.Colors.GREEN_400
            else:
                estado_cliente_txt.value = f"{len(coincidencias)} coincidencia(s). Si es nuevo, se creará al confirmar."
                estado_cliente_txt.color = ft.Colors.AMBER_400
        else:
            sugerencias_lista.visible = False
            estado_cliente_txt.value = "✨ Cliente nuevo: se dará de alta automáticamente al guardar."
            estado_cliente_txt.color = ft.Colors.AMBER_400
        interfaz.page.update()

    cliente_input.on_change = on_cliente_cambio

    numero_pedido_input = ft.TextField(
        label="Número de Pedido (opcional)",
        hint_text="ej: 3 (se reflejará en rótulos como 'Cliente Nro 3')",
        keyboard_type=ft.KeyboardType.NUMBER,
        expand=True,
    )
    bultos_input = ft.TextField(value="1", keyboard_type=ft.KeyboardType.NUMBER, text_align=ft.TextAlign.CENTER, width=70, dense=True)

    def ajustar_bultos(delta: int) -> None:
        try:
            val = int(bultos_input.value or "1")
        except ValueError:
            val = 1
        bultos_input.value = str(max(1, val + delta))
        interfaz.page.update()

    fila_bultos = ft.Container(
        content=ft.Row(
            [
                ft.Text("Cantidad de bultos *", size=13, weight=ft.FontWeight.W_500),
                ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.REMOVE_CIRCLE_OUTLINE, tooltip="Restar 1 bulto", icon_color=interfaz.secundario, on_click=lambda _e: ajustar_bultos(-1)),
                        bultos_input,
                        ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, tooltip="Sumar 1 bulto", icon_color=ROJO, on_click=lambda _e: ajustar_bultos(1)),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
    )

    selector_logistica = ft.Dropdown(
        label="Tipo de Logística *",
        hint_text="Seleccionar tipo de logística...",
        value=None,
        options=[ft.DropdownOption(key=op, text=op) for op in LOGISTICA_OPCIONES],
        expand=True,
    )

    def fecha_seleccionada(_e: ft.Event) -> None:
        val = date_picker.value
        if val:
            fecha_retiro_input.value = val.strftime("%d/%m/%Y") if hasattr(val, "strftime") else str(val)[:10]
        interfaz.page.update()

    date_picker = ft.DatePicker(on_change=fecha_seleccionada, help_text="Seleccionar fecha de retiro", confirm_text="Aceptar", cancel_text="Cancelar")

    def abrir_calendario(_e: ft.Event) -> None:
        interfaz.page.show_dialog(date_picker)

    def limpiar_fecha(_e: ft.Event) -> None:
        fecha_retiro_input.value = ""
        interfaz.page.update()

    fecha_retiro_input = ft.TextField(label="Fecha de retiro (opcional)", hint_text="Sin fecha asignada", read_only=True, expand=True, on_click=abrir_calendario)
    fila_fecha_retiro = ft.Row(
        [
            fecha_retiro_input,
            ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, tooltip="Seleccionar fecha de retiro en calendario", on_click=abrir_calendario),
            ft.IconButton(icon=ft.Icons.BACKSPACE_OUTLINED, tooltip="Quitar fecha de retiro", on_click=limpiar_fecha),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
    )

    armador_nom = interfaz.usuario_actual.nombre_identificador if interfaz.usuario_actual else "Operario"
    armador_input = ft.TextField(label="Armador responsable", value=armador_nom, read_only=True, disabled=True, expand=True)
    agregado_check = ft.Checkbox(label="Agregado", value=False)

    ruta_comprobante: list[Path] = []
    datos_doc_ref: list[Any] = []
    texto_archivo = ft.Text("Ningún comprobante seleccionado (.pdf, .xlsx/.xls o .docx)", size=12, color=interfaz.secundario)
    mensaje_error = ft.Text("", color=ft.Colors.RED_400, size=12)

    async def seleccionar_comprobante(_e: ft.Event) -> None:
        try:
            archivos = await interfaz.subir_archivos_desde_pc(
                carpeta_destino=application_root() / "data" / "pedidos_archivos",
                extensiones=["pdf", "xlsx", "xls", "docx"],
                titulo="Seleccionar Comprobante de Pedido (.pdf, .xlsx, .docx)",
            )
            if not archivos:
                return
            arch_candidato = archivos[0]
            if len(archivos) > 1:
                interfaz.notificar(
                    f"Se seleccionaron {len(archivos)} comprobantes. Se preparó '{arch_candidato.name}'; una vez confirmado este pedido podrás cargar los restantes."
                )
            hash_candidato = calcular_hash_archivo(arch_candidato)
            if hash_candidato:
                duplicado = interfaz.order_store.buscar_pedido_por_hash(hash_candidato)
                if duplicado:
                    ruta_comprobante.clear()
                    datos_doc_ref.clear()
                    texto_archivo.value = f"⛔ DUPLICADO: {arch_candidato.name}"
                    texto_archivo.color = ft.Colors.RED_400
                    mensaje_error.value = (
                        f"⛔ ATENCIÓN: El contenido de este archivo ya fue procesado el {duplicado.created_at[:16]} "
                        f"(Comprobante: {duplicado.nota_pedido}, Cliente: {duplicado.cliente})."
                    )
                    interfaz.page.update()
                    return

            ruta_comprobante.clear()
            ruta_comprobante.append(arch_candidato)
            texto_archivo.value = f"Comprobante: {arch_candidato.name}"
            texto_archivo.color = ft.Colors.GREEN_400
            mensaje_error.value = ""

            try:
                ext_c = arch_candidato.suffix.lower()
                if ext_c == ".pdf":
                    from ...parsers.remito_parser import parsear_remito
                    datos_doc = parsear_remito(arch_candidato)
                elif ext_c == ".docx":
                    from ...parsers.mercado_libre_parser import parsear_pedido_mercado_libre
                    sm = _resolver_sm_cls()(interfaz.menu.ruta_excel_base)
                    datos_doc = parsear_pedido_mercado_libre(arch_candidato, [(cod, val[1]) for cod, val in sm.catalogo.items()])
                else:
                    from ...parsers.canjes_parser import parsear_canje_excel
                    datos_doc = parsear_canje_excel(arch_candidato)

                if datos_doc:
                    datos_doc_ref.clear()
                    datos_doc_ref.append(datos_doc)
                    if getattr(datos_doc, "numero_remito", None):
                        remito_factura_input.value = str(datos_doc.numero_remito).strip()
                    if getattr(datos_doc, "cliente", None):
                        cliente_input.value = str(datos_doc.cliente).strip()
                        on_cliente_cambio(None)
                    if getattr(datos_doc, "fecha_despacho", None) and str(datos_doc.fecha_despacho).strip() and str(datos_doc.fecha_despacho).strip() != "Sin fecha":
                        fecha_retiro_input.value = str(datos_doc.fecha_despacho).strip()
                    elif getattr(datos_doc, "fecha", None) and str(datos_doc.fecha).strip() and str(datos_doc.fecha).strip() != "Sin fecha" and not fecha_retiro_input.value:
                        fecha_retiro_input.value = str(datos_doc.fecha).strip()

                    cli_cod = getattr(datos_doc, "codigo_cliente", "") or ""
                    cli_dir = getattr(datos_doc, "direccion", "") or ""
                    cli_nom = str(getattr(datos_doc, "cliente", "")).strip()
                    if cli_nom and (cli_cod or cli_dir):
                        try:
                            interfaz.order_store.obtener_o_crear_cliente(nombre=cli_nom, codigo=cli_cod, direccion=cli_dir, usuario=armador_nom)
                            clientes_lista_obj.clear()
                            clientes_lista_obj.extend(interfaz.order_store.listar_clientes())
                            clientes_actuales.clear()
                            clientes_actuales.extend([c.nombre for c in clientes_lista_obj])
                        except Exception:
                            pass
            except Exception:
                pass
            interfaz.page.update()
        except Exception as err:
            mensaje_error.value = f"Error al seleccionar comprobante: {err}"
            interfaz.page.update()

    boton_archivo = ft.Button(
        "Adjuntar Comprobante",
        icon=ft.Icons.ATTACH_FILE,
        bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100,
        color=interfaz.texto,
        on_click=seleccionar_comprobante,
    )
    contenedor_comprobante = ft.Container(
        bgcolor=ft.Colors.BLUE_GREY_900 if interfaz.modo_oscuro else ft.Colors.GREY_100,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=10,
        padding=12,
        content=ft.Column(
            [
                ft.Text("Comprobante adjunto (.pdf, .xlsx/.xls o .docx)", size=12, color=interfaz.secundario, weight=ft.FontWeight.W_500),
                ft.Row(
                    [boton_archivo, texto_archivo] if getattr(interfaz, "es_pantalla_movil", False) else [boton_archivo, ft.Container(content=texto_archivo, expand=True)],
                    wrap=bool(getattr(interfaz, "es_pantalla_movil", False)),
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            ],
            spacing=8,
        ),
    )

    async def confirmar_pedido(_e: ft.Event) -> None:
        remito = (remito_factura_input.value or "").strip()
        cli = (cliente_input.value or "").strip()
        num_ped = (numero_pedido_input.value or "").strip()
        log = selector_logistica.value or ""
        f_retiro = (fecha_retiro_input.value or "").strip()
        es_agregado = bool(agregado_check.value)
        try:
            bultos_val = max(1, int(bultos_input.value or "1"))
        except ValueError:
            bultos_val = 1

        if not remito:
            mensaje_error.value = "Debes ingresar el Remito / Factura."
            interfaz.page.update()
            return
        if interfaz.order_store.existe_nota_pedido(remito):
            mensaje_error.value = f"El comprobante '{remito}' ya fue registrado previamente."
            interfaz.page.update()
            return
        if not cli:
            mensaje_error.value = "Debes ingresar o seleccionar un Cliente."
            interfaz.page.update()
            return
        if not log:
            mensaje_error.value = "Debes seleccionar un tipo de logística."
            interfaz.page.update()
            return
        if not ruta_comprobante:
            mensaje_error.value = "Debes adjuntar el comprobante (.pdf o .xlsx/.xls)."
            interfaz.page.update()
            return

        try:
            cli_cod = getattr(datos_doc_ref[0], "codigo_cliente", "") if datos_doc_ref and datos_doc_ref[0] else ""
            cli_dir = getattr(datos_doc_ref[0], "direccion", "") if datos_doc_ref and datos_doc_ref[0] else ""
            interfaz.order_store.obtener_o_crear_cliente(nombre=cli, codigo=cli_cod, direccion=cli_dir, usuario=armador_nom)
        except Exception:
            pass

        archivo_path = ruta_comprobante[0]
        hash_comprobante = calcular_hash_archivo(archivo_path)
        if hash_comprobante:
            duplicado = interfaz.order_store.buscar_pedido_por_hash(hash_comprobante)
            if duplicado:
                mensaje_error.value = (
                    f"⛔ ALERTA DUPLICADO: Este archivo ya fue procesado el {duplicado.created_at[:16]} "
                    f"(Comprobante: {duplicado.nota_pedido}, Cliente: {duplicado.cliente})."
                )
                interfaz.page.update()
                return

        if getattr(confirmar_pedido, "_en_curso", False):
            return
        confirmar_pedido._en_curso = True

        interfaz.page.pop_dialog()
        tipo_archivo = "pdf" if archivo_path.suffix.lower() == ".pdf" else "excel"
        cache_simulacion: dict[str, Any] = {}

        def ejecutar_descuento_pedido() -> None:
            stock_mgr = cache_simulacion.get("stock_mgr")
            reporte = cache_simulacion.get("reporte")
            if stock_mgr is None or reporte is None:
                stock_mgr = _resolver_sm_cls()(ruta_excel_base=interfaz.menu.ruta_excel_base)
                agente = AgenteRemitosStock(stock_manager=stock_mgr)
                kw = {"rutas_pdf": [archivo_path]} if tipo_archivo == "pdf" else {"rutas_canjes": [archivo_path]}
                reporte = agente.ejecutar(**kw, carpeta_descuentos=interfaz.menu.carpeta_descuentos, simulacion=False, guardar_archivo=False)

            nombre_inf = Path(reporte.reporte_stock.archivo_guardado).name if reporte.reporte_stock.archivo_guardado else f"Pedido_{remito}"
            stock_mgr.actualizar_stock_base(
                descuentos=reporte.reporte_stock.descuentos_aplicados,
                sincronizar_excel=False,
                nombre_archivo=nombre_inf,
                usuario=armador_nom,
            )
            if hasattr(stock_mgr, "programar_sincronizacion_excel"):
                stock_mgr.programar_sincronizacion_excel()

            pdf_nom = Path(reporte.reporte_stock.archivo_pdf).name if reporte.reporte_stock.archivo_pdf else ""
            total_descontado = sum(d.cantidad_descontada for d in reporte.reporte_stock.descuentos_aplicados)
            resumen_items = f"{len(reporte.reporte_stock.descuentos_aplicados)} productos ({total_descontado} un.)"
            items_descontados = [(d.codigo, d.nombre_producto, d.cantidad_descontada) for d in reporte.reporte_stock.descuentos_aplicados]
            sin_coincidencia_doc = []
            if reporte and reporte.documentos_verificados:
                for doc in reporte.documentos_verificados:
                    sin_coincidencia_doc.extend(doc.descripciones_sin_coincidencia)

            tx_id = f"PED_{remito}_{hash_comprobante[:10] if hash_comprobante else ''}"
            if hasattr(interfaz.order_store, "registrar_transaccion_idempotente"):
                if not interfaz.order_store.registrar_transaccion_idempotente(tx_id, "CREAR_PEDIDO", remito):
                    print(f"[IDEMPOTENCIA] Transacción duplicada ignorada: {tx_id}")
                    return

            interfaz.order_store.registrar_pedido(
                nota_pedido=remito,
                numero_pedido=num_ped,
                cliente=cli,
                bultos=bultos_val,
                logistica=log,
                armador=armador_nom,
                tipo_archivo=tipo_archivo,
                nombre_archivo=archivo_path.name,
                agregado=es_agregado,
                articulos_descontados=total_descontado,
                resumen_items=resumen_items,
                fecha_retiro=f_retiro,
                archivo_descuento=pdf_nom,
                items=items_descontados,
                archivo_hash=hash_comprobante,
                items_sin_coincidencia=sin_coincidencia_doc,
            )
            interfaz.actualizar_listas()
            interfaz.sincronizar_sesiones(aviso_colaborativo=f"📦 {armador_nom} preparó el Pedido #{remito} ({cli})")
            interfaz.reproducir_sonido("exito")
            print(f"[PEDIDO REGISTRADO] Remito/Factura: {remito} | Pedido: {num_ped} | Cliente: {cli} | Descontados: {resumen_items} | Retiro: {f_retiro}")
            _mostrar_dialogo_exito_pedido(interfaz, remito, cli, bultos_val, log, resumen_items, reporte)

        try:
            sm_sim = _resolver_sm_cls()(ruta_excel_base=interfaz.menu.ruta_excel_base)
            ag_sim = AgenteRemitosStock(stock_manager=sm_sim)
            kw_sim = {"rutas_pdf": [archivo_path]} if tipo_archivo == "pdf" else {"rutas_canjes": [archivo_path]}
            rep_sim = ag_sim.ejecutar(**kw_sim, carpeta_descuentos=interfaz.menu.carpeta_descuentos, simulacion=True, guardar_archivo=False)
            cache_simulacion["stock_mgr"] = sm_sim
            cache_simulacion["reporte"] = rep_sim
            quiebres = [d for d in rep_sim.reporte_stock.descuentos_aplicados if d.stock_nuevo <= 0]
            if quiebres and interfaz.page:
                _mostrar_alerta_preventiva_quiebre(interfaz, remito, cli, quiebres, ejecutar_descuento_pedido)
                return
        except Exception as e_sim:
            print(f"[SIMULACION PREVENTIVA] Omitida: {e_sim}")

        await interfaz.ejecutar_tarea(f"Remito #{remito} ({cli})", ejecutar_descuento_pedido)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Cargar y Armar Pedido", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            width=interfaz.ancho_adaptable(500) if hasattr(interfaz, "ancho_adaptable") else 500,
            content=ft.Column(
                [
                    contenedor_comprobante,
                    remito_factura_input,
                    cliente_input,
                    sugerencias_lista,
                    estado_cliente_txt,
                    numero_pedido_input,
                    fila_bultos,
                    selector_logistica,
                    fila_fecha_retiro,
                    armador_input,
                    agregado_check,
                    mensaje_error,
                ],
                tight=True,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
        actions=[
            ft.Button("Confirmar y Descontar", icon=ft.Icons.CHECK_CIRCLE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=confirmar_pedido),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
