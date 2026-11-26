"""Diálogo modal para la gestión de usuarios (administración)."""

from __future__ import annotations

from typing import Any

import flet as ft

from ...auth import User, UserStoreError
from ..design import colores_de, confirmar_accion_destructiva, fijar_ocupado, grilla_tarjetas_responsiva, marcar_error
from ..theme import ROJO
from .usuarios_modales import (
    construir_tarjeta_usuario,
    mostrar_modal_editar_usuario,
    mostrar_modal_reset_clave,
)


def _registrar_auditoria_usuario(interfaz: Any, accion: str, detalle: str) -> None:
    """Asienta un evento de administración IAM en OrderStore si está disponible."""
    try:
        if hasattr(interfaz, "order_store") and interfaz.order_store:
            usr_act = interfaz.usuario_actual.username if interfaz.usuario_actual else "Admin"
            interfaz.order_store.registrar_auditoria(usr_act, accion, detalle)
    except Exception:
        pass


def _obtener_usuarios_visibles(interfaz: Any, actual_es_master: bool, actual_es_admin: bool, actual: User | None) -> list[User]:
    """Consulta el listado de usuarios con retrocompatibilidad entre versiones de UserStore."""
    try:
        return interfaz.user_store.list_users(
            include_master=actual_es_master,
            exclude_other_admins=actual_es_admin,
            current_user_id=actual.id if actual else None,
        )
    except TypeError:
        try:
            return interfaz.user_store.list_users(include_master=actual_es_master)
        except TypeError:
            return interfaz.user_store.list_users()
    except Exception:
        return interfaz.user_store.list_users()


def mostrar_dialogo_gestion_usuarios(interfaz: Any) -> None:
    """Abre la ventana modal para administrar usuarios, roles y contraseñas."""
    if not interfaz.exigir_roles("administrador", "master"):
        return

    colores = colores_de(interfaz)
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

    actual = interfaz.usuario_actual
    actual_es_master = bool(actual and actual.role == "master")
    actual_es_admin = bool(actual and actual.role == "administrador")
    roles_creables = (
        ["administrador", "operador", "picker", "despachador", "consulta"]
        if actual_es_master
        else ["operador", "picker", "despachador", "consulta"]
    )
    nuevo_rol = ft.Dropdown(
        label="Rol",
        value="consulta",
        options=[ft.DropdownOption(key=role, text=role.capitalize()) for role in roles_creables],
        width=180,
    )
    mensaje = ft.Text(color=colores.error, size=12)

    def _set_feedback(texto: str, es_error: bool = True) -> None:
        mensaje.value = texto
        mensaje.color = colores.error if es_error else colores.exito

    usuarios = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=260)
    crear_boton = ft.Button(
        "Crear usuario",
        icon=ft.Icons.PERSON_ADD,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
    )
    ancho_dlg = interfaz.ancho_adaptable(620) if hasattr(interfaz, "ancho_adaptable") else 620
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.MANAGE_ACCOUNTS, color=ROJO), ft.Text("Gestión de usuarios", weight=ft.FontWeight.BOLD)]),
        content=ft.Container(
            width=ancho_dlg,
            content=ft.Column(
                [
                    ft.Text("Registrar nuevo usuario", weight=ft.FontWeight.BOLD, size=13),
                    grilla_tarjetas_responsiva([nuevo_usuario, nuevo_nombre], interfaz=interfaz, compacto=False, spacing=8, run_spacing=8),
                    grilla_tarjetas_responsiva([nuevo_email, nueva_clave], interfaz=interfaz, compacto=False, spacing=8, run_spacing=8),
                    ft.Row([nuevo_rol, crear_boton], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True, run_spacing=6),
                    mensaje,
                    ft.Divider(),
                    ft.Text("Usuarios existentes", weight=ft.FontWeight.BOLD, size=13),
                    usuarios,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )

    def desbloquear_cuenta(uname: str) -> None:
        if not interfaz.exigir_roles("administrador", "master"):
            return
        target = interfaz.user_store.get_user_by_username(uname)
        if target and not actual_es_master and target.role in ("master", "administrador"):
            _set_feedback("No tienes permisos para desbloquear a este usuario.", es_error=True)
            interfaz.page.update()
            return
        interfaz.user_store.unlock_user(uname)
        _registrar_auditoria_usuario(interfaz, "DESBLOQUEO_USUARIO", f"Cuenta '{uname}' desbloqueada manualmente")
        _set_feedback(f"Cuenta '{uname}' desbloqueada.", es_error=False)
        actualizar_lista()
        interfaz.page.update()

    def cambiar_rol(user_id: int, role: str) -> None:
        if not interfaz.exigir_roles("administrador", "master"):
            return
        if not actual_es_master and role in ("administrador", "master"):
            _set_feedback("Solo el usuario master puede asignar el rol de administrador.", es_error=True)
            actualizar_lista()
            interfaz.page.update()
            return
        target = interfaz.user_store.get_user(user_id)
        if target and not actual_es_master and target.role in ("master", "administrador"):
            _set_feedback("Solo el usuario master puede modificar el rol de un administrador.", es_error=True)
            actualizar_lista()
            interfaz.page.update()
            return
        try:
            interfaz.user_store.update_role(
                user_id,
                role,
                updater_role=interfaz.usuario_actual.role if interfaz.usuario_actual else None,
            )
            nom_t = target.username if target else str(user_id)
            _registrar_auditoria_usuario(interfaz, "CAMBIO_ROL_USUARIO", f"Usuario '{nom_t}' -> rol '{role}'")
            _set_feedback("", es_error=False)
        except (ValueError, UserStoreError) as error:
            _set_feedback(str(error), es_error=True)
        actualizar_lista()
        interfaz.page.update()

    def cambiar_estado(user_id: int, active: bool) -> None:
        if not interfaz.exigir_roles("administrador", "master"):
            return
        target = interfaz.user_store.get_user(user_id)
        if target and not actual_es_master and target.role in ("master", "administrador"):
            _set_feedback("Solo el usuario master puede modificar el estado de un administrador.", es_error=True)
            actualizar_lista()
            interfaz.page.update()
            return

        nom_t = target.username if target else str(user_id)

        def _aplicar_estado() -> None:
            try:
                interfaz.user_store.set_active(
                    user_id,
                    active,
                    updater_role=interfaz.usuario_actual.role if interfaz.usuario_actual else None,
                )
                acc = "ACTIVAR_USUARIO" if active else "DESACTIVAR_USUARIO"
                _registrar_auditoria_usuario(interfaz, acc, f"Usuario '{nom_t}' -> activo={active}")
                _set_feedback(f"Usuario '{nom_t}' {'activado' if active else 'desactivado'}.", es_error=False)
            except UserStoreError as error:
                _set_feedback(str(error), es_error=True)
            actualizar_lista()
            interfaz.page.update()

        if not active:
            confirmar_accion_destructiva(
                interfaz,
                f"Desactivar usuario @{nom_t}",
                f"¿Confirmas desactivar la cuenta de '{nom_t}'? Sus sesiones activas se cerrarán de inmediato.",
                _aplicar_estado,
                texto_confirmar="Sí, Desactivar",
                roles_permitidos=("administrador", "master"),
            )
        else:
            _aplicar_estado()

    def actualizar_lista() -> None:
        nonlocal actual, actual_es_master, actual_es_admin
        usuarios.controls.clear()
        actual = interfaz.usuario_actual
        actual_es_master = bool(actual and actual.role == "master")
        actual_es_admin = bool(actual and actual.role == "administrador")
        bloqueados = (
            interfaz.user_store.list_locked_usernames()
            if hasattr(interfaz.user_store, "list_locked_usernames")
            else set()
        )
        roles_asignables = (
            ["administrador", "operador", "picker", "despachador", "consulta"]
            if actual_es_master
            else ["operador", "picker", "despachador", "consulta"]
        )
        lista_usuarios = _obtener_usuarios_visibles(interfaz, actual_es_master, actual_es_admin, actual)
        for usuario in lista_usuarios:
            if not actual_es_master and usuario.role == "master":
                continue
            es_propio = actual is not None and usuario.id == actual.id
            if actual_es_admin and usuario.role == "administrador" and not es_propio:
                continue
            usuarios.controls.append(
                construir_tarjeta_usuario(
                    interfaz,
                    usuario,
                    actual=actual,
                    actual_es_master=actual_es_master,
                    roles_asignables=roles_asignables,
                    esta_bloqueado=usuario.username in bloqueados,
                    on_cambiar_rol=cambiar_rol,
                    on_cambiar_estado=cambiar_estado,
                    on_editar=lambda u: mostrar_modal_editar_usuario(interfaz, u, actualizar_lista),
                    on_reset_clave=lambda u: mostrar_modal_reset_clave(interfaz, u),
                    on_desbloquear=desbloquear_cuenta,
                )
            )

    def crear_usuario(_evento: ft.Event) -> None:
        if not interfaz.exigir_roles("administrador", "master"):
            return
        if not actual_es_master and nuevo_rol.value in ("administrador", "master"):
            _set_feedback("Solo el usuario master puede crear administradores.", es_error=True)
            interfaz.page.update()
            return
        marcar_error(nuevo_usuario, None)
        fijar_ocupado(crear_boton, True, "Creando...")
        try:
            uname_creado = (nuevo_usuario.value or "").strip()
            rol_creado = nuevo_rol.value or "consulta"
            interfaz.user_store.create_user(
                uname_creado,
                nueva_clave.value or "",
                rol_creado,
                creator_role=interfaz.usuario_actual.role if interfaz.usuario_actual else None,
                nombre=nuevo_nombre.value or "",
                email=nuevo_email.value or "",
            )
        except (ValueError, UserStoreError) as error:
            err_msg = str(error)
            if "ya existe" in err_msg.lower():
                marcar_error(nuevo_usuario, "El usuario ya existe en el sistema")
            _set_feedback(err_msg, es_error=True)
        else:
            _registrar_auditoria_usuario(interfaz, "CREAR_USUARIO", f"Alta de usuario '{uname_creado}' (rol={rol_creado})")
            nuevo_usuario.value = ""
            nuevo_nombre.value = ""
            nuevo_email.value = ""
            nueva_clave.value = ""
            _set_feedback("Usuario creado con éxito.", es_error=False)
        finally:
            fijar_ocupado(crear_boton, False)
        actualizar_lista()
        interfaz.page.update()

    crear_boton.on_click = crear_usuario
    actualizar_lista()
    interfaz.page.show_dialog(dialogo)
