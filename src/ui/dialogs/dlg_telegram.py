"""Diálogo de Configuración de Alertas Proactivas por Telegram Bot."""

from typing import Any
import flet as ft

from ...telegram_notifier import (
    cargar_config_telegram,
    enviar_mensaje_telegram,
    guardar_config_telegram,
)
from ..theme import ROJO


def mostrar_dialogo_configuracion_telegram(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Ventana para configurar el Bot de Telegram y las alertas proactivas."""
    if not interfaz.exigir_roles("master"):
        return

    cfg = cargar_config_telegram()

    input_token = ft.TextField(
        label="Telegram Bot Token",
        value=cfg.get("bot_token", ""),
        hint_text="Ej: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
        password=True,
        can_reveal_password=True,
        dense=True,
        expand=True,
    )

    input_chat_id = ft.TextField(
        label="Chat ID / ID de Grupo o Canal",
        value=cfg.get("chat_id", ""),
        hint_text="Ej: -1001234567890 o tu ID personal",
        dense=True,
        expand=True,
    )

    switch_activo = ft.Switch(
        label="Habilitar envío de alertas por Telegram",
        value=cfg.get("activo", False),
    )

    chk_quiebres = ft.Checkbox(
        label="Notificar quiebres de stock y existencias críticas",
        value=cfg.get("notificar_quiebres", True),
    )

    chk_seguridad = ft.Checkbox(
        label="Notificar bloqueos de cuentas por seguridad (5 intentos fallidos)",
        value=cfg.get("notificar_seguridad", True),
    )

    chk_cierre = ft.Checkbox(
        label="Enviar resumen formal al completar el Cierre de Jornada",
        value=cfg.get("notificar_cierre", True),
    )

    texto_estado = ft.Text("", size=12)

    def probar_conexion(_e: ft.Event | None = None) -> None:
        tok = (input_token.value or "").strip()
        cid = (input_chat_id.value or "").strip()
        if not tok or not cid:
            texto_estado.value = "⚠️ Debes ingresar el Bot Token y el Chat ID para probar la conexión."
            texto_estado.color = ft.Colors.AMBER_400
            interfaz.page.update()
            return

        test_cfg = {
            "bot_token": tok,
            "chat_id": cid,
            "activo": True,
        }
        texto_estado.value = "Enviando mensaje de prueba a Telegram..."
        texto_estado.color = interfaz.secundario
        interfaz.page.update()

        msg = (
            "🤖 <b>StockAgent - Prueba de Conexión Exitosa</b>\n\n"
            "El bot de alertas de Telegram se ha vinculado correctamente con tu servidor de depósito.\n"
            "Recibirás notificaciones automáticas de quiebres, seguridad y cierres de jornada."
        )
        exito, detalle = enviar_mensaje_telegram(msg, config=test_cfg, sync=True)
        if exito:
            texto_estado.value = "✅ ¡Conexión exitosa! Revisa el mensaje recibido en Telegram."
            texto_estado.color = ft.Colors.GREEN_400
        else:
            texto_estado.value = f"❌ {detalle}"
            texto_estado.color = ft.Colors.RED_400
        interfaz.page.update()

    def guardar(_e: ft.Event | None = None) -> None:
        nueva_cfg = {
            "bot_token": (input_token.value or "").strip(),
            "chat_id": (input_chat_id.value or "").strip(),
            "activo": bool(switch_activo.value),
            "notificar_quiebres": bool(chk_quiebres.value),
            "notificar_seguridad": bool(chk_seguridad.value),
            "notificar_cierre": bool(chk_cierre.value),
        }
        guardar_config_telegram(nueva_cfg)
        interfaz.page.pop_dialog()
        interfaz.notificar("Configuración de alertas de Telegram guardada con éxito.")

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.SEND, color=ROJO, size=24),
                ft.Text("Alertas Proactivas por Telegram", size=17, weight=ft.FontWeight.BOLD),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=500,
            content=ft.Column(
                [
                    ft.Text(
                        "Recibe notificaciones automáticas en tiempo real directamente en tu celular o grupo de trabajo "
                        "creando un bot gratuito con @BotFather en Telegram.",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=12, color=interfaz.borde),
                    ft.Row([switch_activo]),
                    ft.Row([input_token]),
                    ft.Row([input_chat_id]),
                    ft.Divider(height=12, color=interfaz.borde),
                    ft.Text("EVENTOS A NOTIFICAR", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
                    chk_quiebres,
                    chk_seguridad,
                    chk_cierre,
                    ft.Container(height=4),
                    texto_estado,
                ],
                spacing=8,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton(
                "Probar Conexión",
                icon=ft.Icons.SEND,
                on_click=probar_conexion,
            ),
            ft.FilledButton(
                "Guardar",
                icon=ft.Icons.SAVE,
                style=ft.ButtonStyle(bgcolor=ROJO, color=ft.Colors.WHITE),
                on_click=guardar,
            ),
            ft.TextButton("Cancelar", on_click=lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    interfaz.page.show_dialog(dialogo)
