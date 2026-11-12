"""Diálogo modal para la gestión de Claves de API Externas (Exclusivo Master)."""

from typing import Any
import flet as ft
from ..theme import ROJO


def mostrar_dialogo_api_keys(interfaz: Any) -> None:
    """Abre la ventana modal para gestionar y emitir API Keys para integraciones externas."""
    if not interfaz.exigir_roles("master"):
        return

    nombre_input = ft.TextField(
        label="Nombre del Sistema / Cliente *",
        hint_text="Ej: ERP Central, Facturación B2B, App Externa...",
        expand=True,
        dense=True,
        autofocus=True,
    )

    rol_dropdown = ft.Dropdown(
        label="Rol asignado",
        value="operador",
        options=[
            ft.DropdownOption("operador", "Operador (Stock / Despacho)"),
            ft.DropdownOption("consulta", "Consulta (Solo lectura)"),
            ft.DropdownOption("administrador", "Administrador"),
        ],
        width=230,
        dense=True,
    )

    error_msg = ft.Text("", color=ft.Colors.RED_400, size=11, visible=False)

    # Contenedor para mostrar la clave recién creada (una sola vez)
    clave_generada_container = ft.Container(visible=False)

    lista_keys = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=260)

    def refrescar_lista():
        lista_keys.controls.clear()
        try:
            keys = interfaz.user_store.list_api_keys()
        except Exception as e:
            lista_keys.controls.append(
                ft.Text(f"Error al cargar claves: {e}", size=12, color=ft.Colors.RED_400)
            )
            if interfaz.page:
                interfaz.page.update()
            return

        if not keys:
            lista_keys.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.KEY_OFF, size=32, color=interfaz.secundario),
                            ft.Text("No hay claves de API registradas.", size=12, color=interfaz.secundario),
                            ft.Text("Genera una clave arriba para permitir conexiones externas seguras.", size=11, color=interfaz.secundario),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                )
            )
        else:
            for k in keys:
                k_hash = k.get("key_hash", "")
                c_name = k.get("client_name", "Desconocido")
                k_role = k.get("role", "operador")
                k_active = bool(k.get("active", 1))
                k_created = k.get("created_at", "")
                k_last_used = k.get("last_used", "") or "Nunca"

                estado_badge = ft.Container(
                    content=ft.Text(
                        "Activa" if k_active else "Revocada",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    bgcolor=ft.Colors.GREEN_700 if k_active else ft.Colors.RED_800,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=10,
                )

                role_badge = ft.Container(
                    content=ft.Text(
                        k_role.capitalize(),
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    bgcolor=ft.Colors.BLUE_GREY_700,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=10,
                )

                def revocar_accion(_e, kh=k_hash, nom=c_name):
                    def confirmar_revocar(_):
                        interfaz.user_store.revoke_api_key(kh)
                        interfaz.page.pop_dialog()
                        interfaz.notificar(f"Clave de '{nom}' revocada.")
                        refrescar_lista()

                    dlg_confirm = ft.AlertDialog(
                        title=ft.Row([ft.Icon(ft.Icons.WARNING, color=ROJO), ft.Text("Confirmar revocación")]),
                        content=ft.Text(f"¿Estás seguro de revocar la clave de '{nom}'? Los sistemas que la utilicen ya no podrán conectarse."),
                        actions=[
                            ft.Button("Sí, Revocar", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=confirmar_revocar),
                            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
                        ],
                    )
                    interfaz.page.show_dialog(dlg_confirm)

                item = ft.Container(
                    bgcolor=interfaz.superficie,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.VPN_KEY, size=20, color=ft.Colors.GREEN_400 if k_active else ft.Colors.RED_400),
                                    ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Text(c_name, weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                                                    estado_badge,
                                                    role_badge,
                                                ],
                                                spacing=6,
                                            ),
                                            ft.Text(
                                                f"Hash: {k_hash[:12]}... · Creada: {k_created} · Último uso: {k_last_used}",
                                                size=10,
                                                color=interfaz.secundario,
                                            ),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                ],
                                spacing=10,
                                expand=True,
                            ),
                            *(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.BLOCK,
                                        icon_size=18,
                                        tooltip="Revocar clave API",
                                        icon_color=ft.Colors.RED_400,
                                        on_click=revocar_accion,
                                    )
                                ]
                                if k_active
                                else []
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
                lista_keys.controls.append(item)

        if interfaz.page:
            interfaz.page.update()

    def crear_nueva_clave(_e: ft.Event) -> None:
        c_name = (nombre_input.value or "").strip()
        if not c_name:
            error_msg.value = "Debe indicar el nombre del sistema o cliente externo."
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()
            return

        error_msg.visible = False
        try:
            raw_key, _key_hash = interfaz.user_store.create_api_key(c_name, role=rol_dropdown.value or "operador")
            nombre_input.value = ""

            # Mostrar panel con la clave para copiar
            def copiar_click(_):
                if hasattr(interfaz, "copiar_al_portapapeles"):
                    interfaz.copiar_al_portapapeles(raw_key)
                interfaz.notificar("¡Clave API copiada al portapapeles!")

            clave_txt = ft.TextField(
                value=raw_key,
                read_only=True,
                dense=True,
                expand=True,
                text_size=12,
            )
            clave_generada_container.content = ft.Container(
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600),
                border=ft.Border.all(1, ft.Colors.GREEN_600),
                border_radius=8,
                padding=10,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_600, size=18),
                                ft.Text(f"Clave generada para '{c_name}':", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.GREEN_400),
                            ],
                            spacing=6,
                        ),
                        ft.Text(
                            "⚠️ Copia esta clave ahora. Por seguridad, está encriptada y no se volverá a mostrar completa.",
                            size=11,
                            color=interfaz.secundario,
                        ),
                        ft.Row(
                            [
                                clave_txt,
                                ft.Button(
                                    "Copiar",
                                    icon=ft.Icons.COPY,
                                    bgcolor=ft.Colors.GREEN_700,
                                    color=ft.Colors.WHITE,
                                    on_click=copiar_click,
                                ),
                            ],
                            spacing=6,
                        ),
                    ],
                    spacing=6,
                ),
            )
            clave_generada_container.visible = True
            interfaz.notificar(f"Clave API creada exitosamente para '{c_name}'.")
            refrescar_lista()
        except Exception as err:
            error_msg.value = f"Error al generar clave: {err}"
            error_msg.visible = True
            if interfaz.page:
                interfaz.page.update()

    refrescar_lista()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.VPN_KEY, color=ROJO),
                ft.Column(
                    [
                        ft.Text("Gestión de Claves API Externas", weight=ft.FontWeight.BOLD, size=16),
                        ft.Text("Autorizaciones de conexión externa (B2B / ERP / REST API)", size=11, color=interfaz.secundario),
                    ],
                    spacing=1,
                ),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=650,
            content=ft.Column(
                [
                    ft.Text("Emitir nueva clave de acceso", weight=ft.FontWeight.BOLD, size=13),
                    ft.Row(
                        [
                            nombre_input,
                            rol_dropdown,
                            ft.Button(
                                "Generar Clave",
                                icon=ft.Icons.ADD_LINK,
                                bgcolor=ROJO,
                                color=ft.Colors.WHITE,
                                on_click=crear_nueva_clave,
                            ),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    error_msg,
                    clave_generada_container,
                    ft.Divider(height=12),
                    ft.Text("Claves de integración registradas", weight=ft.FontWeight.BOLD, size=13),
                    lista_keys,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)
