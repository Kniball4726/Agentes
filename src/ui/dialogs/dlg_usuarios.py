"""Diálogo modal para la gestión de usuarios (administración)."""
from typing import Any
import flet as ft
from ...user_store import USER_ROLES, User, UserStoreError
from ..theme import ROJO


def mostrar_dialogo_gestion_usuarios(interfaz: Any) -> None:
    """Abre la ventana modal para administrar usuarios, roles y contraseñas."""
    if not interfaz.exigir_roles("administrador"):
        return

    nuevo_usuario = ft.TextField(label="Nombre de usuario *", expand=True)
    nuevo_nombre = ft.TextField(
        label="Nombre y apellido (identificador en documentos)",
        hint_text="Ej: Juan Pérez",
        expand=True,
    )
    nuevo_email = ft.TextField(
        label="Correo electrónico (opcional)",
        hint_text="Ej: juan@ultratech.com",
        expand=True,
    )
    nueva_clave = ft.TextField(
        label="Contraseña (mínimo 10 caracteres) *",
        password=True,
        can_reveal_password=True,
        expand=True,
    )
    es_master = bool(interfaz.usuario_actual and interfaz.usuario_actual.role == "master")
    roles_creables = ["administrador", "operador", "consulta"] if es_master else ["operador", "consulta"]
    nuevo_rol = ft.Dropdown(
        label="Rol",
        value="consulta",
        options=[
            ft.DropdownOption(key=role, text=role.capitalize())
            for role in roles_creables
        ],
        width=180,
    )
    mensaje = ft.Text(color=ft.Colors.RED_400, size=12)
    usuarios = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=260)
    crear_boton = ft.Button(
        "Crear usuario",
        icon=ft.Icons.PERSON_ADD,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
    )
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.MANAGE_ACCOUNTS, color=ROJO), ft.Text("Gestión de usuarios", weight=ft.FontWeight.BOLD)]),
        content=ft.Container(
            width=620,
            content=ft.Column(
                [
                    ft.Text("Registrar nuevo usuario", weight=ft.FontWeight.BOLD, size=13),
                    ft.Row([nuevo_usuario, nuevo_nombre], spacing=8),
                    ft.Row([nuevo_email, nueva_clave], spacing=8),
                    ft.Row([nuevo_rol, crear_boton], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    mensaje,
                    ft.Divider(),
                    ft.Text("Usuarios existentes", weight=ft.FontWeight.BOLD, size=13),
                    usuarios,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())
        ],
    )

    def abrir_editar_usuario(u_target: User) -> None:
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
                actualizar_lista()
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

    def actualizar_lista() -> None:
        usuarios.controls.clear()
        actual = interfaz.usuario_actual
        actual_es_master = bool(actual and actual.role == "master")
        bloqueados = (
            interfaz.user_store.list_locked_usernames()
            if hasattr(interfaz.user_store, "list_locked_usernames")
            else set()
        )
        roles_asignables = (
            ["administrador", "operador", "consulta"]
            if actual_es_master
            else ["operador", "consulta"]
        )
        try:
            lista_usuarios = interfaz.user_store.list_users(include_master=actual_es_master)
        except TypeError:
            lista_usuarios = interfaz.user_store.list_users()
        for usuario in lista_usuarios:
            if not actual_es_master and usuario.role == "master":
                continue
            es_propio = actual is not None and usuario.id == actual.id
            es_target_master = usuario.role == "master"
            es_target_admin = usuario.role == "administrador"
            no_puede_editar = es_propio or es_target_master or (es_target_admin and not actual_es_master)
            esta_bloqueado = usuario.username in bloqueados

            selector_rol = ft.Dropdown(
                value=usuario.role,
                options=[
                    ft.DropdownOption(key=role, text=role.capitalize())
                    for role in (USER_ROLES if es_target_master else roles_asignables)
                ],
                width=135,
                disabled=no_puede_editar,
            )
            boton_estado = ft.TextButton(
                "Desactivar" if usuario.active else "Activar",
                on_click=lambda _e, user_id=usuario.id, active=not usuario.active: cambiar_estado(
                    user_id, active
                ),
                disabled=no_puede_editar,
            )
            boton_editar = ft.IconButton(
                icon=ft.Icons.EDIT_OUTLINED,
                tooltip="Editar nombre y correo",
                icon_size=18,
                disabled=es_target_master and not actual_es_master,
                on_click=lambda _e, u=usuario: abrir_editar_usuario(u),
            )
            boton_reset = ft.IconButton(
                icon=ft.Icons.LOCK_RESET,
                tooltip="Restablecer contraseña de este usuario",
                icon_size=18,
                disabled=no_puede_editar,
                on_click=lambda _e, u=usuario: abrir_reset_clave(u),
            )
            boton_desbloquear = (
                ft.IconButton(
                    icon=ft.Icons.LOCK_OPEN,
                    tooltip="Desbloquear cuenta bloqueada por intentos fallidos",
                    icon_color=ft.Colors.AMBER_400,
                    icon_size=18,
                    on_click=lambda _e, uname=usuario.username: desbloquear_cuenta(uname),
                )
                if esta_bloqueado
                else ft.Container()
            )
            selector_rol.on_select = lambda _e, user_id=usuario.id, dropdown=selector_rol: cambiar_rol(
                user_id, dropdown.value or ""
            )

            nombre_principal = usuario.nombre_identificador
            sub_info = f"@{usuario.username}"
            if usuario.email:
                sub_info += f" · {usuario.email}"
            if not usuario.active:
                sub_info += " · (Inactivo)"
            if esta_bloqueado:
                sub_info += " · [BLOQUEADO]"

            info_col = ft.Column(
                [
                    ft.Text(
                        nombre_principal,
                        weight=ft.FontWeight.W_500,
                        size=13,
                        color=ft.Colors.AMBER_400 if esta_bloqueado else interfaz.texto,
                    ),
                    ft.Text(
                        sub_info,
                        size=11,
                        color=ft.Colors.GREY_400 if not esta_bloqueado else ft.Colors.AMBER_300,
                    ),
                ],
                spacing=1,
                expand=True,
            )

            usuarios.controls.append(
                ft.Row(
                    [
                        info_col,
                        selector_rol,
                        boton_desbloquear,
                        boton_editar,
                        boton_reset,
                        boton_estado,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

    def desbloquear_cuenta(uname: str) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        interfaz.user_store.unlock_user(uname)
        try:
            interfaz.order_store.registrar_auditoria(
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Admin",
                accion="DESBLOQUEO_USUARIO",
                detalle=f"Cuenta '{uname}' desbloqueada manualmente",
            )
        except Exception:
            pass
        mensaje.value = f"Cuenta '{uname}' desbloqueada."
        actualizar_lista()
        interfaz.page.update()

    def abrir_reset_clave(u_target: User) -> None:
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

    def cambiar_rol(user_id: int, role: str) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        try:
            interfaz.user_store.update_role(
                user_id,
                role,
                updater_role=interfaz.usuario_actual.role if interfaz.usuario_actual else None,
            )
            mensaje.value = ""
        except (ValueError, UserStoreError) as error:
            mensaje.value = str(error)
        actualizar_lista()
        interfaz.page.update()

    def cambiar_estado(user_id: int, active: bool) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        try:
            interfaz.user_store.set_active(
                user_id,
                active,
                updater_role=interfaz.usuario_actual.role if interfaz.usuario_actual else None,
            )
            mensaje.value = ""
        except UserStoreError as error:
            mensaje.value = str(error)
        actualizar_lista()
        interfaz.page.update()

    def crear_usuario(_evento: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador"):
            return
        try:
            interfaz.user_store.create_user(
                nuevo_usuario.value or "",
                nueva_clave.value or "",
                nuevo_rol.value or "",
                creator_role=interfaz.usuario_actual.role if interfaz.usuario_actual else None,
                nombre=nuevo_nombre.value or "",
                email=nuevo_email.value or "",
            )
        except (ValueError, UserStoreError) as error:
            mensaje.value = str(error)
        else:
            nuevo_usuario.value = ""
            nuevo_nombre.value = ""
            nuevo_email.value = ""
            nueva_clave.value = ""
            mensaje.value = "Usuario creado con éxito."
        actualizar_lista()
        interfaz.page.update()

    crear_boton.on_click = crear_usuario
    actualizar_lista()
    interfaz.page.show_dialog(dialogo)
