"""Diálogo modal para la gestión de API REST, Claves de Integración y Sesiones (Master)."""

from __future__ import annotations

from typing import Any

import flet as ft

from ...server_app import PUERTO_WEB_DEFAULT, obtener_ip_local, obtener_ip_tailscale
from ..theme import ROJO, SECUNDARIO
from .api_panel_tabs import (
    construir_estado_vacio_api,
    construir_tab_docs_estado,
    construir_tab_sesiones,
    formatear_timestamp_api,
)

_formatear_timestamp = formatear_timestamp_api


def mostrar_dialogo_api_master(interfaz: Any, tab_inicial: int = 0) -> None:
    """Abre el panel maestro de API REST: claves API, documentación Swagger y sesiones activas."""
    if not interfaz.exigir_roles("master"):
        return

    user_store = getattr(interfaz, "user_store", None)
    if not user_store:
        interfaz.notificar("❌ No se pudo acceder al almacén de usuarios.")
        return

    es_oscuro = getattr(interfaz, "modo_oscuro", True)
    bg_activo = ROJO
    bg_inactivo = ft.Colors.BLUE_GREY_800 if es_oscuro else ft.Colors.BLUE_GREY_100
    texto_color = getattr(interfaz, "texto", ft.Colors.WHITE if es_oscuro else ft.Colors.BLACK)

    input_cliente = ft.TextField(
        label="Nombre del Cliente / Sistema Externo *",
        hint_text="Ej: ERP Logística, Facturación B2B, App Externa",
        expand=True,
        dense=True,
    )
    dd_rol = ft.Dropdown(
        label="Rol API",
        value="operador",
        options=[
            ft.DropdownOption("operador", "Operador (Despacho / Stock)"),
            ft.DropdownOption("consulta", "Consulta (Solo lectura)"),
            ft.DropdownOption("administrador", "Administrador (Completo catálogo)"),
            ft.DropdownOption("master", "Master (Acceso irrestricto)"),
        ],
        width=230,
        dense=True,
    )
    banner_nueva_clave = ft.Container(visible=False)
    lista_claves = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=260)
    total_keys_txt = ft.Text("0 claves registradas", size=12, color=SECUNDARIO)

    def refrescar_lista_claves() -> None:
        try:
            keys = user_store.list_api_keys()
        except Exception as exc:
            lista_claves.controls = [ft.Text(f"Error al cargar claves: {exc}", color=ft.Colors.RED_400)]
            interfaz.page.update()
            return

        total_keys_txt.value = f"{len(keys)} clave(s) registrada(s)"
        if not keys:
            lista_claves.controls = [
                construir_estado_vacio_api(
                    ft.Icons.VPN_KEY_OFF,
                    "No hay claves API generadas aún.",
                    "Genera una clave arriba para conectar sistemas externos.",
                )
            ]
            interfaz.page.update()
            return

        items = []
        for k in keys:
            k_hash = k.get("key_hash", "")
            c_name = k.get("client_name", "Desconocido")
            rol_k = k.get("role", "operador")
            activo = bool(k.get("active", 1))
            creado = _formatear_timestamp(k.get("created_at"))
            ultimo = _formatear_timestamp(k.get("last_used"))

            badge_estado = ft.Container(
                content=ft.Text("ACTIVA" if activo else "REVOCADA", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.GREEN_700 if activo else ft.Colors.RED_800,
                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                border_radius=4,
            )
            badge_rol = ft.Container(
                content=ft.Text(rol_k.upper(), size=10, weight=ft.FontWeight.W_500, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.BLUE_GREY_700,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
            )

            acciones = [
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="Eliminar clave permanentemente",
                    icon_color=ft.Colors.RED_400,
                    icon_size=18,
                    on_click=lambda _e, h=k_hash: ejecutar_eliminar_clave(h),
                )
            ]
            if activo:
                acciones.insert(
                    0,
                    ft.Button(
                        "Revocar",
                        icon=ft.Icons.BLOCK,
                        style=ft.ButtonStyle(color=ft.Colors.RED_400, padding=ft.Padding.symmetric(horizontal=8, vertical=2)),
                        on_click=lambda _e, h=k_hash: ejecutar_revocar_clave(h),
                    ),
                )

            items.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.KEY if activo else ft.Icons.KEY_OFF, color=ft.Colors.AMBER_400 if activo else SECUNDARIO, size=24),
                            ft.Column(
                                [
                                    ft.Row([ft.Text(c_name, weight=ft.FontWeight.BOLD, size=13), badge_rol, badge_estado], spacing=8),
                                    ft.Text(f"Hash: {k_hash[:14]}... | Creada: {creado} | Último uso: {ultimo}", size=11, color=SECUNDARIO),
                                ],
                                expand=True,
                                spacing=2,
                            ),
                            ft.Row(acciones, spacing=4),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.Padding.all(10),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, texto_color)),
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.03, texto_color),
                )
            )
        lista_claves.controls = items
        interfaz.page.update()

    def copiar_al_portapapeles(texto: str) -> None:
        try:
            interfaz.page.set_clipboard(texto)
            interfaz.notificar("📋 Clave API copiada al portapapeles.")
        except Exception:
            interfaz.notificar("⚠️ Selecciona el texto manualmente para copiar.")

    def ejecutar_crear_clave(_e: ft.Event) -> None:
        cliente = (input_cliente.value or "").strip()
        if not cliente:
            interfaz.notificar("⚠️ Ingrese un nombre descriptivo para el cliente o sistema externo.")
            return
        try:
            raw_key, _key_hash = user_store.create_api_key(client_name=cliente, role=dd_rol.value or "operador")
        except Exception as exc:
            interfaz.notificar(f"❌ Error al crear clave API: {exc}")
            return

        input_cliente.value = ""
        banner_nueva_clave.visible = True
        banner_nueva_clave.content = ft.Container(
            content=ft.Column(
                [
                    ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=20), ft.Text("¡Clave API Generada Exitosamente!", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)], spacing=6),
                    ft.Text(
                        "⚠️ COPIA ESTA CLAVE AHORA. Por motivos de seguridad de cifrado, nunca volverá a mostrarse completa:",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.AMBER_300,
                    ),
                    ft.Row(
                        [
                            ft.TextField(value=raw_key, read_only=True, expand=True, dense=True, text_style=ft.TextStyle(font_family="monospace", size=12)),
                            ft.Button("Copiar", icon=ft.Icons.COPY, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=lambda _ev: copiar_al_portapapeles(raw_key)),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding.all(12),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.GREEN),
            border=ft.Border.all(1, ft.Colors.GREEN_700),
            border_radius=8,
        )
        refrescar_lista_claves()
        interfaz.notificar("✅ Clave API generada con éxito.")

    def ejecutar_revocar_clave(k_hash: str) -> None:
        try:
            if user_store.revoke_api_key(k_hash):
                interfaz.notificar("🔒 Clave API revocada. No se aceptarán más peticiones con ella.")
                refrescar_lista_claves()
            else:
                interfaz.notificar("❌ No se pudo revocar la clave.")
        except Exception as exc:
            interfaz.notificar(f"❌ Error al revocar clave: {exc}")

    def ejecutar_eliminar_clave(k_hash: str) -> None:
        try:
            if user_store.delete_api_key(k_hash):
                interfaz.notificar("🗑️ Clave eliminada del registro.")
                refrescar_lista_claves()
            else:
                interfaz.notificar("❌ No se pudo eliminar la clave.")
        except Exception as exc:
            interfaz.notificar(f"❌ Error al eliminar clave: {exc}")

    vista_keys = ft.Column(
        [
            ft.Text(
                "Emite claves API estáticas (sk_live_...) para autenticar clientes B2B, ERPs o lectores externos mediante encabezado X-API-Key.",
                size=12,
                color=SECUNDARIO,
            ),
            ft.Row([input_cliente, dd_rol, ft.Button("Generar Clave API", icon=ft.Icons.KEY, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=ejecutar_crear_clave)], spacing=8, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            banner_nueva_clave,
            ft.Divider(),
            ft.Row([ft.Text("Claves Registradas", weight=ft.FontWeight.BOLD, size=13), total_keys_txt], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            lista_claves,
        ],
        spacing=8,
    )
    vista_docs = construir_tab_docs_estado(interfaz, texto_color)
    vista_sesiones, refrescar_lista_sesiones = construir_tab_sesiones(interfaz, user_store, texto_color)

    btn_tab_keys = ft.Button("Claves de API (Keys)", icon=ft.Icons.VPN_KEY)
    btn_tab_docs = ft.Button("Documentación y Estado", icon=ft.Icons.CODE)
    btn_tab_sesiones = ft.Button("Sesiones Conectadas", icon=ft.Icons.DEVICES)

    def cambiar_tab(indice: int) -> None:
        for idx, (vista, btn) in enumerate(((vista_keys, btn_tab_keys), (vista_docs, btn_tab_docs), (vista_sesiones, btn_tab_sesiones))):
            vista.visible = (indice == idx)
            btn.bgcolor = bg_activo if indice == idx else bg_inactivo
            btn.color = ft.Colors.WHITE if indice == idx else texto_color
        if indice == 0:
            refrescar_lista_claves()
        elif indice == 2:
            refrescar_lista_sesiones()
        interfaz.page.update()

    btn_tab_keys.on_click = lambda _e: cambiar_tab(0)
    btn_tab_docs.on_click = lambda _e: cambiar_tab(1)
    btn_tab_sesiones.on_click = lambda _e: cambiar_tab(2)

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.API, color=ROJO, size=24), ft.Text("API REST y Servicios de Integración", weight=ft.FontWeight.BOLD, size=16)], spacing=8),
        content=ft.Container(
            width=720,
            content=ft.Column(
                [ft.Row([btn_tab_keys, btn_tab_docs, btn_tab_sesiones], spacing=8), ft.Divider(), vista_keys, vista_docs, vista_sesiones],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
    cambiar_tab(tab_inicial)


def mostrar_gestion_api_keys(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Acceso directo a la pestaña de Gestión de Claves API."""
    mostrar_dialogo_api_master(interfaz, tab_inicial=0)


def mostrar_estado_api(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Acceso directo a la pestaña de Estado y Documentación API."""
    mostrar_dialogo_api_master(interfaz, tab_inicial=1)


def mostrar_sesiones_api(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Acceso directo a la pestaña de Sesiones API Activas."""
    mostrar_dialogo_api_master(interfaz, tab_inicial=2)


__all__ = [
    "PUERTO_WEB_DEFAULT",
    "_formatear_timestamp",
    "mostrar_dialogo_api_master",
    "mostrar_estado_api",
    "mostrar_gestion_api_keys",
    "mostrar_sesiones_api",
    "obtener_ip_local",
    "obtener_ip_tailscale",
]
