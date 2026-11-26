"""Diálogos de anulación, desarmado lógico y eliminación física de pedidos.

La lógica de restitución de stock, liberación de reservas y persistencia en
``OrderStore`` reside en ``pedidos_baja_ops``.
"""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ...core.stock_order_tx import tiene_reserva_activa_pedido
from ...orders import Pedido
from ..design import tono_legible
from ..theme import ROJO
from .pedidos_baja_ops import (
    _calcular_devoluciones_pedido,
    _instanciar_stock_manager_baja,
    _persistir_baja_pedido,
    _refrescar_vistas_pedido,
    _resolver_pedido_actual,
    _resolver_product_store_baja,
    _resolver_sm_cls,
    _restituir_stock_pedido,
    _revertir_restitucion_baja,
    _textos_confirmacion_baja,
    ejecutar_anulacion_pedido_tx,
    ejecutar_baja_transaccional,
)

__all__ = [
    "_calcular_devoluciones_pedido",
    "_instanciar_stock_manager_baja",
    "_persistir_baja_pedido",
    "_refrescar_vistas_pedido",
    "_resolver_pedido_actual",
    "_resolver_product_store_baja",
    "_resolver_sm_cls",
    "_restituir_stock_pedido",
    "_revertir_restitucion_baja",
    "_textos_confirmacion_baja",
    "construir_botones_baja_pedido",
    "mostrar_dialogo_confirmar_anulacion_pedido",
    "mostrar_dialogo_confirmar_desarmar_pedido",
    "mostrar_dialogo_confirmar_eliminacion_pedido",
]


def _construir_lista_devolucion_items(
    interfaz: Any,
    pedido: Pedido,
    items: list[tuple[str, str, int]],
    total_unidades: int,
    ya_anulado: bool,
    solo_reserva_activa: bool = False,
) -> list[ft.Control]:
    """Construye los controles de vista previa de artículos a restituir al stock o liberar de reserva."""
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

    etiqueta_previa = (
        f"Productos en reserva activa a liberar ({total_unidades} unidades en total):"
        if solo_reserva_activa
        else f"Productos a devolver al inventario ({total_unidades} unidades en total):"
    )
    return [
        ft.Text(
            etiqueta_previa,
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


def mostrar_dialogo_confirmar_anulacion_pedido(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre el diálogo para anular un pedido registrado restituyendo su stock o liberando reserva."""
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
            msg, aviso_colab = ejecutar_anulacion_pedido_tx(
                interfaz,
                pedido,
                usr=usr,
                motivo_txt=motivo_txt,
            )
            interfaz.notificar(msg)
            if not aviso_colab:
                return
            if al_final:
                al_final()
            interfaz.actualizar_listas()
            interfaz.sincronizar_sesiones(aviso_colaborativo=aviso_colab)
        except Exception as err:
            interfaz.notificar(f"Error al anular pedido: {err}")
        finally:
            en_curso[0] = False

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    c_ambar = tono_legible("AMBER", es_oscuro)
    ancho_dlg = interfaz.ancho_adaptable(420) if hasattr(interfaz, "ancho_adaptable") else 420
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ROJO),
                ft.Text("Confirmar Anulación de Pedido"),
            ]
        ),
        content=ft.Container(
            width=ancho_dlg,
            content=ft.Column(
                [
                    ft.Text(
                        f"¿Estás seguro de anular el pedido '{pedido.nota_pedido}' del cliente '{pedido.cliente}'?"
                    ),
                    ft.Text(
                        "⚠️ Al anular este pedido, todas las unidades descontadas se devolverán automáticamente al stock disponible y a la planilla Productos.xlsx en tiempo real.",
                        size=11,
                        color=c_ambar,
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(
                        "Esta acción quedará registrada en el log de auditoría del sistema.",
                        size=11,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=10),
                    motivo_input,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.Button(
                "Anular y Devolver Stock",
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=ejecutar_anulacion,
            ),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def _mostrar_dialogo_baja_pedido(
    interfaz: Any,
    pedido: Pedido,
    *,
    modo: str,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Despliega confirmación unificada para Desarmar (borrado lógico) o Eliminar (borrado físico)."""
    es_eliminar = modo == "eliminar"
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in (
        "operador",
        "administrador",
    ):
        verbo = "eliminar" if es_eliminar else "desarmar"
        interfaz.notificar(f"No tienes permisos suficientes para {verbo} pedidos.")
        return

    ya_anulado = getattr(pedido, "estado", "") == "anulado"
    if not es_eliminar and ya_anulado:
        interfaz.notificar(f"El pedido #{pedido.nota_pedido} ya se encuentra anulado.")
        return

    items = [] if ya_anulado else interfaz.order_store.obtener_items_pedido(pedido.id)
    total_unidades = (
        0
        if ya_anulado
        else (sum(cant for _, _, cant in items) if items else pedido.articulos_descontados)
    )
    p_store_prev = _resolver_product_store_baja(interfaz)
    solo_reserva_prev = (
        False if ya_anulado else tiene_reserva_activa_pedido(p_store_prev, pedido.nota_pedido)
    )

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    c_ambar = tono_legible("AMBER", es_oscuro)
    color_acento = ROJO if es_eliminar else ft.Colors.AMBER_800
    icono_titulo = ft.Icons.DELETE_FOREVER if es_eliminar else ft.Icons.REMOVE_SHOPPING_CART
    titulo_txt = (
        f"Eliminar Pedido #{pedido.nota_pedido}"
        if es_eliminar
        else f"Desarmar Pedido #{pedido.nota_pedido}"
    )
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
        if (
            en_curso[0]
            or interfaz.usuario_actual is None
            or interfaz.usuario_actual.role not in ("operador", "administrador")
        ):
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

            msg_exito, aviso_colab = ejecutar_baja_transaccional(
                interfaz,
                pedido,
                pedido_actual,
                es_eliminar=es_eliminar,
                usr=usr,
                motivo_txt=motivo_txt,
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
        title=ft.Row(
            [ft.Icon(icono_titulo, color=ROJO if es_eliminar else c_ambar), ft.Text(titulo_txt)],
            spacing=8,
        ),
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
                    *_construir_lista_devolucion_items(
                        interfaz,
                        pedido,
                        items,
                        total_unidades,
                        ya_anulado,
                        solo_reserva_prev,
                    ),
                    motivo_input,
                    error_msg,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            ft.Button(
                btn_texto, bgcolor=color_acento, color=ft.Colors.WHITE, on_click=ejecutar_baja
            ),
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
