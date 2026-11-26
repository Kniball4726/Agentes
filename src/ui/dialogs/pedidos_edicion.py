"""Diálogos de bloqueo de concurrencia y edición de datos de pedidos."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import flet as ft

from ...orders import LOGISTICA_OPCIONES, Pedido
from ..design import colores_de, limpiar_errores, marcar_error
from ..theme import ROJO


def _formatear_antiguedad_bloqueo(f_bloqueo: str) -> str:
    """Devuelve una descripción legible del tiempo transcurrido desde el bloqueo."""
    try:
        t_diff = int((datetime.now() - datetime.fromisoformat(f_bloqueo)).total_seconds() // 60)
        return f"hace {t_diff} min" if t_diff > 0 else "hace menos de 1 minuto"
    except Exception:
        return "recientemente"


def _mostrar_dialogo_bloqueo_pedido(
    interfaz: Any,
    pedido: Pedido,
    usr_bloqueo: str,
    f_bloqueo: str,
    al_final: Callable[[], None] | None,
) -> None:
    """Informa que el pedido está siendo editado por otro usuario y ofrece lectura o desbloqueo."""
    tiempo_str = _formatear_antiguedad_bloqueo(f_bloqueo)

    def forzar_desbloqueo_y_abrir(_e: ft.Event) -> None:
        interfaz.page.pop_dialog()
        interfaz.order_store.liberar_bloqueo_pedido(pedido.id)
        mostrar_dialogo_editar_pedido(interfaz, pedido, al_final)

    def abrir_modo_lectura(_e: ft.Event) -> None:
        interfaz.page.pop_dialog()
        if hasattr(interfaz, "mostrar_detalle_pedido_modal"):
            interfaz.mostrar_detalle_pedido_modal(pedido)

    ancho_bloq = interfaz.ancho_adaptable(450) if hasattr(interfaz, "ancho_adaptable") else 450
    dialogo_bloqueo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [ft.Icon(ft.Icons.LOCK, color=colores_de(interfaz).advertencia), ft.Text("Pedido en Edición Simultánea")]
        ),
        content=ft.Container(
            width=ancho_bloq,
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


def _adquirir_lock_edicion(interfaz: Any, pedido: Pedido, usr_actual: str) -> tuple[bool, str, str]:
    """Intenta adquirir el soft-lock de edición para un pedido."""
    store = getattr(interfaz, "order_store", None)
    if not store:
        return True, usr_actual, ""
    try:
        res_lock = store.adquirir_bloqueo_pedido(pedido.id, usr_actual)
        if isinstance(res_lock, tuple) and len(res_lock) >= 3:
            return bool(res_lock[0]), str(res_lock[1]), str(res_lock[2])
        return bool(res_lock), usr_actual, ""
    except Exception:
        return True, usr_actual, ""


def _liberar_lock_silencioso(interfaz: Any, pedido_id: int, usr: str) -> None:
    """Libera el bloqueo de edición de un pedido ignorando errores de red o cierre."""
    store = getattr(interfaz, "order_store", None)
    if not store:
        return
    try:
        store.liberar_bloqueo_pedido(pedido_id, usr)
    except Exception:
        pass


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
    ok_lock, usr_bloqueo, f_bloqueo = _adquirir_lock_edicion(interfaz, pedido, usr_actual)
    if not ok_lock:
        _mostrar_dialogo_bloqueo_pedido(interfaz, pedido, usr_bloqueo, f_bloqueo, al_final)
        return

    cliente_input = ft.TextField(
        label="Cliente *",
        value=pedido.cliente,
        dense=True,
        autofocus=not bool(getattr(interfaz, "es_pantalla_movil", False)),
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
    numero_guia_input = ft.TextField(
        label="N° de Guía / Tracking del Transporte (opcional)",
        value=str(getattr(pedido, "numero_guia", "") or ""),
        hint_text="ej: TRK-987654 o 00012345678",
        dense=True,
    )
    error_msg = ft.Text("", color=ft.Colors.RED_400, size=11, visible=False)

    def _mostrar_error(campo: ft.Control | None, msg_corto: str, msg_largo: str) -> None:
        if campo is not None:
            marcar_error(campo, msg_corto)
        error_msg.value = msg_largo
        error_msg.visible = True
        if interfaz.page:
            interfaz.page.update()

    def guardar_cambios(_e: ft.Event) -> None:
        limpiar_errores(cliente_input, bultos_input)
        c_val = (cliente_input.value or "").strip()
        if not c_val:
            _mostrar_error(cliente_input, "El cliente no puede estar vacío.", "El cliente no puede estar vacío.")
            return
        try:
            b_val = int((bultos_input.value or "1").strip())
            if b_val < 1:
                raise ValueError
        except Exception:
            _mostrar_error(
                bultos_input,
                "Debe ser un entero mayor o igual a 1.",
                "La cantidad de bultos debe ser un número entero mayor o igual a 1.",
            )
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
            _liberar_lock_silencioso(interfaz, pedido.id, usr)
            interfaz.notificar(f"Pedido #{pedido.nota_pedido} actualizado correctamente.")
            if al_final:
                al_final()
            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"✏️ {usr} actualizó datos del Pedido #{pedido.nota_pedido} ({c_val})"
            )
        except Exception as err:
            _mostrar_error(None, "", f"Error al actualizar: {err}")

    def al_cerrar_dialogo(_e: Any = None) -> None:
        _liberar_lock_silencioso(interfaz, getattr(pedido, "id", 0), usr_actual)

    ancho_edit = interfaz.ancho_adaptable(420) if hasattr(interfaz, "ancho_adaptable") else 420
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.EDIT_NOTE, color=ft.Colors.BLUE_600), ft.Text(f"Modificar Pedido #{pedido.nota_pedido}")], spacing=8),
        content=ft.Container(
            width=ancho_edit,
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
