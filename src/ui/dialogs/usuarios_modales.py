"""Componentes de tarjeta y sub-modales de edición/reseteo para gestión de usuarios."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ...auth import USER_ROLES, User, UserStoreError
from ..design import es_viewport_estrecho, tono_legible
from ..theme import ROJO


def construir_tarjeta_usuario(
    interfaz: Any,
    usuario: User,
    *,
    actual: User | None,
    actual_es_master: bool,
    roles_asignables: list[str],
    esta_bloqueado: bool,
    on_cambiar_rol: Callable[[int, str], None],
    on_cambiar_estado: Callable[[int, bool], None],
    on_editar: Callable[[User], None],
    on_reset_clave: Callable[[User], None],
    on_desbloquear: Callable[[str], None],
) -> ft.Control:
    """Renderiza una fila o tarjeta responsiva con acciones para un usuario del sistema."""
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    es_propio = actual is not None and usuario.id == actual.id
    es_target_master = usuario.role == "master"
    es_target_admin = usuario.role == "administrador"
    no_puede_editar = es_propio or es_target_master or (es_target_admin and not actual_es_master)

    selector_rol = ft.Dropdown(
        value=usuario.role,
        options=[
            ft.DropdownOption(key=role, text=role.capitalize())
            for role in (USER_ROLES if es_target_master else roles_asignables)
        ],
        width=135,
        disabled=no_puede_editar,
    )
    selector_rol.on_select = lambda _e, user_id=usuario.id, dropdown=selector_rol: on_cambiar_rol(
        user_id, dropdown.value or ""
    )

    boton_estado = ft.TextButton(
        "Desactivar" if usuario.active else "Activar",
        on_click=lambda _e, user_id=usuario.id, active=not usuario.active: on_cambiar_estado(
            user_id, active
        ),
        disabled=no_puede_editar,
    )
    boton_editar = ft.IconButton(
        icon=ft.Icons.EDIT_OUTLINED,
        tooltip="Editar nombre y correo",
        icon_size=18,
        disabled=es_target_master and not actual_es_master,
        on_click=lambda _e, u=usuario: on_editar(u),
    )
    boton_reset = ft.IconButton(
        icon=ft.Icons.LOCK_RESET,
        tooltip="Restablecer contraseña de este usuario",
        icon_size=18,
        disabled=no_puede_editar,
        on_click=lambda _e, u=usuario: on_reset_clave(u),
    )
    boton_desbloquear = (
        ft.IconButton(
            icon=ft.Icons.LOCK_OPEN,
            tooltip="Desbloquear cuenta bloqueada por intentos fallidos",
            icon_color=ft.Colors.AMBER_400,
            icon_size=18,
            on_click=lambda _e, uname=usuario.username: on_desbloquear(uname),
        )
        if esta_bloqueado
        else ft.Container()
    )

    sub_info = f"@{usuario.username}"
    if usuario.email:
        sub_info += f" · {usuario.email}"
    if not usuario.active:
        sub_info += " · (Inactivo)"
    if esta_bloqueado:
        sub_info += " · [BLOQUEADO]"

    c_ambar = tono_legible("AMBER", es_oscuro)
    info_col = ft.Column(
        [
            ft.Text(
                usuario.nombre_identificador,
                weight=ft.FontWeight.W_500,
                size=13,
                color=c_ambar if esta_bloqueado else interfaz.texto,
            ),
            ft.Text(
                sub_info,
                size=11,
                color=interfaz.secundario if not esta_bloqueado else c_ambar,
            ),
        ],
        spacing=1,
        expand=True,
    )

    if es_viewport_estrecho(interfaz, umbral=620.0):
        info_col.expand = False
        return ft.Container(
            bgcolor=interfaz.superficie,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=8,
            content=ft.Column(
                [
                    info_col,
                    ft.Row(
                        [selector_rol, boton_desbloquear, boton_editar, boton_reset, boton_estado],
                        spacing=4,
                        wrap=True,
                        run_spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=6,
                tight=True,
            ),
        )

    return ft.Row(
        [info_col, selector_rol, boton_desbloquear, boton_editar, boton_reset, boton_estado],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def mostrar_modal_editar_usuario(
    interfaz: Any,
    u_target: User,
    on_guardado: Callable[[], None],
) -> None:
    """Despliega el sub-modal para editar nombre identificador y correo de un usuario."""
    actual = interfaz.usuario_actual
    actual_es_master = bool(actual and actual.role == "master")
    if not actual_es_master and u_target.role in ("master", "administrador") and u_target.id != (actual.id if actual else 0):
        interfaz.notificar("No tienes permisos para editar a otro administrador.")
        return

    edit_nombre = ft.TextField(
        label="Nombre y apellido / Identificador en documentos",
        value=u_target.nombre,
        hint_text="Ej: Juan Pérez",
        autofocus=True,
    )
    edit_email = ft.TextField(
        label="Correo electrónico",
        value=u_target.email,
        hint_text="Ej: usuario@ultratech.com",
    )
    err_edit = ft.Text("", color=ft.Colors.RED_400, size=12)

    def guardar_edicion(_ev: ft.Event) -> None:
        try:
            interfaz.user_store.update_user_info(
                u_target.id,
                nombre=edit_nombre.value or "",
                email=edit_email.value or "",
                updater_role=interfaz.usuario_actual.role if interfaz.usuario_actual else None,
            )
            if interfaz.usuario_actual and interfaz.usuario_actual.id == u_target.id:
                interfaz.usuario_actual = interfaz.user_store.get_user(u_target.id)
                interfaz.construir()
            interfaz.page.pop_dialog()
            interfaz.notificar(f"Datos del usuario '{u_target.username}' actualizados.")
            on_guardado()
        except (ValueError, UserStoreError) as err:
            err_edit.value = str(err)
            interfaz.page.update()

    dlg_edit = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Editar usuario: @{u_target.username}"),
        content=ft.Container(
            width=420,
            content=ft.Column(
                [
                    ft.Text(f"Rol: {u_target.role.capitalize()}", size=12, color=interfaz.secundario),
                    edit_nombre,
                    edit_email,
                    err_edit,
                ],
                tight=True,
                spacing=10,
            ),
        ),
        actions=[
            ft.Button("Guardar", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=guardar_edicion),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dlg_edit)


def mostrar_modal_reset_clave(interfaz: Any, u_target: User) -> None:
    """Despliega el sub-modal para restablecer la contraseña temporal de un usuario."""
    actual = interfaz.usuario_actual
    actual_es_master = bool(actual and actual.role == "master")
    if not actual_es_master and u_target.role in ("master", "administrador"):
        interfaz.notificar("Solo el usuario master puede restablecer la clave de un administrador.")
        return

    clave_temp = ft.TextField(
        label=f"Nueva contraseña para {u_target.username} (mín. 10 caracteres)",
        password=True,
        can_reveal_password=True,
        autofocus=True,
    )
    forzar_check = ft.Checkbox(
        label="Exigir que el usuario la cambie en su próximo inicio de sesión",
        value=True,
    )
    err_txt = ft.Text("", color=ft.Colors.RED_400, size=12)

    def confirmar_reset(_ev: ft.Event) -> None:
        try:
            interfaz.user_store.reset_password(
                u_target.id,
                clave_temp.value or "",
                updater_role=interfaz.usuario_actual.role if interfaz.usuario_actual else None,
                must_change=bool(forzar_check.value),
            )
            interfaz.order_store.registrar_auditoria(
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Admin",
                accion="RESET_CLAVE",
                detalle=f"Contraseña restablecida para el usuario '{u_target.username}'",
            )
            interfaz.page.pop_dialog()
            interfaz.notificar(f"Contraseña de '{u_target.username}' restablecida y cuenta desbloqueada.")
        except (ValueError, UserStoreError) as err:
            err_txt.value = str(err)
            interfaz.page.update()

    dlg_reset = ft.AlertDialog(
        modal=True,
        title=ft.Text(f"Restablecer clave: {u_target.username}"),
        content=ft.Container(
            width=400,
            content=ft.Column([clave_temp, forzar_check, err_txt], tight=True, spacing=10),
        ),
        actions=[
            ft.Button("Restablecer", bgcolor=ROJO, color=ft.Colors.WHITE, on_click=confirmar_reset),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dlg_reset)
