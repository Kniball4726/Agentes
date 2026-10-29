"""Diálogos modales para creación, edición, anulación y desarmado de pedidos en tiempo real."""
from pathlib import Path
import sys
from typing import Any, Callable
import flet as ft

from ...agent import AgenteRemitosStock
from ...orders_store import LOGISTICA_OPCIONES, Pedido, calcular_hash_archivo
from ...paths import application_root
from ...stock_manager import StockManager as _DefaultStockManager
from ..theme import ROJO


def _get_stock_manager_cls():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def mostrar_dialogo_crear_pedido(interfaz: Any) -> None:
    """Abre el formulario para cargar un comprobante, parsearlo, verificar duplicados y armar el pedido."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("La carga de pedidos en tiempo real es una función exclusiva del rol operador.")
        return

    remito_factura_input = ft.TextField(
        label="Remito / Factura *",
        autofocus=True,
        expand=True,
    )
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
            c for c in clientes_lista_obj
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
                                        *(
                                            [ft.Text(det_txt, size=10, color=interfaz.secundario)]
                                            if det_txt
                                            else []
                                        ),
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

    bultos_input = ft.TextField(
        value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        text_align=ft.TextAlign.CENTER,
        width=70,
        dense=True,
    )

    def ajustar_bultos(delta: int) -> None:
        try:
            val = int(bultos_input.value or "1")
        except ValueError:
            val = 1
        nuevo = max(1, val + delta)
        bultos_input.value = str(nuevo)
        interfaz.page.update()

    btn_restar_bultos = ft.IconButton(
        icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
        tooltip="Restar 1 bulto",
        icon_color=interfaz.secundario,
        on_click=lambda _e: ajustar_bultos(-1),
    )
    btn_sumar_bultos = ft.IconButton(
        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
        tooltip="Sumar 1 bulto",
        icon_color=ROJO,
        on_click=lambda _e: ajustar_bultos(1),
    )
    fila_bultos = ft.Container(
        content=ft.Row(
            [
                ft.Text("Cantidad de bultos *", size=13, weight=ft.FontWeight.W_500),
                ft.Row(
                    [btn_restar_bultos, bultos_input, btn_sumar_bultos],
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
            if hasattr(val, "strftime"):
                fecha_retiro_input.value = val.strftime("%d/%m/%Y")
            else:
                fecha_retiro_input.value = str(val)[:10]
        interfaz.page.update()

    date_picker = ft.DatePicker(
        on_change=fecha_seleccionada,
        help_text="Seleccionar fecha de retiro",
        confirm_text="Aceptar",
        cancel_text="Cancelar",
    )

    def abrir_calendario(_e: ft.Event) -> None:
        interfaz.page.show_dialog(date_picker)

    def limpiar_fecha(_e: ft.Event) -> None:
        fecha_retiro_input.value = ""
        interfaz.page.update()

    fecha_retiro_input = ft.TextField(
        label="Fecha de retiro (opcional)",
        hint_text="Sin fecha asignada",
        read_only=True,
        expand=True,
        on_click=abrir_calendario,
    )
    fila_fecha_retiro = ft.Row(
        [
            fecha_retiro_input,
            ft.IconButton(
                icon=ft.Icons.CALENDAR_MONTH,
                tooltip="Seleccionar fecha de retiro en calendario",
                on_click=abrir_calendario,
            ),
            ft.IconButton(
                icon=ft.Icons.BACKSPACE_OUTLINED,
                tooltip="Quitar fecha de retiro",
                on_click=limpiar_fecha,
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=4,
    )

    armador_nom = interfaz.usuario_actual.nombre_identificador if interfaz.usuario_actual else "Operario"
    armador_input = ft.TextField(
        label="Armador responsable",
        value=armador_nom,
        read_only=True,
        disabled=True,
        expand=True,
    )
    agregado_check = ft.Checkbox(
        label="Agregado",
        value=False,
    )

    ruta_comprobante: list[Path] = []
    datos_doc_ref: list[Any] = []
    texto_archivo = ft.Text(
        "Ningún comprobante seleccionado (.pdf o .xlsx/.xls)",
        size=12,
        color=interfaz.secundario,
    )

    async def seleccionar_comprobante(_e: ft.Event) -> None:
        try:
            archivos = await interfaz.subir_archivos_desde_pc(
                carpeta_destino=application_root() / "data" / "pedidos_archivos",
                extensiones=["pdf", "xlsx", "xls"],
                titulo="Seleccionar Comprobante de Pedido",
            )
            if archivos:
                arch_candidato = archivos[0]
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
                        from ...remito_parser import parsear_remito
                        datos_doc = parsear_remito(arch_candidato)
                    else:
                        from ...canjes_parser import parsear_canje_excel
                        datos_doc = parsear_canje_excel(arch_candidato)

                    if datos_doc:
                        datos_doc_ref.clear()
                        datos_doc_ref.append(datos_doc)
                        if getattr(datos_doc, "numero_remito", None):
                            remito_factura_input.value = str(datos_doc.numero_remito).strip()
                        if getattr(datos_doc, "cliente", None):
                            cliente_input.value = str(datos_doc.cliente).strip()
                            on_cliente_cambio(None)
                        # Auto-asignar fecha de retiro según la fecha de despacho
                        if getattr(datos_doc, "fecha_despacho", None) and str(datos_doc.fecha_despacho).strip() and str(datos_doc.fecha_despacho).strip() != "Sin fecha":
                            fecha_retiro_input.value = str(datos_doc.fecha_despacho).strip()
                        elif getattr(datos_doc, "fecha", None) and str(datos_doc.fecha).strip() and str(datos_doc.fecha).strip() != "Sin fecha" and not fecha_retiro_input.value:
                            fecha_retiro_input.value = str(datos_doc.fecha).strip()

                        # Enriquecer cliente con código y dirección automáticamente
                        cli_cod = getattr(datos_doc, "codigo_cliente", "") or ""
                        cli_dir = getattr(datos_doc, "direccion", "") or ""
                        cli_nom = str(getattr(datos_doc, "cliente", "")).strip()
                        if cli_nom and (cli_cod or cli_dir):
                            try:
                                interfaz.order_store.obtener_o_crear_cliente(
                                    nombre=cli_nom,
                                    codigo=cli_cod,
                                    direccion=cli_dir,
                                    usuario=armador_nom,
                                )
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
                ft.Text(
                    "Comprobante adjunto (.pdf o .xlsx/.xls)",
                    size=12,
                    color=interfaz.secundario,
                    weight=ft.FontWeight.W_500,
                ),
                ft.Row(
                    [boton_archivo, ft.Container(content=texto_archivo, expand=True)],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            ],
            spacing=8,
        ),
    )

    mensaje_error = ft.Text("", color=ft.Colors.RED_400, size=12)

    async def confirmar_pedido(_e: ft.Event) -> None:
        remito = (remito_factura_input.value or "").strip()
        cli = (cliente_input.value or "").strip()
        num_ped = (numero_pedido_input.value or "").strip()
        log = selector_logistica.value or ""
        f_retiro = (fecha_retiro_input.value or "").strip()
        es_agregado = bool(agregado_check.value)

        try:
            bultos_val = int(bultos_input.value or "1")
            if bultos_val < 1:
                bultos_val = 1
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

        if cli:
            try:
                cli_cod = getattr(datos_doc_ref[0], "codigo_cliente", "") if datos_doc_ref and datos_doc_ref[0] else ""
                cli_dir = getattr(datos_doc_ref[0], "direccion", "") if datos_doc_ref and datos_doc_ref[0] else ""
                interfaz.order_store.obtener_o_crear_cliente(
                    nombre=cli,
                    codigo=cli_cod,
                    direccion=cli_dir,
                    usuario=armador_nom,
                )
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

        interfaz.page.pop_dialog()
        ext = archivo_path.suffix.lower()
        tipo_archivo = "pdf" if ext == ".pdf" else "excel"

        def ejecutar_descuento_pedido() -> None:
            sm_cls = _get_stock_manager_cls()
            stock_mgr = sm_cls(ruta_excel_base=interfaz.menu.ruta_excel_base)
            agente = AgenteRemitosStock(stock_manager=stock_mgr)
            if tipo_archivo == "pdf":
                reporte = agente.ejecutar(
                    rutas_pdf=[archivo_path],
                    carpeta_descuentos=interfaz.menu.carpeta_descuentos,
                    simulacion=False,
                    guardar_archivo=False,
                )
            else:
                reporte = agente.ejecutar(
                    rutas_canjes=[archivo_path],
                    carpeta_descuentos=interfaz.menu.carpeta_descuentos,
                    simulacion=False,
                    guardar_archivo=False,
                )

            nombre_inf = Path(reporte.reporte_stock.archivo_guardado).name if reporte.reporte_stock.archivo_guardado else f"Pedido_{remito}"
            stock_mgr.actualizar_stock_base(
                descuentos=reporte.reporte_stock.descuentos_aplicados,
                sincronizar_excel=False,
                nombre_archivo=nombre_inf,
                usuario=armador_nom,
            )

            pdf_nom = Path(reporte.reporte_stock.archivo_pdf).name if reporte.reporte_stock.archivo_pdf else ""

            total_descontado = sum(
                d.cantidad_descontada for d in reporte.reporte_stock.descuentos_aplicados
            )
            resumen_items = f"{len(reporte.reporte_stock.descuentos_aplicados)} productos ({total_descontado} un.)"
            items_descontados = [
                (d.codigo, d.nombre_producto, d.cantidad_descontada)
                for d in reporte.reporte_stock.descuentos_aplicados
            ]
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
            )
            interfaz.actualizar_listas()
            print(f"[PEDIDO REGISTRADO] Remito/Factura: {remito} | Pedido: {num_ped} | Cliente: {cli} | Descontados: {resumen_items} | Retiro: {f_retiro}")

        await interfaz.ejecutar_tarea(f"Remito #{remito} ({cli})", ejecutar_descuento_pedido)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Cargar y Armar Pedido", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            width=500,
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
            ft.Button(
                "Confirmar y Descontar",
                icon=ft.Icons.CHECK_CIRCLE,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=confirmar_pedido,
            ),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_dialogo_confirmar_anulacion_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para anular un pedido registrado."""
    motivo_input = ft.TextField(
        label="Motivo de la anulación (opcional)",
        hint_text="ej: Cancelado por el cliente, duplicado, error en carga",
        dense=True,
        autofocus=True,
    )

    def ejecutar_anulacion(_e: ft.Event) -> None:
        interfaz.page.pop_dialog()
        try:
            interfaz.order_store.anular_pedido(
                pedido_id=pedido.id,
                motivo=motivo_input.value or "",
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema",
            )
            interfaz.notificar(f"Pedido {pedido.nota_pedido} anulado correctamente.")
            if al_final:
                al_final()
        except Exception as err:
            interfaz.notificar(f"Error al anular pedido: {err}")

    dialogo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ROJO), ft.Text("Confirmar Anulación de Pedido")]),
        content=ft.Container(
            width=420,
            content=ft.Column(
                [
                    ft.Text(f"¿Estás seguro de anular el pedido '{pedido.nota_pedido}' del cliente '{pedido.cliente}'?"),
                    *(
                        [ft.Text(f"⚠️ Atención: Este pedido ya formó parte del Cierre #{pedido.cierre_id} (el stock ya fue descontado en el Excel).", size=11, color=ft.Colors.AMBER_800, weight=ft.FontWeight.W_500)]
                        if getattr(pedido, "cierre_id", None)
                        else [ft.Text("Al estar pendiente de cierre, sus artículos no se descontarán en el Excel.", size=11, color=ft.Colors.GREEN_700)]
                    ),
                    ft.Text("Esta acción quedará registrada en el log de auditoría del sistema.", size=11, color=interfaz.secundario),
                    ft.Divider(height=10),
                    motivo_input,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.Button("Anular Pedido", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=ejecutar_anulacion),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_dialogo_editar_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para modificar los datos de un pedido existente."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador", "master"):
        interfaz.notificar("No tienes permisos suficientes para modificar pedidos.")
        return

    cliente_input = ft.TextField(
        label="Cliente *",
        value=pedido.cliente,
        dense=True,
        autofocus=True,
    )
    numero_pedido_input = ft.TextField(
        label="Número de Pedido (opcional)",
        value=str(getattr(pedido, "numero_pedido", "") or ""),
        hint_text="ej: 3",
        dense=True,
    )
    bultos_input = ft.TextField(
        label="Cantidad de Bultos *",
        value=str(pedido.bultos),
        keyboard_type=ft.KeyboardType.NUMBER,
        dense=True,
    )
    logistica_dropdown = ft.Dropdown(
        label="Logística *",
        value=pedido.logistica if pedido.logistica in LOGISTICA_OPCIONES else LOGISTICA_OPCIONES[0],
        options=[ft.DropdownOption(key=op, text=op) for op in LOGISTICA_OPCIONES],
        dense=True,
    )
    fecha_retiro_input = ft.TextField(
        label="Fecha de Retiro / Despacho (opcional)",
        value=str(getattr(pedido, "fecha_retiro", "") or ""),
        hint_text="ej: 26/10/2026",
        dense=True,
    )
    error_msg = ft.Text("", color=ft.Colors.RED_400, size=11, visible=False)

    def guardar_cambios(_e: ft.Event) -> None:
        c_val = (cliente_input.value or "").strip()
        if not c_val:
            error_msg.value = "El cliente no puede estar vacío."
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()
            return

        try:
            b_val = int((bultos_input.value or "1").strip())
            if b_val < 1:
                raise ValueError
        except Exception:
            error_msg.value = "La cantidad de bultos debe ser un número entero mayor o igual a 1."
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()
            return

        log_val = logistica_dropdown.value or LOGISTICA_OPCIONES[0]
        num_val = (numero_pedido_input.value or "").strip()
        ret_val = (fecha_retiro_input.value or "").strip()

        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema"
        try:
            interfaz.order_store.actualizar_datos_pedido(
                pedido_id=pedido.id,
                cliente=c_val,
                numero_pedido=num_val,
                bultos=b_val,
                logistica=log_val,
                fecha_retiro=ret_val,
                usuario=usr,
            )
            interfaz.page.pop_dialog()
            interfaz.notificar(f"Pedido #{pedido.nota_pedido} actualizado correctamente.")
            if al_final:
                al_final()
            interfaz.sincronizar_sesiones()
        except Exception as err:
            error_msg.value = f"Error al actualizar: {err}"
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.EDIT_NOTE, color=ft.Colors.BLUE_600),
                ft.Text(f"Modificar Pedido #{pedido.nota_pedido}"),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=420,
            content=ft.Column(
                [
                    ft.Text(
                        f"Remito: {pedido.nota_pedido} · Archivo: {pedido.nombre_archivo}",
                        size=11,
                        color=interfaz.secundario,
                    ),
                    cliente_input,
                    numero_pedido_input,
                    bultos_input,
                    logistica_dropdown,
                    fecha_retiro_input,
                    error_msg,
                ],
                tight=True,
                spacing=10,
            ),
        ),
        actions=[
            ft.Button("Guardar Cambios", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=guardar_cambios),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_dialogo_confirmar_desarmar_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para desarmar un pedido y reincorporar sus artículos al inventario."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador", "master"):
        interfaz.notificar("No tienes permisos suficientes para desarmar pedidos.")
        return

    if pedido.estado == "anulado":
        interfaz.notificar(f"El pedido #{pedido.nota_pedido} ya se encuentra anulado.")
        return

    items = interfaz.order_store.obtener_items_pedido(pedido.id)
    total_unidades = sum(cant for _, _, cant in items) if items else pedido.articulos_descontados

    lista_items_controls = []
    if items:
        for cod, desc, cant in items:
            lista_items_controls.append(
                ft.Row(
                    [
                        ft.Text(f"• {cod}", weight=ft.FontWeight.BOLD, size=11, color=interfaz.texto),
                        ft.Text(f"{desc}", size=11, color=interfaz.secundario, expand=True, no_wrap=True),
                        ft.Text(f"+{cant} u.", weight=ft.FontWeight.BOLD, size=11, color=ft.Colors.GREEN_400),
                    ],
                    spacing=6,
                )
            )
    else:
        lista_items_controls.append(
            ft.Text(
                f"Detalle: {pedido.resumen_items or f'{pedido.articulos_descontados} artículos'}",
                size=11,
                color=interfaz.secundario,
            )
        )

    motivo_input = ft.TextField(
        label="Motivo del desarmado (opcional)",
        hint_text="ej: Pedido cancelado por el cliente / Reincorporación de mercadería a depósito",
        dense=True,
        autofocus=True,
    )
    error_msg = ft.Text("", color=ft.Colors.RED_400, size=11, visible=False)

    def ejecutar_desarmado(_e: ft.Event) -> None:
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema"
        motivo_txt = (motivo_input.value or "").strip()
        try:
            if items:
                devoluciones: dict[str, int] = {}
                for cod, _desc, cant in items:
                    if cant > 0:
                        devoluciones[cod] = devoluciones.get(cod, 0) + cant
                if devoluciones:
                    interfaz.menu.stock_manager.registrar_ingreso_fabrica(devoluciones, sobrescribir=False)
                    try:
                        interfaz.menu.stock_manager.registrar_movimientos_historial(devoluciones, tipo="ingreso_fabrica")
                    except Exception:
                        pass

            motivo_anulacion = f"Desarmado de pedido y devolución de stock. {motivo_txt}".strip()
            interfaz.order_store.anular_pedido(
                pedido_id=pedido.id,
                motivo=motivo_anulacion,
                usuario=usr,
            )
            interfaz.order_store.registrar_auditoria(
                usuario=usr,
                accion="DESARMAR_PEDIDO",
                detalle=f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) desarmado. Stock restituido: {total_unidades} unidades. Motivo: {motivo_txt or 'Sin especificar'}",
            )

            interfaz.page.pop_dialog()
            interfaz.notificar(f"Pedido #{pedido.nota_pedido} desarmado con éxito. Se reincorporaron {total_unidades} unidades al stock.")
            if al_final:
                al_final()
            interfaz.sincronizar_sesiones()
        except Exception as err:
            error_msg.value = f"Error al desarmar pedido: {err}"
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.REMOVE_SHOPPING_CART, color=ROJO),
                ft.Text(f"Desarmar Pedido #{pedido.nota_pedido}"),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=460,
            content=ft.Column(
                [
                    ft.Text(
                        f"¿Confirmas el desarmado del pedido de '{pedido.cliente}'? "
                        f"El pedido se anulará y los productos se sumarán de vuelta al stock disponible en el sistema y en el Excel.",
                        size=12,
                    ),
                    *(
                        [ft.Text(f"⚠️ Atención: Este pedido ya formó parte del Cierre #{pedido.cierre_id}. Al desarmarlo, las unidades se reincorporarán al stock actual.", size=11, color=ft.Colors.AMBER_800, weight=ft.FontWeight.W_500)]
                        if getattr(pedido, "cierre_id", None)
                        else []
                    ),
                    ft.Divider(height=10),
                    ft.Text(
                        f"Productos a devolver al inventario ({total_unidades} unidades en total):",
                        weight=ft.FontWeight.BOLD,
                        size=11,
                        color=interfaz.texto,
                    ),
                    ft.Container(
                        content=ft.ListView(lista_items_controls, spacing=4),
                        height=140,
                        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_100,
                        border=ft.Border.all(1, interfaz.borde),
                        border_radius=6,
                    ),
                    motivo_input,
                    error_msg,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.Button("Desarmar y Devolver Stock", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=ejecutar_desarmado),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
