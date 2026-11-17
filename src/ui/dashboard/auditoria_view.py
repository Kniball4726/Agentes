"""Vista y renderizado de tarjetas de auditoría para el rol Master."""

from __future__ import annotations

from typing import Any
import flet as ft
from ..theme import ROJO


def renderizar_auditoria_master(interfaz: Any, eventos_auditoria: list[Any]) -> None:
    """Genera las tarjetas de eventos de auditoría para la consola del rol Master."""
    interfaz.lista_informes.controls.clear()
    if not eventos_auditoria:
        interfaz.lista_informes.controls.append(
            ft.Text("Todavía no hay eventos de auditoría registrados.", size=12, color=interfaz.secundario)
        )
        return

    for ev in eventos_auditoria[:15]:
        accion_ev = getattr(ev, "accion", "")
        usuario_ev = getattr(ev, "usuario", "")
        fecha_ev = getattr(ev, "fecha", "")
        detalle_ev = getattr(ev, "detalle", "")

        if "LOGIN" in accion_ev or "AUTH" in accion_ev:
            icono_ev = ft.Icons.LOGIN
            color_ev = ft.Colors.GREEN_400
        elif "LOCK" in accion_ev or "BLOQUEO" in accion_ev or "ANULAR" in accion_ev:
            icono_ev = ft.Icons.LOCK
            color_ev = ft.Colors.RED_400
        elif "RESET" in accion_ev or "USER" in accion_ev:
            icono_ev = ft.Icons.MANAGE_ACCOUNTS
            color_ev = ft.Colors.BLUE_400
        elif "BACKUP" in accion_ev:
            icono_ev = ft.Icons.BACKUP
            color_ev = ft.Colors.PURPLE_400
        elif "INGRESO_RAPIDO" in accion_ev:
            icono_ev = ft.Icons.ADD_CIRCLE_OUTLINE
            color_ev = ft.Colors.GREEN_400
        elif "SALIDA_RAPIDA" in accion_ev:
            icono_ev = ft.Icons.REMOVE_CIRCLE_OUTLINE
            color_ev = ft.Colors.AMBER_400
        else:
            icono_ev = ft.Icons.SECURITY
            color_ev = ROJO

        interfaz.lista_informes.controls.append(
            ft.ListTile(
                leading=ft.Icon(icono_ev, color=color_ev, size=19),
                title=ft.Text(f"[{accion_ev}] @{usuario_ev}", size=12, color=interfaz.texto, weight=ft.FontWeight.W_500, no_wrap=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                subtitle=ft.Text(f"{detalle_ev} · {fecha_ev}", size=10, color=interfaz.secundario, no_wrap=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                dense=True,
                content_padding=ft.Padding.symmetric(horizontal=8, vertical=0),
            )
        )
