"""Diálogo modular de creación y armado de pedidos en tiempo real con detección preventiva de quiebre."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft

from ...agent import AgenteRemitosStock
from ...core.stock_order_tx import detectar_conflictos_stock_y_reservas
from ...orders import LOGISTICA_OPCIONES, calcular_hash_archivo
from ..theme import ROJO
from .pedidos_crear_componentes import (
    SelectorClientePedido,
    SelectorComprobantePedido,
    SelectorFechaRetiroPedido,
)
from .pedidos_crear_modales import (
    _mostrar_alerta_preventiva_quiebre,
    _resolver_sm_cls,
    ejecutar_descuento_y_registro_pedido,
    ejecutar_reserva_y_registro_pedido,
)


def mostrar_dialogo_crear_pedido(interfaz: Any) -> None:
    """Abre el formulario para cargar un comprobante, parsearlo, verificar duplicados y armar el pedido."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("La carga de pedidos en tiempo real es una función exclusiva del rol operador.")
        return

    if hasattr(interfaz, "cerrar_drawer_si_movil"):
        interfaz.cerrar_drawer_si_movil()
    if hasattr(interfaz, "_asegurar_file_picker"):
        interfaz._asegurar_file_picker()

    remito_factura_input = ft.TextField(
        label="Remito / Factura *",
        autofocus=not bool(getattr(interfaz, "es_pantalla_movil", False)),
        expand=True,
    )

    selector_cliente = SelectorClientePedido(interfaz)
    selector_fecha = SelectorFechaRetiroPedido(interfaz)

    mensaje_error = ft.Text("", color=ft.Colors.RED_400, size=12)

    def on_error(err_msg: str) -> None:
        mensaje_error.value = err_msg
        interfaz.page.update()

    def on_datos_extraidos(datos_doc: Any, _arch_candidato: Path, _hash_candidato: str) -> None:
        if getattr(datos_doc, "numero_remito", None):
            remito_factura_input.value = str(datos_doc.numero_remito).strip()
        if getattr(datos_doc, "cliente", None):
            selector_cliente.value = str(datos_doc.cliente).strip()

        fecha_val = getattr(datos_doc, "fecha_despacho", None) or getattr(datos_doc, "fecha", None)
        if fecha_val and str(fecha_val).strip() and str(fecha_val).strip() != "Sin fecha":
            selector_fecha.value = str(fecha_val).strip()

        cli_cod = getattr(datos_doc, "codigo_cliente", "") or ""
        cli_dir = getattr(datos_doc, "direccion", "") or ""
        cli_nom = str(getattr(datos_doc, "cliente", "")).strip()
        if cli_nom and (cli_cod or cli_dir):
            try:
                armador_nom = interfaz.usuario_actual.nombre_identificador if interfaz.usuario_actual else "Operario"
                interfaz.order_store.obtener_o_crear_cliente(nombre=cli_nom, codigo=cli_cod, direccion=cli_dir, usuario=armador_nom)
                selector_cliente.recargar_clientes()
            except Exception:
                pass

    selector_comprobante = SelectorComprobantePedido(
        interfaz,
        on_datos_extraidos=on_datos_extraidos,
        on_error=on_error,
    )

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

    armador_nom = interfaz.usuario_actual.nombre_identificador if interfaz.usuario_actual else "Operario"
    armador_input = ft.TextField(label="Armador responsable", value=armador_nom, read_only=True, disabled=True, expand=True)
    agregado_check = ft.Checkbox(label="Agregado", value=False)
    solo_reservar_check = ft.Checkbox(
        label="Solo reservar stock (en preparación, sin descontar todavía)",
        value=False,
    )

    async def confirmar_pedido(_e: ft.Event) -> None:
        remito = (remito_factura_input.value or "").strip()
        cli = selector_cliente.value
        num_ped = (numero_pedido_input.value or "").strip()
        log = selector_logistica.value or ""
        f_retiro = selector_fecha.value
        es_agregado = bool(agregado_check.value)
        solo_reservar = bool(solo_reservar_check.value)

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
        if not selector_comprobante.ruta_comprobante:
            mensaje_error.value = "Debes adjuntar el comprobante (.pdf o .xlsx/.xls)."
            interfaz.page.update()
            return

        try:
            datos_doc_ref = selector_comprobante.datos_doc_ref
            cli_cod = getattr(datos_doc_ref[0], "codigo_cliente", "") if datos_doc_ref and datos_doc_ref[0] else ""
            cli_dir = getattr(datos_doc_ref[0], "direccion", "") if datos_doc_ref and datos_doc_ref[0] else ""
            interfaz.order_store.obtener_o_crear_cliente(nombre=cli, codigo=cli_cod, direccion=cli_dir, usuario=armador_nom)
        except Exception:
            pass

        archivo_path = selector_comprobante.ruta_comprobante[0]
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

        def ejecutar_operacion_pedido() -> None:
            fn = (
                ejecutar_reserva_y_registro_pedido
                if solo_reservar
                else ejecutar_descuento_y_registro_pedido
            )
            fn(
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
            sm_sim = _resolver_sm_cls(interfaz)(ruta_excel_base=interfaz.menu.ruta_excel_base)
            ag_sim = AgenteRemitosStock(stock_manager=sm_sim)
            kw_sim = {"rutas_pdf": [archivo_path]} if tipo_archivo == "pdf" else {"rutas_canjes": [archivo_path]}
            rep_sim = ag_sim.ejecutar(**kw_sim, carpeta_descuentos=interfaz.menu.carpeta_descuentos, simulacion=True, guardar_archivo=False)
            cache_simulacion["stock_mgr"] = sm_sim
            cache_simulacion["reporte"] = rep_sim
            p_store_sim = getattr(sm_sim, "product_store", None) or getattr(interfaz, "product_store", None)
            conflictos = detectar_conflictos_stock_y_reservas(
                rep_sim.reporte_stock.descuentos_aplicados,
                p_store_sim,
            )
            if conflictos and interfaz.page:
                _mostrar_alerta_preventiva_quiebre(
                    interfaz,
                    remito,
                    cli,
                    conflictos,
                    ejecutar_operacion_pedido,
                    solo_reservar=solo_reservar,
                )
                return
        except Exception as e_sim:
            print(f"[SIMULACION PREVENTIVA] Omitida: {e_sim}")

        await interfaz.ejecutar_tarea(f"Remito #{remito} ({cli})", ejecutar_operacion_pedido)

    btn_confirmar = ft.Button(
        "Confirmar y Descontar",
        icon=ft.Icons.CHECK_CIRCLE,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        on_click=confirmar_pedido,
    )

    def _al_cambiar_solo_reservar(_e: Any) -> None:
        btn_confirmar.content = (
            "Confirmar y Reservar" if solo_reservar_check.value else "Confirmar y Descontar"
        )
        if getattr(interfaz, "page", None):
            interfaz.page.update()

    solo_reservar_check.on_change = _al_cambiar_solo_reservar

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Cargar y Armar Pedido", weight=ft.FontWeight.BOLD),
        content=ft.Container(
            width=interfaz.ancho_adaptable(500) if hasattr(interfaz, "ancho_adaptable") else 500,
            content=ft.Column(
                [
                    selector_comprobante.contenedor,
                    remito_factura_input,
                    selector_cliente.input_cliente,
                    selector_cliente.sugerencias_lista,
                    selector_cliente.estado_cliente_txt,
                    numero_pedido_input,
                    fila_bultos,
                    selector_logistica,
                    selector_fecha.fila_control,
                    armador_input,
                    agregado_check,
                    solo_reservar_check,
                    mensaje_error,
                ],
                tight=True,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
        actions=[
            btn_confirmar,
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
