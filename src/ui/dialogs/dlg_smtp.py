"""Diálogo modal para configuración del servidor de correo SMTP y alertas automáticas."""
from typing import Any
import flet as ft
from ...integrations.email_sender import (
    guardar_config_email,
    obtener_config_email,
    probar_conexion_smtp,
)
from ...alertas_programadas import enviar_resumen_ahora
from ..design import (
    campo_secreto_seguro,
    colores_de,
    fijar_ocupado,
    marcar_error,
    resolver_secreto,
    validar_entero_no_negativo,
)
from ..theme import ROJO


def mostrar_dialogo_configuracion_smtp(interfaz: Any) -> None:
    """Modal para configurar el servidor SMTP (cifrado) y las alertas automáticas programadas."""
    if not interfaz.exigir_roles("master"):
        return

    colores = colores_de(interfaz)
    cfg = obtener_config_email()
    cfg_alertas = cfg.get("alertas", {}) if isinstance(cfg.get("alertas"), dict) else {}
    clave_guardada = str(cfg.get("smtp_password", "") or "")

    servidor_input = ft.TextField(
        label="Servidor SMTP",
        value=cfg.get("smtp_servidor", ""),
        hint_text="ej: smtp.gmail.com, smtp.office365.com",
        prefix_icon=ft.Icons.DNS,
        expand=True,
        dense=True,
    )
    puerto_input = ft.TextField(
        label="Puerto",
        value=str(cfg.get("smtp_puerto", 587)),
        hint_text="587 o 465",
        keyboard_type=ft.KeyboardType.NUMBER,
        width=100,
        dense=True,
    )
    usuario_input = ft.TextField(
        label="Usuario / Correo remitente",
        value=cfg.get("smtp_usuario", ""),
        hint_text="ej: tu_cuenta@gmail.com",
        prefix_icon=ft.Icons.ACCOUNT_CIRCLE,
        dense=True,
    )
    pass_input = campo_secreto_seguro(
        "Contraseña o Token de Aplicación (se guarda cifrada con DPAPI)",
        clave_guardada,
        prefix_icon=ft.Icons.LOCK,
        dense=True,
    )
    tls_check = ft.Checkbox(label="Usar STARTTLS (Puerto 587)", value=cfg.get("smtp_usar_tls", True))
    ssl_check = ft.Checkbox(label="Usar SSL directo (Puerto 465)", value=cfg.get("smtp_usar_ssl", False))

    alerta_activo_check = ft.Checkbox(
        label="Activar envío diario automático de alertas (stock crítico y resumen de despachos)",
        value=bool(cfg_alertas.get("activo", False)),
    )
    alerta_hora_input = ft.TextField(
        label="Hora de envío (HH:MM)",
        value=str(cfg_alertas.get("hora", "18:00") or "18:00"),
        width=150,
        dense=True,
        prefix_icon=ft.Icons.SCHEDULE,
    )
    alerta_dest_input = ft.TextField(
        label="Destinatarios de alertas automáticas",
        value=str(cfg_alertas.get("destinatarios", "") or cfg.get("destinatarios_guardados", "")),
        hint_text="gerencia@empresa.com, compras@empresa.com",
        expand=True,
        dense=True,
        prefix_icon=ft.Icons.NOTIFICATIONS_ACTIVE,
    )

    resultado_txt = ft.Text("", size=11)
    btn_probar = ft.Button("Probar Conexión", icon=ft.Icons.NETWORK_CHECK)
    btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, bgcolor=ROJO, color=ft.Colors.WHITE)

    def probar_conexion(_e: ft.Event) -> None:
        puerto_val = validar_entero_no_negativo(puerto_input, "El puerto SMTP", minimo=1, maximo=65535)
        if puerto_val is None:
            interfaz.page.update()
            return
        cfg_prueba = {
            "smtp_servidor": servidor_input.value,
            "smtp_puerto": puerto_val,
            "smtp_usuario": usuario_input.value,
            "smtp_password": resolver_secreto(pass_input, clave_guardada),
            "smtp_usar_tls": tls_check.value,
            "smtp_usar_ssl": ssl_check.value,
        }
        resultado_txt.value = "Probando conexión con el servidor..."
        resultado_txt.color = colores.info
        fijar_ocupado(btn_probar, True, "Probando...")
        interfaz.page.update()

        try:
            ok, res_msg = probar_conexion_smtp(cfg_prueba)
        finally:
            fijar_ocupado(btn_probar, False)
        if ok:
            resultado_txt.value = f"✅ {res_msg}"
            resultado_txt.color = colores.exito
        else:
            resultado_txt.value = f"❌ {res_msg}"
            resultado_txt.color = colores.error
        interfaz.page.update()

    def enviar_resumen_manual(_e: ft.Event) -> None:
        dest_str = (alerta_dest_input.value or "").strip() or (usuario_input.value or "").strip()
        dest_list = [d.strip() for d in dest_str.replace(";", ",").split(",") if d.strip()]
        ok, msg = enviar_resumen_ahora(destinatarios=dest_list or None)
        resultado_txt.value = f"{'✅' if ok else '❌'} {msg}"
        resultado_txt.color = colores.exito if ok else colores.error
        interfaz.page.update()

    def guardar(_e: ft.Event) -> None:
        puerto_val = validar_entero_no_negativo(puerto_input, "El puerto SMTP", minimo=1, maximo=65535)
        if puerto_val is None:
            interfaz.page.update()
            return
        marcar_error(puerto_input, None)
        fijar_ocupado(btn_guardar, True, "Guardando...")
        try:
            clave_final = resolver_secreto(pass_input, clave_guardada)
            cfg_actualizada = {
                **cfg,
                "smtp_servidor": (servidor_input.value or "").strip(),
                "smtp_puerto": puerto_val,
                "smtp_usuario": (usuario_input.value or "").strip(),
                "smtp_password": clave_final,
                "smtp_usar_tls": bool(tls_check.value),
                "smtp_usar_ssl": bool(ssl_check.value),
                "alertas": {
                    **cfg_alertas,
                    "activo": bool(alerta_activo_check.value),
                    "hora": (alerta_hora_input.value or "18:00").strip() or "18:00",
                    "destinatarios": (alerta_dest_input.value or "").strip(),
                    "incluir_stock_critico": True,
                    "incluir_resumen_diario": True,
                },
            }
            guardar_config_email(cfg_actualizada)
            order_store = getattr(interfaz, "order_store", None)
            if order_store and hasattr(order_store, "registrar_auditoria"):
                usr_nom = getattr(getattr(interfaz, "usuario_actual", None), "username", "Master")
                order_store.registrar_auditoria(
                    usr_nom,
                    "CONFIG_SMTP_ACTUALIZADA",
                    f"Servidor: {cfg_actualizada['smtp_servidor']}:{puerto_val}",
                )
            interfaz.page.pop_dialog()
            interfaz.notificar("Configuración SMTP (con clave cifrada) y alertas programadas guardadas correctamente.")
        finally:
            fijar_ocupado(btn_guardar, False)

    btn_probar.on_click = probar_conexion
    btn_guardar.on_click = guardar

    ancho_dlg = interfaz.ancho_adaptable(540) if hasattr(interfaz, "ancho_adaptable") else 540
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.SETTINGS, color=colores.secundario, size=20),
                ft.Text("Servidor de Correo (SMTP) y Alertas Programadas", weight=ft.FontWeight.BOLD, size=15),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=ancho_dlg,
            content=ft.Column(
                [
                    ft.Text(
                        "Las credenciales SMTP se almacenan cifradas localmente (Windows DPAPI / Fernet) "
                        "o mediante la variable de entorno STOCKAGENT_SMTP_PASSWORD.",
                        size=11,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=8),
                    ft.Row([servidor_input, puerto_input], spacing=8),
                    usuario_input,
                    pass_input,
                    ft.Row([tls_check, ssl_check], spacing=8),
                    ft.Divider(height=10),
                    ft.Text("Alertas Automáticas por Correo:", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    alerta_activo_check,
                    ft.Row([alerta_hora_input, alerta_dest_input], spacing=8),
                    ft.Row(
                        [
                            ft.TextButton(
                                "Enviar resumen de prueba ahora",
                                icon=ft.Icons.SEND_TIME_EXTENSION,
                                on_click=enviar_resumen_manual,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                    resultado_txt,
                ],
                tight=True,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
        actions=[
            btn_probar,
            btn_guardar,
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
