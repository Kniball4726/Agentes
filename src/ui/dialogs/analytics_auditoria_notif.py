"""Vistas de auditoría del sistema y notificaciones de operarios."""

from __future__ import annotations

import sys
from typing import Any

import flet as ft

from ..theme import ROJO
from ._shared import resolve_stock_manager


def _resolver_stock_manager():
    """Resuelve StockManager respetando patches sobre dlg_analytics o src.flet_gui."""
    mod_dlg = sys.modules.get("src.ui.dialogs.dlg_analytics")
    if mod_dlg is not None and hasattr(mod_dlg, "_get_stock_manager"):
        return mod_dlg._get_stock_manager()
    return resolve_stock_manager("src.flet_gui")


def mostrar_registro_auditoria(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Ventana del historial de auditoría y trazabilidad del sistema."""
    if not interfaz.exigir_roles("master"):
        return

    lista_eventos = ft.ListView(expand=True, spacing=6, height=380)
    input_busqueda = ft.TextField(
        hint_text="Filtrar eventos por usuario, acción o detalle...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
    )

    def color_accion(accion: str) -> tuple[str, str]:
        if "CARGA" in accion or "CREAR" in accion:
            return (
                ft.Colors.BLUE_100 if not interfaz.modo_oscuro else ft.Colors.BLUE_900,
                ft.Colors.BLUE_800 if not interfaz.modo_oscuro else ft.Colors.BLUE_200,
            )
        if "ANULAR" in accion or "ALERTA" in accion:
            return (
                ft.Colors.RED_100 if not interfaz.modo_oscuro else ft.Colors.RED_900,
                ft.Colors.RED_800 if not interfaz.modo_oscuro else ft.Colors.RED_200,
            )
        if "CIERRE" in accion:
            return (
                ft.Colors.GREEN_100 if not interfaz.modo_oscuro else ft.Colors.GREEN_900,
                ft.Colors.GREEN_800 if not interfaz.modo_oscuro else ft.Colors.GREEN_200,
            )
        if "BACKUP" in accion:
            return (
                ft.Colors.PURPLE_100 if not interfaz.modo_oscuro else ft.Colors.PURPLE_900,
                ft.Colors.PURPLE_800 if not interfaz.modo_oscuro else ft.Colors.PURPLE_200,
            )
        return (ft.Colors.GREY_200 if not interfaz.modo_oscuro else ft.Colors.GREY_800, interfaz.texto)

    def refrescar_lista(_ev: ft.Event | None = None) -> None:
        lista_eventos.controls.clear()
        txt = (input_busqueda.value or "").strip()
        logs = interfaz.order_store.listar_auditoria(limit=200, filtro_texto=txt)
        if not logs:
            lista_eventos.controls.append(ft.Text("No se encontraron registros de auditoría.", size=12, color=interfaz.secundario))
        else:
            for reg in logs:
                bg_col, txt_col = color_accion(reg.accion)
                badge = ft.Container(
                    content=ft.Text(reg.accion, size=9, weight=ft.FontWeight.BOLD, color=txt_col),
                    bgcolor=bg_col,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                )
                lista_eventos.controls.append(
                    ft.Container(
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
                        border=ft.Border.all(1, interfaz.borde),
                        border_radius=6,
                        padding=8,
                        content=ft.Row(
                            [
                                badge,
                                ft.Text(f"[{reg.usuario}]", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                                ft.Text(reg.detalle, size=11, color=interfaz.texto, expand=True),
                                ft.Text(reg.created_at[:16], size=10, color=interfaz.secundario),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
        interfaz.page.update()

    input_busqueda.on_change = refrescar_lista
    refrescar_lista()

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.SECURITY, color=ROJO),
                ft.Text("Registro de Auditoría y Trazabilidad", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=740,
            content=ft.Column([input_busqueda, ft.Divider(height=6), lista_eventos], tight=True, spacing=8),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _ev: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_notificaciones_admin(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para revisar notificaciones de operarios y avisos de stock."""
    if not interfaz.exigir_roles("administrador"):
        return

    sm = _resolver_stock_manager()(interfaz.menu.ruta_excel_base)
    lista_notificaciones = ft.ListView(expand=True, spacing=8, height=340)

    def recargar_lista() -> None:
        lista_notificaciones.controls.clear()
        items = sm.obtener_notificaciones_admin(solo_no_leidas=False)
        if not items:
            lista_notificaciones.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=20,
                    content=ft.Text("No hay notificaciones de operarios registradas.", color=interfaz.secundario, size=13),
                )
            )
        else:
            for n in items:
                nid = n["id"]
                leida = bool(n["is_read"])
                operador = n["operator_username"]
                fecha = n["created_at"]
                msg = n["message"]
                tipo_notif = n["notification_type"] if "notification_type" in n.keys() else "descuento"

                def crear_handler_marcar(notif_id: int):
                    def marcar(_e: ft.Event):
                        sm.marcar_notificaciones_leidas(notif_id)
                        recargar_lista()
                        interfaz.page.update()
                    return marcar

                badge_leida = None
                if not leida:
                    badge_leida = ft.Container(
                        content=ft.Text("NUEVA", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        bgcolor=ROJO,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    )

                etiqueta_tipo = "Inventario Físico" if tipo_notif == "stock_fisico" else "Descuento"
                fila_cabecera = [
                    ft.Icon(
                        ft.Icons.ASSIGNMENT_TURNED_IN
                        if tipo_notif == "stock_fisico"
                        else (ft.Icons.NOTIFICATIONS_ACTIVE if not leida else ft.Icons.CHECK_CIRCLE),
                        color=ft.Colors.BLUE_500
                        if (tipo_notif == "stock_fisico" and not leida)
                        else (ROJO if not leida else ft.Colors.GREEN_600),
                        size=16,
                    ),
                    ft.Text(f"[{etiqueta_tipo}] Operario: {operador}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                    ft.Text(f"· {fecha}", size=11, color=interfaz.secundario),
                ]
                if badge_leida:
                    fila_cabecera.append(badge_leida)

                card_content = [
                    ft.Row(fila_cabecera, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    ft.Text(msg, size=12, color=interfaz.texto),
                ]
                acciones_fila = []
                if tipo_notif == "stock_fisico":
                    acciones_fila.append(
                        ft.TextButton(
                            "Ver comparativa",
                            icon=ft.Icons.COMPARE_ARROWS,
                            on_click=lambda _e: (
                                interfaz.page.pop_dialog(),
                                interfaz.mostrar_comparativa_stock_fisico_admin(),
                            ),
                        )
                    )
                if not leida:
                    acciones_fila.append(
                        ft.TextButton("Marcar como leída", icon=ft.Icons.CHECK, on_click=crear_handler_marcar(nid))
                    )
                if acciones_fila:
                    card_content.append(ft.Row(acciones_fila, alignment=ft.MainAxisAlignment.END))

                lista_notificaciones.controls.append(
                    ft.Container(
                        padding=10,
                        border_radius=8,
                        bgcolor=ft.Colors.RED_50 if (not leida and not interfaz.modo_oscuro) else (ft.Colors.WHITE_10 if not leida else ft.Colors.TRANSPARENT),
                        border=ft.Border.all(1, ft.Colors.RED_200 if (not leida and not interfaz.modo_oscuro) else interfaz.borde),
                        content=ft.Column(card_content, spacing=4),
                    )
                )
        interfaz.page.update()

    recargar_lista()

    def marcar_todas_leidas(_e: ft.Event) -> None:
        sm.marcar_notificaciones_leidas(None)
        recargar_lista()
        interfaz.page.update()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.NOTIFICATIONS, color=ROJO),
                ft.Text("Notificaciones de Descuentos de Operarios", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=550,
            content=ft.Column(
                [
                    ft.Text(
                        "Registro de descuentos de stock ejecutados por usuarios con rol de operador.",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=6),
                    lista_notificaciones,
                ],
                tight=True,
                spacing=6,
            ),
        ),
        actions=[
            ft.TextButton("Marcar todas como leídas", icon=ft.Icons.DONE_ALL, on_click=marcar_todas_leidas),
            interfaz.boton_dialogo("Cerrar", lambda _e: (interfaz.page.pop_dialog(), interfaz.actualizar_estado())),
        ],
    )
    interfaz.page.show_dialog(dialogo)
