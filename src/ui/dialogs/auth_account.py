"""Vistas y diálogos de cuenta: cambio de clave, perfil y configuración inicial."""

from __future__ import annotations

from typing import Any

import flet as ft

from ...auth import USER_ROLES, UserStoreError
from ..design import colores_de, fijar_ocupado, limpiar_errores, marcar_error
from ..theme import ROJO
from .auth_styles import (
    _borde_espejo,
    _estilizar_campo_espejo,
    _gradiente_tarjeta_espejo,
    _sombra_espejo,
    limpiar_chrome_auth,
    renderizar_en_fondo_espejo,
)


def mostrar_cambio_clave_obligatorio(interfaz: Any) -> None:
    """Exige cambiar la contraseña por defecto o temporal antes de ingresar al sistema."""
    if interfaz.usuario_actual is None:
        interfaz.mostrar_inicio_sesion()
        return
    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    modo_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    interfaz._modo_movil_previo = es_movil
    padding_tarjeta = 18 if es_movil else 32
    ancho_tarjeta = interfaz.ancho_adaptable(350 if es_movil else 460, margen=24 if es_movil else 32)
    ancho_boton = max(220, ancho_tarjeta - (padding_tarjeta * 2))

    actual_input = ft.TextField(
        label="Contraseña actual",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        autofocus=not es_movil,
        width=ancho_boton,
    )
    nueva_input = ft.TextField(
        label="Nueva contraseña (mínimo 10 caracteres)",
        prefix_icon=ft.Icons.KEY_OUTLINED,
        password=True,
        can_reveal_password=True,
        width=ancho_boton,
    )
    confirmar_input = ft.TextField(
        label="Confirmar nueva contraseña",
        prefix_icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
        password=True,
        can_reveal_password=True,
        width=ancho_boton,
    )
    for campo in (actual_input, nueva_input, confirmar_input):
        _estilizar_campo_espejo(campo, modo_oscuro)
    colores = colores_de(interfaz)
    msg_error = ft.Text("", color=colores.error, size=12, visible=False)
    btn_actualizar = ft.Button(
        "Actualizar contraseña y continuar",
        icon=ft.Icons.LOCK_RESET,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        width=ancho_boton,
        height=44,
    )

    def confirmar_cambio(_e: ft.Event) -> None:
        if not interfaz.usuario_actual:
            return
        limpiar_errores(actual_input, nueva_input, confirmar_input)
        if (nueva_input.value or "") != (confirmar_input.value or ""):
            marcar_error(confirmar_input, "La confirmación no coincide.")
            msg_error.value = "La nueva contraseña y su confirmación no coinciden."
            msg_error.visible = True
            interfaz.page.update()
            return
        fijar_ocupado(btn_actualizar, True, "Actualizando...")
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
            fijar_ocupado(btn_actualizar, False)
            msg_error.value = str(err)
            msg_error.visible = True
            interfaz.page.update()

    btn_actualizar.on_click = confirmar_cambio

    interfaz.page.controls.clear()
    tarjeta = ft.Container(
        width=ancho_tarjeta,
        padding=padding_tarjeta,
        gradient=_gradiente_tarjeta_espejo(modo_oscuro),
        blur=ft.Blur(22, 22),
        border=_borde_espejo(modo_oscuro),
        border_radius=18,
        shadow=_sombra_espejo(modo_oscuro),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.SECURITY, color=ROJO, size=26),
                        ft.Text(
                            "Cambio de contraseña requerido",
                            size=18 if es_movil else 20,
                            weight=ft.FontWeight.BOLD,
                            color=interfaz.texto,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    f"Hola {interfaz.usuario_actual.username}. Por seguridad, debes definir una nueva contraseña personal antes de continuar.",
                    color=interfaz.secundario,
                    size=13,
                ),
                actual_input,
                nueva_input,
                confirmar_input,
                msg_error,
                btn_actualizar,
                ft.TextButton(
                    "Cancelar y volver al inicio",
                    width=ancho_boton,
                    on_click=interfaz.cerrar_sesion,
                ),
            ],
            width=ancho_boton,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )
    renderizar_en_fondo_espejo(interfaz, tarjeta, es_movil, modo_oscuro)


def mostrar_cambiar_mi_clave(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Diálogo modal para que el usuario autenticado cambie su contraseña."""
    if not interfaz.exigir_roles(*USER_ROLES):
        return
    colores = colores_de(interfaz)
    actual_input = ft.TextField(label="Contraseña actual", password=True, can_reveal_password=True, autofocus=True)
    nueva_input = ft.TextField(label="Nueva contraseña (mínimo 10 caracteres)", password=True, can_reveal_password=True)
    confirmar_input = ft.TextField(label="Confirmar nueva contraseña", password=True, can_reveal_password=True)
    msg_error = ft.Text("", color=colores.error, size=12)
    btn_guardar = ft.Button("Guardar nueva clave", icon=ft.Icons.SAVE, bgcolor=ROJO, color=ft.Colors.WHITE)

    def guardar_clave(_e: ft.Event) -> None:
        if not interfaz.usuario_actual:
            return
        limpiar_errores(actual_input, nueva_input, confirmar_input)
        if (nueva_input.value or "") != (confirmar_input.value or ""):
            marcar_error(confirmar_input, "Las contraseñas nuevas no coinciden.")
            msg_error.value = "Las contraseñas nuevas no coinciden."
            interfaz.page.update()
            return
        fijar_ocupado(btn_guardar, True, "Guardando...")
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
            fijar_ocupado(btn_guardar, False)
            msg_error.value = str(err)
            interfaz.page.update()

    btn_guardar.on_click = guardar_clave

    ancho_dlg = interfaz.ancho_adaptable(400) if hasattr(interfaz, "ancho_adaptable") else 400
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.KEY, color=ROJO), ft.Text("Cambiar mi contraseña", weight=ft.FontWeight.BOLD)]),
        content=ft.Container(
            width=ancho_dlg,
            content=ft.Column(
                [actual_input, nueva_input, confirmar_input, msg_error],
                tight=True,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        ),
        actions=[
            btn_guardar,
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

    ancho_perfil = interfaz.ancho_adaptable(420) if hasattr(interfaz, "ancho_adaptable") else 420
    dialogo_perfil = ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.BADGE_OUTLINED, color=ROJO), ft.Text("Mi Perfil", weight=ft.FontWeight.BOLD)]),
        content=ft.Container(
            width=ancho_perfil,
            content=ft.Column(
                [
                    ft.Text(f"Usuario: @{actual.username} · Rol: {actual.role.capitalize()}", size=12, color=interfaz.secundario),
                    nombre_input,
                    email_input,
                    msg_error,
                ],
                tight=True,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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
    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    modo_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    interfaz._modo_movil_previo = es_movil
    padding_tarjeta = 18 if es_movil else 32
    ancho_tarjeta = interfaz.ancho_adaptable(350 if es_movil else 460, margen=24 if es_movil else 32)
    ancho_boton = max(220, ancho_tarjeta - (padding_tarjeta * 2))

    usuario = ft.TextField(label="Usuario administrador *", prefix_icon=ft.Icons.PERSON_OUTLINE, autofocus=not es_movil, width=ancho_boton)
    nombre_input = ft.TextField(
        label="Nombre y apellido (identificador en documentos)",
        prefix_icon=ft.Icons.BADGE_OUTLINED,
        hint_text="Ej: Juan Pérez",
        width=ancho_boton,
    )
    email_input = ft.TextField(label="Correo electrónico (opcional)", prefix_icon=ft.Icons.EMAIL_OUTLINED, hint_text="Ej: admin@ultratech.com", width=ancho_boton)
    clave = ft.TextField(label="Contraseña (mínimo 10 caracteres) *", prefix_icon=ft.Icons.LOCK_OUTLINE, password=True, can_reveal_password=True, width=ancho_boton)
    confirmar = ft.TextField(label="Confirmar contraseña *", prefix_icon=ft.Icons.CHECK_CIRCLE_OUTLINE, password=True, can_reveal_password=True, width=ancho_boton)
    for campo in (usuario, nombre_input, email_input, clave, confirmar):
        _estilizar_campo_espejo(campo, modo_oscuro)
    colores = colores_de(interfaz)
    mensaje = ft.Text(error, color=colores.error, size=12, visible=bool(error))
    btn_crear_admin = ft.Button("Crear cuenta y continuar", icon=ft.Icons.PERSON_ADD, bgcolor=ROJO, color=ft.Colors.WHITE, width=ancho_boton, height=44)

    def crear_administrador(_evento: ft.Event) -> None:
        limpiar_errores(usuario, clave, confirmar)
        if clave.value != confirmar.value:
            marcar_error(confirmar, "Las contraseñas no coinciden.")
            mensaje.value = "Las contraseñas no coinciden."
            mensaje.visible = True
            interfaz.page.update()
            return
        fijar_ocupado(btn_crear_admin, True, "Creando cuenta...")
        try:
            interfaz.usuario_actual = interfaz.user_store.create_initial_admin(
                usuario.value or "",
                clave.value or "",
                nombre=nombre_input.value or "",
                email=email_input.value or "",
            )
        except (ValueError, UserStoreError) as err:
            fijar_ocupado(btn_crear_admin, False)
            err_msg = str(err)
            if "ya existe" in err_msg.lower():
                marcar_error(usuario, "El usuario ya existe en el sistema")
            mensaje.value = err_msg
            mensaje.visible = True
            interfaz.page.update()
            return
        interfaz.construir()

    btn_crear_admin.on_click = crear_administrador

    limpiar_chrome_auth(interfaz)
    tarjeta = ft.Container(
        width=ancho_tarjeta,
        padding=padding_tarjeta,
        gradient=_gradiente_tarjeta_espejo(modo_oscuro),
        blur=ft.Blur(22, 22),
        border=_borde_espejo(modo_oscuro),
        border_radius=18,
        shadow=_sombra_espejo(modo_oscuro),
        content=ft.Column(
            [
                ft.Column(
                    [
                        ft.Text("Configurar administrador", size=22 if es_movil else 24, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ft.Text("Crea la primera cuenta para proteger el acceso al sistema.", size=13, color=interfaz.secundario),
                    ],
                    spacing=4,
                    tight=True,
                ),
                usuario,
                nombre_input,
                email_input,
                clave,
                confirmar,
                mensaje,
                btn_crear_admin,
            ],
            width=ancho_boton,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
    )
    renderizar_en_fondo_espejo(interfaz, tarjeta, es_movil, modo_oscuro)
