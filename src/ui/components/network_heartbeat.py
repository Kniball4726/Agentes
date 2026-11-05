"""Módulo de monitorización de conectividad de red, Heartbeat periódico y semáforos visuales."""

from __future__ import annotations

import sqlite3
import threading
import time
from typing import Any
import flet as ft


def actualizar_estado_conexion_ui(
    interfaz: Any,
    estado: str = "online",
    mensaje: str = "",
    latencia_ms: float = 0.0,
) -> None:
    """Actualiza los semáforos de red en el encabezado y notifica microcortes o reconexiones en tiempo real."""
    estado_previo = getattr(interfaz, "_estado_red_actual", "online")
    interfaz._estado_red_actual = estado
    modo_oscuro = getattr(interfaz, "modo_oscuro", True)

    if estado == "online":
        icono = ft.Icons.CIRCLE
        color_icono = ft.Colors.GREEN_400
        texto_label = "En línea"
        color_texto = ft.Colors.GREEN_400 if modo_oscuro else ft.Colors.GREEN_700
        bg_color = ft.Colors.GREEN_900 if modo_oscuro else ft.Colors.GREEN_50
        borde_color = ft.Colors.GREEN_800 if modo_oscuro else ft.Colors.GREEN_300
        tt = (
            f"Conexión activa con el servidor central ({int(latencia_ms)} ms)"
            if latencia_ms > 0
            else "Conectado al servidor local de StockAgent y sincronizado"
        )
    elif estado == "degraded":
        icono = ft.Icons.WARNING_AMBER_ROUNDED
        color_icono = ft.Colors.AMBER_400
        texto_label = "Red Lenta"
        color_texto = ft.Colors.AMBER_400 if modo_oscuro else ft.Colors.AMBER_800
        bg_color = ft.Colors.AMBER_900 if modo_oscuro else ft.Colors.AMBER_50
        borde_color = ft.Colors.AMBER_800 if modo_oscuro else ft.Colors.AMBER_300
        tt = f"Alta latencia detectada ({int(latencia_ms)} ms). Conexión Wi-Fi inestable."
    else:
        icono = ft.Icons.WIFI_OFF
        color_icono = ft.Colors.RED_400
        texto_label = "Sin conexión"
        color_texto = ft.Colors.RED_400 if modo_oscuro else ft.Colors.RED_700
        bg_color = ft.Colors.RED_900 if modo_oscuro else ft.Colors.RED_50
        borde_color = ft.Colors.RED_800 if modo_oscuro else ft.Colors.RED_300
        tt = mensaje or "Conexión interrumpida con el servidor. Reintentando enlace automáticamente..."

    for sem in [getattr(interfaz, "semaforo_conexion", None), getattr(interfaz, "semaforo_conexion_movil", None)]:
        if sem is not None and isinstance(sem.content, ft.Row) and len(sem.content.controls) >= 2:
            try:
                sem.content.controls[0].name = icono
                sem.content.controls[0].color = color_icono
                sem.content.controls[1].value = texto_label
                sem.content.controls[1].color = color_texto
                sem.bgcolor = bg_color
                sem.border = ft.Border.all(1, borde_color)
                sem.tooltip = tt
            except Exception:
                pass

    try:
        if getattr(interfaz, "page", None):
            interfaz.page.update()
    except Exception:
        pass

    if estado_previo != estado:
        if estado == "offline":
            try:
                snack = ft.SnackBar(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.WIFI_OFF, color=ft.Colors.WHITE, size=16),
                            ft.Text(
                                "Se perdió el enlace Wi-Fi con el servidor. Reintentando reconexión...",
                                color=ft.Colors.WHITE,
                                size=12,
                            ),
                        ],
                        spacing=8,
                    ),
                    bgcolor=ft.Colors.RED_800,
                    duration=5000,
                )
                interfaz.page.show_dialog(snack)
                interfaz.reproducir_sonido("error")
            except Exception:
                pass
        elif estado == "online" and estado_previo == "offline":
            try:
                snack = ft.SnackBar(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.WIFI, color=ft.Colors.WHITE, size=16),
                            ft.Text("Conexión restablecida con el servidor central.", color=ft.Colors.WHITE, size=12),
                        ],
                        spacing=8,
                    ),
                    bgcolor=ft.Colors.GREEN_800,
                    duration=3500,
                )
                interfaz.page.show_dialog(snack)
                interfaz.reproducir_sonido("exito")
                interfaz.actualizar_estado()
            except Exception:
                pass


def iniciar_heartbeat_red_daemon(interfaz: Any) -> None:
    """Inicia un hilo demonio en segundo plano para verificar periódicamente la conexión con la base central."""
    if getattr(interfaz, "_heartbeat_iniciado", False):
        return
    interfaz._heartbeat_iniciado = True
    interfaz._heartbeat_activo = True

    def _loop() -> None:
        while getattr(interfaz, "_heartbeat_activo", True):
            time.sleep(12)
            if not getattr(interfaz, "_heartbeat_activo", True) or not getattr(interfaz, "page", None):
                break
            try:
                t0 = time.monotonic()
                order_store = getattr(interfaz, "order_store", None)
                if not order_store:
                    break
                with sqlite3.connect(order_store.database_path, timeout=3) as conn:
                    conn.execute("SELECT 1").fetchone()
                lat_ms = (time.monotonic() - t0) * 1000.0
                nuevo_estado = "online" if lat_ms < 900.0 else "degraded"
                actualizar_estado_conexion_ui(interfaz, nuevo_estado, latencia_ms=lat_ms)
            except Exception as ex_ping:
                actualizar_estado_conexion_ui(interfaz, "offline", mensaje=f"Error de enlace: {ex_ping}")

    t = threading.Thread(target=_loop, name=f"HeartbeatRed_{id(interfaz)}", daemon=True)
    t.start()
