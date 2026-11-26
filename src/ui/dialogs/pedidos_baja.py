"""Diálogos de anulación, desarmado lógico, eliminación física y restitución de stock de pedidos."""

from __future__ import annotations

import sys
from typing import Any, Callable

import flet as ft

from ...inventory import StockManager as _DefaultStockManager
from ...orders import Pedido
from ..design import tono_legible
from ..theme import ROJO


def _resolver_sm_cls():
    """Resuelve la clase StockManager vigente respetando mocks de tests en dlg_pedidos o flet_gui."""
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
    if not interfaz.exigir_roles("operador", "administrador"):
        return

    motivo_input = ft.TextField(
        label="Motivo de la anulación (opcional)",
        hint_text="ej: Cancelado por el cliente, duplicado, error en carga",
        dense=True,
        autofocus=not bool(getattr(interfaz, "es_pantalla_movil", False)),
    )
    en_curso = [False]

    def ejecutar_anulacion(_e: ft.Event) -> None:
        if en_curso[0] or not interfaz.exigir_roles("operador", "administrador"):
            return
        en_curso[0] = True
        interfaz.page.pop_dialog()
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema"
        motivo_txt = (motivo_input.value or "").strip()
        try:
            pedido_actual = interfaz.order_store.buscar_pedido_por_nota(pedido.nota_pedido) or pedido
            if getattr(pedido_actual, "estado", "") == "anulado":
                interfaz.notificar(f"El pedido {pedido.nota_pedido} ya se encontraba anulado.")
                return
            unidades_restituidas = _restituir_stock_pedido(interfaz, pedido_actual)
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
        except Exception as err:
            interfaz.notificar(f"Error al anular pedido: {err}")
        finally:
            en_curso[0] = False

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    c_ambar = tono_legible("AMBER", es_oscuro)
    ancho_dlg = interfaz.ancho_adaptable(420) if hasattr(interfaz, "ancho_adaptable") else 420
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ROJO), ft.Text("Confirmar Anulación de Pedido")]),
        content=ft.Container(
            width=ancho_dlg,
            content=ft.Column(
                [
                    ft.Text(f"¿Estás seguro de anular el pedido '{pedido.nota_pedido}' del cliente '{pedido.cliente}'?"),
                    ft.Text(
                        "⚠️ Al anular este pedido, todas las unidades descontadas se devolverán automáticamente al stock disponible y a la planilla Productos.xlsx en tiempo real.",
                        size=11,
                        color=c_ambar,
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


def _resolver_pedido_actual(interfaz: Any, pedido: Pedido) -> Pedido | None:
    """Obtiene el estado vigente del pedido desde el store; tolera mocks sin configurar."""
    store = getattr(interfaz, "order_store", None)
    if store is None:
        return pedido
    for metodo, arg in (("obtener_pedido_por_id", pedido.id), ("buscar_pedido_por_nota", pedido.nota_pedido)):
        fn = getattr(store, metodo, None)
        if callable(fn):
            res = fn(arg)
            if res is None:
                return None
            if isinstance(getattr(res, "estado", None), str):
                return res
    return pedido


def _refrescar_vistas_pedido(interfaz: Any, al_final: Callable[[], None] | None) -> None:
    """Ejecuta el callback local y refresca las listas globales del dashboard sin duplicar."""
    act_listas = getattr(interfaz, "actualizar_listas", None)
    if callable(al_final):
        al_final()
    if callable(act_listas) and act_listas is not al_final:
        act_listas()


def _construir_lista_devolucion_items(
    interfaz: Any,
    pedido: Pedido,
    items: list[tuple[str, str, int]],
    total_unidades: int,
    ya_anulado: bool,
) -> list[ft.Control]:
    """Construye los controles de vista previa de artículos a restituir al stock."""
    if ya_anulado:
        return [
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=6,
                content=ft.Text(
                    "Este pedido ya estaba desarmado/anulado: sus artículos ya fueron restituidos al inventario anteriormente.",
                    size=11,
                    color=interfaz.secundario,
                ),
            )
        ]

    if items:
        lista_items_controls: list[ft.Control] = [
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
            ft.Text(
                f"Detalle: {pedido.resumen_items or f'{pedido.articulos_descontados} artículos'}",
                size=11,
                color=interfaz.secundario,
            )
        ]

    return [
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
    ]


def _textos_confirmacion_baja(pedido: Pedido, *, es_eliminar: bool, ya_anulado: bool) -> tuple[str, str, str]:
    """Devuelve texto de confirmación, advertencia de cierre y texto del botón para baja de pedido."""
    if es_eliminar:
        texto = (
            f"¿Confirmas la eliminación física definitiva del pedido anulado de '{pedido.cliente}'? "
            "Se borrará permanentemente de la base de datos y podrás volver a cargar el remito."
            if ya_anulado
            else f"¿Confirmas la eliminación física definitiva del pedido de '{pedido.cliente}'? "
            "Se borrará permanentemente de la base de datos (permitiendo recargar el remito) y los productos se devolverán al stock."
        )
        aviso_cierre = (
            f"⚠️ Atención: Este pedido formó parte del Cierre #{pedido.cierre_id}. "
            "Al eliminarlo, desaparecerá del historial de ese cierre y se restituirá el stock activo."
        )
        return texto, aviso_cierre, "Eliminar Definitivamente"

    texto = (
        f"¿Confirmas el desarmado del pedido de '{pedido.cliente}'? "
        "Se aplicará borrado lógico (estado anulado) y los productos se sumarán de vuelta al stock disponible en el sistema y en el Excel."
    )
    aviso_cierre = (
        f"⚠️ Atención: Este pedido ya formó parte del Cierre #{pedido.cierre_id}. "
        "Al desarmarlo, las unidades se reincorporarán al stock actual."
    )
    return texto, aviso_cierre, "Desarmar y Devolver Stock"


def _persistir_baja_pedido(
    interfaz: Any,
    pedido: Pedido,
    *,
    es_eliminar: bool,
    usr: str,
    motivo_txt: str,
    unidades_restituidas: int,
) -> tuple[str, str]:
    """Ejecuta el borrado físico o lógico en OrderStore junto con su registro de auditoría."""
    if es_eliminar:
        interfaz.order_store.eliminar_pedido(
            pedido_id=pedido.id,
            motivo=motivo_txt,
            usuario=usr,
            registrar_auditoria=False,
        )
        interfaz.order_store.registrar_auditoria(
            usuario=usr,
            accion="ELIMINAR_PEDIDO",
            detalle=(
                f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) eliminado definitivamente (borrado físico). "
                f"Stock restituido: {unidades_restituidas} unidades. Motivo: {motivo_txt or 'Sin especificar'}"
            ),
        )
        msg_exito = f"Pedido #{pedido.nota_pedido} eliminado definitivamente."
        if unidades_restituidas > 0:
            msg_exito += f" Se reincorporaron {unidades_restituidas} unidades al stock."
        return msg_exito, f"🗑️ {usr} eliminó el Pedido #{pedido.nota_pedido} ({pedido.cliente})"

    interfaz.order_store.anular_pedido(
        pedido_id=pedido.id,
        motivo=f"Desarmado de pedido y devolución de stock. {motivo_txt}".strip(),
        usuario=usr,
    )
    interfaz.order_store.registrar_auditoria(
        usuario=usr,
        accion="DESARMAR_PEDIDO",
        detalle=(
            f"Pedido #{pedido.nota_pedido} ({pedido.cliente}) desarmado (borrado lógico). "
            f"Stock restituido: {unidades_restituidas} unidades. Motivo: {motivo_txt or 'Sin especificar'}"
        ),
    )
    return (
        f"Pedido #{pedido.nota_pedido} desarmado con éxito. Se reincorporaron {unidades_restituidas} unidades al stock.",
        f"⚠️ {usr} desarmó el Pedido #{pedido.nota_pedido} ({pedido.cliente})",
    )


def _mostrar_dialogo_baja_pedido(
    interfaz: Any,
    pedido: Pedido,
    *,
    modo: str,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Despliega confirmación unificada para Desarmar (borrado lógico) o Eliminar (borrado físico)."""
    es_eliminar = modo == "eliminar"
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador"):
        verbo = "eliminar" if es_eliminar else "desarmar"
        interfaz.notificar(f"No tienes permisos suficientes para {verbo} pedidos.")
        return

    ya_anulado = getattr(pedido, "estado", "") == "anulado"
    if not es_eliminar and ya_anulado:
        interfaz.notificar(f"El pedido #{pedido.nota_pedido} ya se encuentra anulado.")
        return

    items = [] if ya_anulado else interfaz.order_store.obtener_items_pedido(pedido.id)
    total_unidades = 0 if ya_anulado else (sum(cant for _, _, cant in items) if items else pedido.articulos_descontados)

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    c_ambar = tono_legible("AMBER", es_oscuro)
    color_acento = ROJO if es_eliminar else ft.Colors.AMBER_800
    icono_titulo = ft.Icons.DELETE_FOREVER if es_eliminar else ft.Icons.REMOVE_SHOPPING_CART
    titulo_txt = f"Eliminar Pedido #{pedido.nota_pedido}" if es_eliminar else f"Desarmar Pedido #{pedido.nota_pedido}"
    motivo_input = ft.TextField(
        label="Motivo de la eliminación (opcional)" if es_eliminar else "Motivo del desarmado (opcional)",
        hint_text=(
            "ej: Carga errónea, remito duplicado para volver a cargar"
            if es_eliminar
            else "ej: Pedido cancelado por el cliente / Reincorporación de mercadería a depósito"
        ),
        dense=True,
        autofocus=not bool(getattr(interfaz, "es_pantalla_movil", False)),
    )
    error_msg = ft.Text("", color=ft.Colors.RED_400, size=11, visible=False)
    en_curso = [False]

    def ejecutar_baja(_e: ft.Event) -> None:
        if en_curso[0] or interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador"):
            return
        en_curso[0] = True
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Sistema"
        motivo_txt = (motivo_input.value or "").strip()
        try:
            pedido_actual = _resolver_pedido_actual(interfaz, pedido)
            if pedido_actual is None:
                interfaz.page.pop_dialog()
                interfaz.notificar(f"El pedido #{pedido.nota_pedido} ya no existe en el sistema.")
                _refrescar_vistas_pedido(interfaz, al_final)
                return

            estaba_anulado = getattr(pedido_actual, "estado", "") == "anulado"
            if not es_eliminar and estaba_anulado:
                interfaz.page.pop_dialog()
                interfaz.notificar(f"El pedido #{pedido.nota_pedido} ya se encuentra anulado.")
                _refrescar_vistas_pedido(interfaz, al_final)
                return

            unidades_restituidas = 0 if estaba_anulado else _restituir_stock_pedido(interfaz, pedido_actual)
            msg_exito, aviso_colab = _persistir_baja_pedido(
                interfaz,
                pedido,
                es_eliminar=es_eliminar,
                usr=usr,
                motivo_txt=motivo_txt,
                unidades_restituidas=unidades_restituidas,
            )
            interfaz.page.pop_dialog()
            interfaz.notificar(msg_exito)
            _refrescar_vistas_pedido(interfaz, al_final)
            interfaz.sincronizar_sesiones(aviso_colaborativo=aviso_colab)
        except Exception as err:
            verbo_err = "eliminar" if es_eliminar else "desarmar"
            error_msg.value = f"Error al {verbo_err} pedido: {err}"
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()
        finally:
            en_curso[0] = False

    texto_confirmacion, aviso_cierre, btn_texto = _textos_confirmacion_baja(
        pedido, es_eliminar=es_eliminar, ya_anulado=ya_anulado
    )
    ancho_dlg = interfaz.ancho_adaptable(460) if hasattr(interfaz, "ancho_adaptable") else 460
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(icono_titulo, color=ROJO if es_eliminar else c_ambar), ft.Text(titulo_txt)], spacing=8),
        content=ft.Container(
            width=ancho_dlg,
            content=ft.Column(
                [
                    ft.Text(texto_confirmacion, size=12),
                    *(
                        [ft.Text(aviso_cierre, size=11, color=c_ambar, weight=ft.FontWeight.W_500)]
                        if getattr(pedido, "cierre_id", None)
                        else []
                    ),
                    ft.Divider(height=10),
                    *_construir_lista_devolucion_items(interfaz, pedido, items, total_unidades, ya_anulado),
                    motivo_input,
                    error_msg,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.Button(btn_texto, bgcolor=color_acento, color=ft.Colors.WHITE, on_click=ejecutar_baja),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_dialogo_confirmar_desarmar_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para desarmar un pedido (borrado lógico) y reincorporar sus artículos al inventario."""
    _mostrar_dialogo_baja_pedido(interfaz, pedido, modo="desarmar", al_final=al_final)


def mostrar_dialogo_confirmar_eliminacion_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para eliminar físicamente un pedido y restituir sus artículos al inventario."""
    _mostrar_dialogo_baja_pedido(interfaz, pedido, modo="eliminar", al_final=al_final)


def _abrir_baja_pedido(
    interfaz: Any,
    pedido: Pedido,
    *,
    modo: str,
    on_finalizar: Callable[[], None] | None = None,
) -> None:
    """Despacha el diálogo de desarmado o eliminación delegando en el coordinador si existe."""
    cb = on_finalizar or getattr(interfaz, "actualizar_listas", None)
    metodo = "confirmar_eliminacion_pedido" if modo == "eliminar" else "confirmar_desarmar_pedido"
    fn = getattr(interfaz, metodo, None)
    if callable(fn):
        fn(pedido, al_final=cb)
    else:
        _mostrar_dialogo_baja_pedido(interfaz, pedido, modo=modo, al_final=cb)


def construir_botones_baja_pedido(
    interfaz: Any,
    pedido: Pedido,
    *,
    on_finalizar: Callable[[], None] | None = None,
    icon_size: int = 16,
    button_size: int = 26,
) -> list[ft.Control]:
    """Construye los botones de Desarmar (borrado lógico) y Eliminar (borrado físico) para el operario."""
    usuario = getattr(interfaz, "usuario_actual", None)
    if not (usuario and getattr(usuario, "role", None) == "operador"):
        return []

    es_anulado = getattr(pedido, "estado", "") == "anulado"
    estilo_compacto = ft.ButtonStyle(padding=0)
    col_sec = getattr(interfaz, "secundario", ft.Colors.GREY_400)
    return [
        ft.IconButton(
            icon=ft.Icons.REMOVE_SHOPPING_CART_OUTLINED,
            icon_size=icon_size,
            width=button_size,
            height=button_size,
            style=estilo_compacto,
            disabled=es_anulado,
            tooltip=(
                "Pedido ya desarmado/anulado"
                if es_anulado
                else "Desarmar pedido (borrado lógico y devuelve stock)"
            ),
            icon_color=col_sec if es_anulado else ft.Colors.AMBER_400,
            on_click=(
                None
                if es_anulado
                else (
                    lambda _e, p_obj=pedido: _abrir_baja_pedido(
                        interfaz, p_obj, modo="desarmar", on_finalizar=on_finalizar
                    )
                )
            ),
        ),
        ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_size=icon_size,
            width=button_size,
            height=button_size,
            style=estilo_compacto,
            tooltip="Eliminar pedido definitivamente (borrado físico y devuelve stock)",
            icon_color=ft.Colors.RED_400,
            on_click=lambda _e, p_obj=pedido: _abrir_baja_pedido(
                interfaz, p_obj, modo="eliminar", on_finalizar=on_finalizar
            ),
        ),
    ]
