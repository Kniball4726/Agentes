"""Diálogos de edición, anulación, desarmado y restitución de stock de pedidos."""

from __future__ import annotations

from datetime import datetime
import sys
from typing import Any, Callable

import flet as ft

from ...inventory import StockManager as _DefaultStockManager
from ...orders import LOGISTICA_OPCIONES, Pedido
from ..theme import ROJO


def _resolver_sm_cls():
    mod_ped = sys.modules.get("src.ui.dialogs.dlg_pedidos")
    if mod_ped is not None and hasattr(mod_ped, "_get_stock_manager_cls"):
        return mod_ped._get_stock_manager_cls()
    mod_gui = sys.modules.get("src.flet_gui")
    if mod_gui is not None and hasattr(mod_gui, "StockManager"):
        return getattr(mod_gui, "StockManager")
    return _DefaultStockManager


def _restituir_stock_pedido(interfaz: Any, pedido: Pedido) -> int:
    """Reincorpora los productos y cantidades de un pedido al stock de SQLite y Productos.xlsx en tiempo real."""
    items = interfaz.order_store.obtener_items_pedido(pedido.id)
    if not items:
        return 0
    devoluciones: dict[str, int] = {}
    for cod, _desc, cant in items:
        if cant > 0:
            devoluciones[cod] = devoluciones.get(cod, 0) + cant
    if devoluciones:
        sm_cls = _resolver_sm_cls()
        ruta_base_datos = getattr(interfaz, "ruta_base_datos", None) or getattr(interfaz.menu, "ruta_base_datos", None)
        kwargs: dict[str, Any] = {"ruta_excel_base": interfaz.menu.ruta_excel_base}
        if ruta_base_datos:
            kwargs["ruta_base_datos"] = ruta_base_datos
        sm = sm_cls(**kwargs)
        sm.registrar_ingreso_fabrica(devoluciones, sobrescribir=False)
        try:
            sm.registrar_movimientos_historial(devoluciones, tipo="ingreso_fabrica")
        except Exception:
            pass
    return sum(devoluciones.values())


def mostrar_dialogo_confirmar_anulacion_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para anular un pedido registrado restituyendo su stock en tiempo real."""
    motivo_input = ft.TextField(
        label="Motivo de la anulación (opcional)",
        hint_text="ej: Cancelado por el cliente, duplicado, error en carga",
        dense=True,
        autofocus=not bool(getattr(interfaz, "es_pantalla_movil", False)),
    )

    def ejecutar_anulacion(_e: ft.Event) -> None:
        interfaz.page.pop_dialog()
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema"
        motivo_txt = (motivo_input.value or "").strip()
        try:
            unidades_restituidas = _restituir_stock_pedido(interfaz, pedido) if pedido.estado != "anulado" else 0
            interfaz.order_store.anular_pedido(
                pedido_id=pedido.id,
                motivo=f"Anulación de pedido: {motivo_txt}".strip() if motivo_txt else "Anulación de pedido",
                usuario=usr,
            )
            interfaz.order_store.registrar_auditoria(
                usuario=usr,
                accion="ANULAR_PEDIDO",
                detalle=f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) anulado. Stock devuelto: {unidades_restituidas} un. Motivo: {motivo_txt or 'Sin motivo'}",
            )
            msg = f"Pedido {pedido.nota_pedido} anulado correctamente."
            if unidades_restituidas > 0:
                msg += f" Se reincorporaron {unidades_restituidas} unidades al inventario y al Excel."
            interfaz.notificar(msg)
            if al_final:
                al_final()
            interfaz.actualizar_listas()
            interfaz.sincronizar_sesiones(aviso_colaborativo=f"⚠️ {usr} anuló el Pedido #{pedido.nota_pedido} ({pedido.cliente})")
            interfaz.sincronizar_sesiones()
        except Exception as err:
            interfaz.notificar(f"Error al anular pedido: {err}")

    dialogo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ROJO), ft.Text("Confirmar Anulación de Pedido")]),
        content=ft.Container(
            width=420,
            content=ft.Column(
                [
                    ft.Text(f"¿Estás seguro de anular el pedido '{pedido.nota_pedido}' del cliente '{pedido.cliente}'?"),
                    ft.Text(
                        "⚠️ Al anular este pedido, todas las unidades descontadas se devolverán automáticamente al stock disponible y a la planilla Productos.xlsx en tiempo real.",
                        size=11,
                        color=ft.Colors.AMBER_800,
                        weight=ft.FontWeight.W_500,
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
            ft.Button("Anular y Devolver Stock", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=ejecutar_anulacion),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def _mostrar_dialogo_bloqueo_pedido(
    interfaz: Any,
    pedido: Pedido,
    usr_bloqueo: str,
    f_bloqueo: str,
    al_final: Callable[[], None] | None,
) -> None:
    tiempo_str = "recientemente"
    try:
        t_diff = int((datetime.now() - datetime.fromisoformat(f_bloqueo)).total_seconds() // 60)
        tiempo_str = f"hace {t_diff} min" if t_diff > 0 else "hace menos de 1 minuto"
    except Exception:
        pass

    def forzar_desbloqueo_y_abrir(_e):
        interfaz.page.pop_dialog()
        interfaz.order_store.liberar_bloqueo_pedido(pedido.id)
        mostrar_dialogo_editar_pedido(interfaz, pedido, al_final)

    def abrir_modo_lectura(_e):
        interfaz.page.pop_dialog()
        if hasattr(interfaz, "mostrar_detalle_pedido_modal"):
            interfaz.mostrar_detalle_pedido_modal(pedido)

    dialogo_bloqueo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.LOCK, color=ft.Colors.AMBER_400), ft.Text("Pedido en Edición Simultánea")]),
        content=ft.Container(
            width=450,
            content=ft.Column(
                [
                    ft.Text(
                        f"⚠️ El Pedido #{pedido.nota_pedido} ({pedido.cliente}) está siendo modificado actualmente por @{usr_bloqueo} ({tiempo_str}).",
                        size=13,
                    ),
                    ft.Text(
                        "Para evitar colisión de datos, no se permiten modificaciones simultáneas sobre el mismo pedido.",
                        size=12,
                        color=interfaz.secundario,
                    ),
                ],
                tight=True,
                spacing=6,
            ),
        ),
        actions=[
            ft.Button("Ver en Modo Lectura", icon=ft.Icons.VISIBILITY, on_click=abrir_modo_lectura),
            ft.Button(
                "Forzar Desbloqueo",
                icon=ft.Icons.LOCK_OPEN,
                color=ft.Colors.RED_400,
                tooltip="Usar si el compañero cerró la pestaña o se ausentó",
                on_click=forzar_desbloqueo_y_abrir,
            ),
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo_bloqueo)


def mostrar_dialogo_editar_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para modificar los datos de un pedido existente (exclusivo Operador)."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("La modificación de pedidos es una función exclusiva del rol Operador de depósito.")
        return

    usr_actual = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
    if hasattr(interfaz, "order_store") and interfaz.order_store:
        try:
            res_lock = interfaz.order_store.adquirir_bloqueo_pedido(pedido.id, usr_actual)
            if isinstance(res_lock, tuple) and len(res_lock) >= 3:
                ok_lock, usr_bloqueo, f_bloqueo = res_lock[0], res_lock[1], res_lock[2]
            else:
                ok_lock, usr_bloqueo, f_bloqueo = bool(res_lock), usr_actual, ""
        except Exception:
            ok_lock, usr_bloqueo, f_bloqueo = True, usr_actual, ""
        if not ok_lock:
            _mostrar_dialogo_bloqueo_pedido(interfaz, pedido, usr_bloqueo, f_bloqueo, al_final)
            return

    cliente_input = ft.TextField(label="Cliente *", value=pedido.cliente, dense=True, autofocus=not bool(getattr(interfaz, "es_pantalla_movil", False)))
    numero_pedido_input = ft.TextField(label="Número de Pedido (opcional)", value=str(getattr(pedido, "numero_pedido", "") or ""), hint_text="ej: 3", dense=True)
    bultos_input = ft.TextField(label="Cantidad de Bultos *", value=str(pedido.bultos), keyboard_type=ft.KeyboardType.NUMBER, dense=True)
    logistica_dropdown = ft.Dropdown(
        label="Logística *",
        value=pedido.logistica if pedido.logistica in LOGISTICA_OPCIONES else LOGISTICA_OPCIONES[0],
        options=[ft.DropdownOption(key=op, text=op) for op in LOGISTICA_OPCIONES],
        dense=True,
    )
    fecha_retiro_input = ft.TextField(label="Fecha de Retiro / Despacho (opcional)", value=str(getattr(pedido, "fecha_retiro", "") or ""), hint_text="ej: 26/10/2026", dense=True)
    numero_guia_input = ft.TextField(label="N° de Guía / Tracking del Transporte (opcional)", value=str(getattr(pedido, "numero_guia", "") or ""), hint_text="ej: TRK-987654 o 00012345678", dense=True)
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

        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema"
        try:
            interfaz.order_store.actualizar_datos_pedido(
                pedido_id=pedido.id,
                cliente=c_val,
                numero_pedido=(numero_pedido_input.value or "").strip(),
                bultos=b_val,
                logistica=logistica_dropdown.value or LOGISTICA_OPCIONES[0],
                fecha_retiro=(fecha_retiro_input.value or "").strip(),
                usuario=usr,
                numero_guia=(numero_guia_input.value or "").strip(),
            )
            interfaz.page.pop_dialog()
            if hasattr(interfaz, "order_store") and interfaz.order_store:
                try:
                    interfaz.order_store.liberar_bloqueo_pedido(pedido.id, usr)
                except Exception:
                    pass
            interfaz.notificar(f"Pedido #{pedido.nota_pedido} actualizado correctamente.")
            if al_final:
                al_final()
            interfaz.sincronizar_sesiones(aviso_colaborativo=f"✏️ {usr} actualizó datos del Pedido #{pedido.nota_pedido} ({c_val})")
        except Exception as err:
            error_msg.value = f"Error al actualizar: {err}"
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()

    def al_cerrar_dialogo(_e=None):
        if hasattr(interfaz, "order_store") and interfaz.order_store:
            try:
                interfaz.order_store.liberar_bloqueo_pedido(getattr(pedido, "id", 0), usr_actual)
            except Exception:
                pass

    dialogo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.EDIT_NOTE, color=ft.Colors.BLUE_600), ft.Text(f"Modificar Pedido #{pedido.nota_pedido}")], spacing=8),
        content=ft.Container(
            width=420,
            content=ft.Column(
                [
                    ft.Text(f"Remito: {pedido.nota_pedido} · Archivo: {pedido.nombre_archivo}", size=11, color=interfaz.secundario),
                    cliente_input,
                    numero_pedido_input,
                    bultos_input,
                    logistica_dropdown,
                    fecha_retiro_input,
                    numero_guia_input,
                    error_msg,
                ],
                tight=True,
                spacing=10,
            ),
        ),
        actions=[
            ft.Button("Guardar Cambios", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=guardar_cambios),
            interfaz.boton_dialogo("Cancelar", lambda _e: (al_cerrar_dialogo(), interfaz.page.pop_dialog())),
        ],
        on_dismiss=al_cerrar_dialogo,
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_dialogo_confirmar_desarmar_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para desarmar un pedido y reincorporar sus artículos al inventario."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador"):
        interfaz.notificar("No tienes permisos suficientes para desarmar pedidos.")
        return
    if pedido.estado == "anulado":
        interfaz.notificar(f"El pedido #{pedido.nota_pedido} ya se encuentra anulado.")
        return

    items = interfaz.order_store.obtener_items_pedido(pedido.id)
    total_unidades = sum(cant for _, _, cant in items) if items else pedido.articulos_descontados

    if items:
        lista_items_controls = [
            ft.Row(
                [
                    ft.Text(f"• {cod}", weight=ft.FontWeight.BOLD, size=11, color=interfaz.texto),
                    ft.Text(f"{desc}", size=11, color=interfaz.secundario, expand=True, no_wrap=True),
                    ft.Text(f"+{cant} u.", weight=ft.FontWeight.BOLD, size=11, color=ft.Colors.GREEN_400),
                ],
                spacing=6,
            )
            for cod, desc, cant in items
        ]
    else:
        lista_items_controls = [
            ft.Text(f"Detalle: {pedido.resumen_items or f'{pedido.articulos_descontados} artículos'}", size=11, color=interfaz.secundario)
        ]

    motivo_input = ft.TextField(
        label="Motivo del desarmado (opcional)",
        hint_text="ej: Pedido cancelado por el cliente / Reincorporación de mercadería a depósito",
        dense=True,
        autofocus=not bool(getattr(interfaz, "es_pantalla_movil", False)),
    )
    error_msg = ft.Text("", color=ft.Colors.RED_400, size=11, visible=False)

    def ejecutar_desarmado(_e: ft.Event) -> None:
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema"
        motivo_txt = (motivo_input.value or "").strip()
        try:
            _restituir_stock_pedido(interfaz, pedido)
            interfaz.order_store.anular_pedido(
                pedido_id=pedido.id,
                motivo=f"Desarmado de pedido y devolución de stock. {motivo_txt}".strip(),
                usuario=usr,
            )
            interfaz.order_store.registrar_auditoria(
                usuario=usr,
                accion="DESARMAR_PEDIDO",
                detalle=f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) desarmado. Stock restituido: {total_unidades} unidades. Motivo: {motivo_txt or 'Sin especificar'}",
            )
            interfaz.page.pop_dialog()
            interfaz.notificar(f"Pedido #{pedido.nota_pedido} desarmado con éxito. Se reincorporaron {total_unidades} unidades al stock.")
            interfaz.sincronizar_sesiones(aviso_colaborativo=f"⚠️ {usr} desarmó el Pedido #{pedido.nota_pedido} ({pedido.cliente})")
            if al_final:
                al_final()
            interfaz.sincronizar_sesiones()
        except Exception as err:
            error_msg.value = f"Error al desarmar pedido: {err}"
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()

    dialogo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.REMOVE_SHOPPING_CART, color=ROJO), ft.Text(f"Desarmar Pedido #{pedido.nota_pedido}")], spacing=8),
        content=ft.Container(
            width=460,
            content=ft.Column(
                [
                    ft.Text(
                        f"¿Confirmas el desarmado del pedido de '{pedido.cliente}'? "
                        "El pedido se anulará y los productos se sumarán de vuelta al stock disponible en el sistema y en el Excel.",
                        size=12,
                    ),
                    *(
                        [
                            ft.Text(
                                f"⚠️ Atención: Este pedido ya formó parte del Cierre #{pedido.cierre_id}. Al desarmarlo, las unidades se reincorporarán al stock actual.",
                                size=11,
                                color=ft.Colors.AMBER_800,
                                weight=ft.FontWeight.W_500,
                            )
                        ]
                        if getattr(pedido, "cierre_id", None)
                        else []
                    ),
                    ft.Divider(height=10),
                    ft.Text(f"Productos a devolver al inventario ({total_unidades} unidades en total):", weight=ft.FontWeight.BOLD, size=11, color=interfaz.texto),
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
