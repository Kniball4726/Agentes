"""Diálogos y pantallas de autenticación, perfil y configuración inicial."""

from datetime import datetime
import logging
from typing import Any

import flet as ft

from ..theme import ROJO
from ...user_store import UserStoreError, USER_ROLES

logger = logging.getLogger("stockagent")


def mostrar_inicio_sesion(interfaz: Any, error: str = "") -> None:
    """Pantalla de inicio de sesión."""
    usuario = ft.TextField(label="Usuario", autofocus=True)
    clave = ft.TextField(
        label="Contraseña",
        password=True,
        can_reveal_password=True,
        on_submit=lambda e: iniciar(e),
    )
    mensaje = ft.Text(error, color=ft.Colors.RED_400, size=12)

    def iniciar(_evento: ft.Event) -> None:
        nom_intento = (usuario.value or "").strip() or "desconocido"
        res = interfaz.user_store.authenticate_detailed(
            usuario.value or "", clave.value or ""
        )
        if res.user is None:
            mensaje.value = res.error or "Usuario o contraseña incorrectos, o cuenta inactiva."
            try:
                interfaz.order_store.registrar_auditoria(
                    usuario=nom_intento,
                    accion="CUENTA_BLOQUEADA" if res.locked else "LOGIN_FALLIDO",
                    detalle=res.error or "Intento de acceso fallido",
                )
            except Exception:
                pass
            logger.warning("Intento de login fallido para '%s': %s", nom_intento, res.error)
            interfaz.page.update()
            return

        interfaz.usuario_actual = res.user
        interfaz.ultima_actividad = datetime.now()
        try:
            interfaz.order_store.registrar_auditoria(
                usuario=res.user.username,
                accion="LOGIN_EXITOSO",
                detalle=f"Inicio de sesión exitoso (rol: {res.user.role})",
            )
        except Exception:
            pass
        logger.info("Inicio de sesión exitoso: %s (%s)", res.user.username, res.user.role)
        if getattr(res.user, "must_change_password", False):
            interfaz.mostrar_cambio_clave_obligatorio()
        else:
            interfaz.construir()

    interfaz.chat_visible = False
    interfaz.page.floating_action_button = None
    if hasattr(interfaz.page, "overlay") and interfaz.page.overlay is not None:
        interfaz.page.overlay.clear()
    interfaz.page.controls.clear()
    ancho_tarjeta = interfaz.ancho_adaptable(420, margen=32)
    ancho_boton = ancho_tarjeta - (40 if interfaz.es_pantalla_movil else 56)
    interfaz.page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=interfaz.fondo,
            content=ft.Container(
                width=ancho_tarjeta,
                padding=18 if interfaz.es_pantalla_movil else 28,
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=16,
                content=ft.Column(
                    [
                        ft.Text(
                            "Iniciar sesión",
                            size=22 if interfaz.es_pantalla_movil else 24,
                            weight=ft.FontWeight.BOLD,
                            color=interfaz.texto,
                        ),
                        ft.Text(
                            "Agente de control de stock",
                            color=interfaz.secundario,
                        ),
                        usuario,
                        clave,
                        mensaje,
                        ft.Button(
                            "Ingresar",
                            icon=ft.Icons.LOGIN,
                            on_click=iniciar,
                            bgcolor=ROJO,
                            color=ft.Colors.WHITE,
                            width=ancho_boton,
                        ),
                    ],
                    tight=True,
                    spacing=14,
                ),
            ),
        )
    )
    interfaz.page.update()


def mostrar_cambio_clave_obligatorio(interfaz: Any) -> None:
    """Exige cambiar la contraseña por defecto o temporal antes de ingresar al sistema."""
    if interfaz.usuario_actual is None:
        interfaz.mostrar_inicio_sesion()
        return
    actual_input = ft.TextField(
        label="Contraseña actual",
        password=True,
        can_reveal_password=True,
        autofocus=True,
    )
    nueva_input = ft.TextField(
        label="Nueva contraseña (mínimo 10 caracteres)",
        password=True,
        can_reveal_password=True,
    )
    confirmar_input = ft.TextField(
        label="Confirmar nueva contraseña",
        password=True,
        can_reveal_password=True,
    )
    msg_error = ft.Text("", color=ft.Colors.RED_400, size=12)

    def confirmar_cambio(_e: ft.Event) -> None:
        if not interfaz.usuario_actual:
            return
        if (nueva_input.value or "") != (confirmar_input.value or ""):
            msg_error.value = "La nueva contraseña y su confirmación no coinciden."
            interfaz.page.update()
            return
        try:
            interfaz.user_store.change_password(
                interfaz.usuario_actual.id,
                actual_input.value or "",
                nueva_input.value or "",
            )
            interfaz.usuario_actual = interfaz.user_store.get_user(interfaz.usuario_actual.id)
            interfaz.order_store.registrar_auditoria(
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Usuario",
                accion="CAMBIO_CLAVE",
                detalle="Cambio de contraseña obligatorio completado al iniciar sesión",
            )
            interfaz.construir()
            interfaz.notificar("Contraseña actualizada con éxito. ¡Bienvenido!")
        except (ValueError, UserStoreError) as err:
            msg_error.value = str(err)
            interfaz.page.update()

    interfaz.page.controls.clear()
    interfaz.page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=interfaz.fondo,
            content=ft.Container(
                width=450,
                padding=28,
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=16,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.SECURITY, color=ROJO, size=26),
                                ft.Text(
                                    "Cambio de contraseña requerido",
                                    size=20,
                                    weight=ft.FontWeight.BOLD,
                                    color=interfaz.texto,
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.Text(
                            f"Hola {interfaz.usuario_actual.username}. Por seguridad, debes definir una nueva contraseña personal antes de continuar.",
                            color=interfaz.secundario,
                            size=12,
                        ),
                        actual_input,
                        nueva_input,
                        confirmar_input,
                        msg_error,
                        ft.Button(
                            "Actualizar contraseña y continuar",
                            icon=ft.Icons.LOCK_RESET,
                            bgcolor=ROJO,
                            color=ft.Colors.WHITE,
                            width=390,
                            on_click=confirmar_cambio,
                        ),
                        ft.TextButton(
                            "Cancelar y volver al inicio",
                            on_click=interfaz.cerrar_sesion,
                        ),
                    ],
                    tight=True,
                    spacing=12,
                ),
            ),
        )
    )
    interfaz.page.update()


def mostrar_cambiar_mi_clave(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Diálogo modal para que el usuario autenticado cambie su contraseña."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return
    actual_input = ft.TextField(
        label="Contraseña actual",
        password=True,
        can_reveal_password=True,
        autofocus=True,
    )
    nueva_input = ft.TextField(
        label="Nueva contraseña (mínimo 10 caracteres)",
        password=True,
        can_reveal_password=True,
    )
    confirmar_input = ft.TextField(
        label="Confirmar nueva contraseña",
        password=True,
        can_reveal_password=True,
    )
    msg_error = ft.Text("", color=ft.Colors.RED_400, size=12)

    def guardar_clave(_e: ft.Event) -> None:
        if not interfaz.usuario_actual:
            return
        if (nueva_input.value or "") != (confirmar_input.value or ""):
            msg_error.value = "Las contraseñas nuevas no coinciden."
            interfaz.page.update()
            return
        try:
            interfaz.user_store.change_password(
                interfaz.usuario_actual.id,
                actual_input.value or "",
                nueva_input.value or "",
            )
            interfaz.order_store.registrar_auditoria(
                usuario=interfaz.usuario_actual.username,
                accion="CAMBIO_CLAVE",
                detalle="El usuario actualizó su propia contraseña",
            )
            interfaz.page.pop_dialog()
            interfaz.notificar("Tu contraseña ha sido actualizada correctamente.")
        except (ValueError, UserStoreError) as err:
            msg_error.value = str(err)
            interfaz.page.update()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.KEY, color=ROJO), ft.Text("Cambiar mi contraseña", weight=ft.FontWeight.BOLD)]),
        content=ft.Container(
            width=400,
            content=ft.Column(
                [actual_input, nueva_input, confirmar_input, msg_error],
                tight=True,
                spacing=10,
            ),
        ),
        actions=[
            ft.Button("Guardar nueva clave", icon=ft.Icons.SAVE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=guardar_clave),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_mi_perfil(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana de perfil personal del usuario autenticado."""
    if not interfaz.usuario_actual:
        return
    actual = interfaz.usuario_actual
    nombre_input = ft.TextField(
        label="Nombre y apellido / Identificador en documentos",
        value=actual.nombre,
        hint_text="Ej: Juan Pérez",
        autofocus=True,
    )
    email_input = ft.TextField(
        label="Correo electrónico",
        value=actual.email,
        hint_text="Ej: usuario@ultratech.com",
    )
    msg_error = ft.Text("", color=ft.Colors.RED_400, size=12)

    def guardar_perfil(_e: ft.Event) -> None:
        if not interfaz.usuario_actual:
            return
        try:
            interfaz.user_store.update_user_info(
                interfaz.usuario_actual.id,
                nombre=nombre_input.value or "",
                email=email_input.value or "",
            )
            interfaz.usuario_actual = interfaz.user_store.get_user(interfaz.usuario_actual.id)
            interfaz.page.pop_dialog()
            interfaz.construir()
            interfaz.notificar("Tu perfil ha sido actualizado correctamente.")
        except (ValueError, UserStoreError) as err:
            msg_error.value = str(err)
            interfaz.page.update()

    dialogo_perfil = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.BADGE_OUTLINED, color=ROJO), ft.Text("Mi Perfil", weight=ft.FontWeight.BOLD)]),
        content=ft.Container(
            width=420,
            content=ft.Column(
                [
                    ft.Text(f"Usuario: @{actual.username} · Rol: {actual.role.capitalize()}", size=12, color=interfaz.secundario),
                    nombre_input,
                    email_input,
                    msg_error,
                ],
                tight=True,
                spacing=12,
            ),
        ),
        actions=[
            ft.Button("Guardar cambios", icon=ft.Icons.SAVE, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=guardar_perfil),
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo_perfil)


def mostrar_configuracion_inicial(interfaz: Any, error: str = "") -> None:
    """Pantalla inicial para crear el primer administrador del sistema."""
    usuario = ft.TextField(label="Usuario administrador *", autofocus=True)
    nombre_input = ft.TextField(
        label="Nombre y apellido (identificador en documentos)",
        hint_text="Ej: Juan Pérez",
    )
    email_input = ft.TextField(
        label="Correo electrónico (opcional)",
        hint_text="Ej: admin@ultratech.com",
    )
    clave = ft.TextField(
        label="Contraseña (mínimo 10 caracteres) *",
        password=True,
        can_reveal_password=True,
    )
    confirmar = ft.TextField(
        label="Confirmar contraseña *",
        password=True,
        can_reveal_password=True,
    )
    mensaje = ft.Text(error, color=ft.Colors.RED_400)

    def crear_administrador(_evento: ft.Event) -> None:
        if clave.value != confirmar.value:
            mensaje.value = "Las contraseñas no coinciden."
            interfaz.page.update()
            return
        try:
            interfaz.usuario_actual = interfaz.user_store.create_initial_admin(
                usuario.value or "",
                clave.value or "",
                nombre=nombre_input.value or "",
                email=email_input.value or "",
            )
        except (ValueError, UserStoreError) as err:
            mensaje.value = str(err)
            interfaz.page.update()
            return
        interfaz.construir()

    interfaz.chat_visible = False
    interfaz.page.floating_action_button = None
    if hasattr(interfaz.page, "overlay") and interfaz.page.overlay is not None:
        interfaz.page.overlay.clear()
    interfaz.page.controls.clear()
    interfaz.page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=interfaz.fondo,
            content=ft.Container(
                width=460,
                padding=28,
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=16,
                content=ft.Column(
                    [
                        ft.Text(
                            "Configurar administrador",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            color=interfaz.texto,
                        ),
                        ft.Text(
                            "Crea la primera cuenta para proteger el acceso al sistema.",
                            color=interfaz.secundario,
                        ),
                        usuario,
                        nombre_input,
                        email_input,
                        clave,
                        confirmar,
                        mensaje,
                        ft.Button(
                            "Crear cuenta y continuar",
                            icon=ft.Icons.PERSON_ADD,
                            on_click=crear_administrador,
                            bgcolor=ROJO,
                            color=ft.Colors.WHITE,
                            width=400,
                        ),
                    ],
                    tight=True,
                    spacing=14,
                ),
            ),
        )
    )
    interfaz.page.update()
