"""Diálogo exprés para ajuste rápido de bultos y reimpresión de etiquetas."""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from ..theme import ROJO
from ...orders.models import Pedido


def mostrar_dialogo_ajuste_bultos_express(
    interfaz: Any,
    pedido: Pedido,
    al_final: Callable[[], None] | None = None,
) -> None:
    """Abre un diálogo exprés para modificar la cantidad de bultos y reimprimir rótulos en un clic."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("El ajuste de bultos es exclusivo del rol Operador.")
        return

    bultos_val = [max(1, int(pedido.bultos))]
    txt_bultos = ft.Text(str(bultos_val[0]), size=22, weight=ft.FontWeight.BOLD, color=interfaz.texto)

    def cambiar(delta: int):
        bultos_val[0] = max(1, bultos_val[0] + delta)
        txt_bultos.value = str(bultos_val[0])
        interfaz.page.update()

    def guardar_y_cerrar(reimprimir: bool = False):
        try:
            usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
            pedido_act = interfaz.order_store.actualizar_datos_pedido(
                pedido_id=pedido.id,
                bultos=bultos_val[0],
                usuario=usr,
            )
            interfaz.page.pop_dialog()
            interfaz.notificar(f"Bultos actualizados: {pedido.bultos} → {bultos_val[0]}")
            if reimprimir and hasattr(interfaz, "imprimir_rotulos_pedido"):
                interfaz.imprimir_rotulos_pedido(pedido_act)
            if al_final:
                al_final()
            elif hasattr(interfaz, "actualizar_listas"):
                interfaz.actualizar_listas()
        except Exception as err:
            interfaz.notificar(f"Error al actualizar bultos: {err}")

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.Icons.ALL_INBOX, color=ROJO),
            ft.Text("Ajuste Rápido de Bultos", size=16, weight=ft.FontWeight.BOLD),
        ], spacing=8),
        content=ft.Column(
            [
                ft.Text(f"Remito: {pedido.nota_pedido} · Cliente: {pedido.cliente}", size=12, color=interfaz.secundario),
                ft.Divider(height=10),
                ft.Row(
                    [
                        ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_color=ft.Colors.RED_400, icon_size=28, on_click=lambda _: cambiar(-1)),
                        ft.Container(content=txt_bultos, alignment=ft.Alignment.CENTER, width=60),
                        ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=ft.Colors.GREEN_400, icon_size=28, on_click=lambda _: cambiar(1)),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                ft.Text("Modifica la cantidad de bultos del envío.", size=11, color=interfaz.secundario, text_align=ft.TextAlign.CENTER),
            ],
            tight=True,
            spacing=8,
            width=320,
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: interfaz.page.pop_dialog()),
            ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=lambda _: guardar_y_cerrar(reimprimir=False)),
            ft.Button("Guardar y Reimprimir", icon=ft.Icons.PRINT, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=lambda _: guardar_y_cerrar(reimprimir=True)),
        ],
    )
    interfaz.page.show_dialog(dialogo)
