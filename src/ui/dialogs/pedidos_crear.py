"""Diálogo de creación y armado de pedidos en tiempo real con detección preventiva de quiebre."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft

from ...agent import AgenteRemitosStock
from ...orders import LOGISTICA_OPCIONES, calcular_hash_archivo
from ...paths import application_root
from ..theme import ROJO
from .pedidos_crear_modales import (
    _mostrar_alerta_preventiva_quiebre,
    _mostrar_dialogo_exito_pedido,
    _resolver_sm_cls,
    ejecutar_descuento_y_registro_pedido,
    parsear_comprobante_pedido,
)


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
                datos_doc = parsear_comprobante_pedido(arch_candidato, interfaz.menu.ruta_excel_base)

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
            ejecutar_descuento_y_registro_pedido(
                interfaz=interfaz,
                remito=remito,
                num_ped=num_ped,
                cli=cli,
                bultos_val=bultos_val,
                log=log,
                f_retiro=f_retiro,
                armador_nom=armador_nom,
                es_agregado=es_agregado,
                tipo_archivo=tipo_archivo,
                archivo_path=archivo_path,
                hash_comprobante=hash_comprobante,
                cache_simulacion=cache_simulacion,
            )

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
