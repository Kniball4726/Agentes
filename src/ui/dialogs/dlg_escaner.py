"""Diálogo modal para el escaneo de rótulos QR y actualización del estado de despacho."""
from datetime import datetime
from typing import Any, Callable
import flet as ft
from ..theme import ROJO


def mostrar_dialogo_escaner_qr_despacho(
    interfaz: Any,
    al_actualizar: Callable[[], None] | None = None,
) -> None:
    """Modal para escanear códigos QR de rótulos de bulto o ingresar remito y avanzar estado."""
    if interfaz.usuario_actual is None:
        return
    selector_modo = ft.Dropdown(
        label="Acción al escanear / ingresar",
        value="auto",
        options=[
            ft.DropdownOption(key="auto", text="Avanzar automáticamente (Armado → Despachado → Entregado)"),
            ft.DropdownOption(key="despachado", text="Marcar siempre como DESPACHADO"),
            ft.DropdownOption(key="entregado", text="Marcar siempre como ENTREGADO"),
            ft.DropdownOption(key="armado", text="Volver a ARMADO"),
        ],
        dense=True,
    )
    input_qr = ft.TextField(
        label="Escanear código QR del rótulo o escribir N° de Remito / Factura",
        hint_text="Ej: REMITO:0001-00012345|CLIENTE:...|BULTOS:1/2 o 0001-00012345",
        prefix_icon=ft.Icons.QR_CODE_SCANNER,
        autofocus=True,
    )
    historial_escaneos = ft.ListView(expand=True, spacing=6, height=220)
    msg_estado = ft.Text(
        "Posiciona el lector sobre este campo y escanea la etiqueta del bulto (presiona Enter).",
        size=12,
        color=interfaz.secundario,
    )

    def procesar_escaneo(_e: ft.Event | None = None) -> None:
        raw = (input_qr.value or "").strip()
        if not raw:
            return
        modo_sel = selector_modo.value or "auto"
        estado_forzado = None if modo_sel == "auto" else modo_sel
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
        ok, msg, ped = interfaz.order_store.avanzar_estado_por_codigo(
            codigo_qr_o_remito=raw,
            usuario=usr,
            nuevo_estado=estado_forzado,
        )
        input_qr.value = ""
        msg_estado.value = f"{'✅' if ok else '❌'} {msg}"
        msg_estado.color = ft.Colors.GREEN_400 if ok else ft.Colors.RED_400
        if ped is not None:
            historial_escaneos.controls.insert(
                0,
                ft.Container(
                    padding=8,
                    border_radius=6,
                    bgcolor=ft.Colors.GREEN_900 if (ok and interfaz.modo_oscuro) else (ft.Colors.GREEN_50 if ok else ft.Colors.RED_50),
                    border=ft.Border.all(1, ft.Colors.GREEN_600 if ok else ft.Colors.RED_400),
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE if ok else ft.Icons.INFO, color=ft.Colors.GREEN_400 if ok else ft.Colors.RED_400, size=18),
                            ft.Text(
                                f"[{datetime.now().strftime('%H:%M:%S')}] Remito {ped.nota_pedido} ({ped.cliente}) → {ped.estado_despacho.upper()}",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=interfaz.texto,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                ),
            )
        if al_actualizar is not None:
            al_actualizar()
        interfaz.sincronizar_sesiones()
        input_qr.focus()
        interfaz.page.update()

    input_qr.on_submit = procesar_escaneo

    dlg_qr = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.QR_CODE_SCANNER, color=ROJO),
                ft.Text("Escáner QR de Despacho y Entrega", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=560,
            content=ft.Column(
                [
                    selector_modo,
                    ft.Row(
                        [
                            ft.Container(content=input_qr, expand=True),
                            ft.Button(
                                "Procesar",
                                icon=ft.Icons.CHECK,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                on_click=procesar_escaneo,
                            ),
                        ],
                        spacing=8,
                    ),
                    msg_estado,
                    ft.Divider(height=8),
                    ft.Text("Últimos bultos / pedidos escaneados en esta sesión:", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                    historial_escaneos,
                ],
                tight=True,
                spacing=10,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dlg_qr)
