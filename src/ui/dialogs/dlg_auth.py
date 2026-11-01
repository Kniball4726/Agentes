"""Diálogos y pantallas de autenticación, perfil y configuración inicial."""

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

import flet as ft

from ..theme import ROJO
from ...user_store import UserStoreError, USER_ROLES

logger = logging.getLogger("stockagent")


def _borde_espejo(modo_oscuro: bool) -> ft.Border:
    """Borde biselado con brillo especular superior-izquierdo tipo espejo/cristal."""
    brillo_alto = ft.Colors.with_opacity(0.38 if modo_oscuro else 0.85, ft.Colors.WHITE)
    brillo_bajo = ft.Colors.with_opacity(0.12 if modo_oscuro else 0.35, ft.Colors.WHITE)
    return ft.Border(
        top=ft.BorderSide(1.5, brillo_alto),
        left=ft.BorderSide(1.5, brillo_alto),
        right=ft.BorderSide(1, brillo_bajo),
        bottom=ft.BorderSide(1, brillo_bajo),
    )


def _sombra_espejo(modo_oscuro: bool) -> list[ft.BoxShadow]:
    """Sombra profunda multicapa con resplandor especular sutil."""
    return [
        ft.BoxShadow(
            spread_radius=1,
            blur_radius=38,
            color=ft.Colors.with_opacity(0.55 if modo_oscuro else 0.18, ft.Colors.BLACK),
            offset=ft.Offset(0, 16),
        ),
        ft.BoxShadow(
            spread_radius=0,
            blur_radius=24,
            color=ft.Colors.with_opacity(0.16 if modo_oscuro else 0.10, ROJO),
            offset=ft.Offset(0, 4),
        ),
    ]


def _gradiente_fondo_espejo(modo_oscuro: bool) -> ft.LinearGradient:
    """Fondo ambiental para potenciar el desenfoque y reflejo del cristal."""
    if modo_oscuro:
        return ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[
                "#080B11",
                "#151C28",
                "#241118",
                "#0B0F17",
            ],
            stops=[0.0, 0.4, 0.75, 1.0],
        )
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=[
            "#ECEFF4",
            "#F8FAFC",
            "#FCE8E8",
            "#E2E8F0",
        ],
        stops=[0.0, 0.45, 0.78, 1.0],
    )


def _gradiente_tarjeta_espejo(modo_oscuro: bool) -> ft.LinearGradient:
    """Gradiente diagonal con franja de reflejo de luz sobre cristal."""
    if modo_oscuro:
        return ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[
                ft.Colors.with_opacity(0.84, "#1E293B"),
                ft.Colors.with_opacity(0.76, "#162032"),
                ft.Colors.with_opacity(0.88, "#283548"),
                ft.Colors.with_opacity(0.78, "#0F172A"),
            ],
            stops=[0.0, 0.38, 0.54, 1.0],
        )
    return ft.LinearGradient(
        begin=ft.Alignment.TOP_LEFT,
        end=ft.Alignment.BOTTOM_RIGHT,
        colors=[
            ft.Colors.with_opacity(0.88, ft.Colors.WHITE),
            ft.Colors.with_opacity(0.75, "#F8FAFC"),
            ft.Colors.with_opacity(0.94, ft.Colors.WHITE),
            ft.Colors.with_opacity(0.82, "#F1F5F9"),
        ],
        stops=[0.0, 0.4, 0.56, 1.0],
    )


def _estilizar_campo_espejo(campo: ft.TextField, modo_oscuro: bool) -> None:
    """Aplica acabado translúcido y borde brillante a un campo de texto."""
    campo.bgcolor = (
        ft.Colors.with_opacity(0.07, ft.Colors.WHITE)
        if modo_oscuro
        else ft.Colors.with_opacity(0.65, ft.Colors.WHITE)
    )
    campo.border_radius = 12
    campo.border_color = (
        ft.Colors.with_opacity(0.24, ft.Colors.WHITE)
        if modo_oscuro
        else ft.Colors.with_opacity(0.22, ft.Colors.BLUE_GREY_400)
    )
    campo.focused_border_color = ROJO


def mostrar_inicio_sesion(interfaz: Any, error: str = "") -> None:
    """Pantalla de inicio de sesión adaptable con acabado cristal/espejo (Glassmorphism)."""
    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    modo_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    interfaz._modo_movil_previo = es_movil
    usuario = ft.TextField(
        label="Usuario",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        autofocus=not es_movil,
        on_submit=lambda e: iniciar(e),
    )
    clave = ft.TextField(
        label="Contraseña",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        on_submit=lambda e: iniciar(e),
    )
    _estilizar_campo_espejo(usuario, modo_oscuro)
    _estilizar_campo_espejo(clave, modo_oscuro)

    mensaje = ft.Text(
        error,
        color=ft.Colors.RED_400,
        size=12,
        visible=bool(error),
    )

    def iniciar(_evento: ft.Event) -> None:
        nom_intento = (usuario.value or "").strip() or "desconocido"
        res = interfaz.user_store.authenticate_detailed(
            usuario.value or "", clave.value or ""
        )
        if res.user is None:
            mensaje.value = res.error or "Usuario o contraseña incorrectos, o cuenta inactiva."
            mensaje.visible = True
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
    if hasattr(interfaz.page, "drawer"):
        interfaz.page.drawer = None
    if hasattr(interfaz.page, "overlay") and interfaz.page.overlay is not None:
        interfaz.page.overlay.clear()
    interfaz.page.controls.clear()

    logo_path = Path(__file__).resolve().parent.parent.parent / "img" / "ultratech.png"
    logo_bytes = logo_path.read_bytes() if logo_path.exists() else b""
    w_actual = getattr(interfaz.page, "width", None)
    if isinstance(w_actual, (int, float)) and w_actual > 0:
        interfaz._ancho_previo = float(w_actual)

    usar_layout_compacto = es_movil or interfaz.ancho_adaptable(880, margen=48) < 720

    if usar_layout_compacto:
        padding_tarjeta = 18
        ancho_tarjeta = interfaz.ancho_adaptable(350, margen=24)
        ancho_boton = max(220, ancho_tarjeta - (padding_tarjeta * 2))
        usuario.width = ancho_boton
        clave.width = ancho_boton
        encabezado_movil: list[ft.Control] = []
        if logo_bytes:
            encabezado_movil.append(
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.92, ft.Colors.RED_50),
                    border=ft.Border.all(
                        1.5,
                        ft.Colors.with_opacity(0.65, ft.Colors.WHITE),
                    ),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Image(
                        src=logo_bytes,
                        width=32,
                        height=32,
                        fit=ft.BoxFit.CONTAIN,
                    ),
                )
            )
        encabezado_movil.append(
            ft.Column(
                [
                    ft.Text(
                        "StockAgent",
                        size=19,
                        weight=ft.FontWeight.BOLD,
                        color=interfaz.texto,
                    ),
                    ft.Text(
                        "Depósito Pasteur · Iniciar sesión",
                        size=12,
                        color=interfaz.secundario,
                    ),
                ],
                spacing=2,
                tight=True,
                expand=True,
            )
        )
        tarjeta_contenido = ft.Container(
            width=ancho_tarjeta,
            padding=padding_tarjeta,
            gradient=_gradiente_tarjeta_espejo(modo_oscuro),
            blur=ft.Blur(20, 20),
            border=_borde_espejo(modo_oscuro),
            border_radius=18,
            shadow=_sombra_espejo(modo_oscuro),
            content=ft.Column(
                [
                    ft.Row(
                        encabezado_movil,
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
                        height=42,
                    ),
                ],
                width=ancho_boton,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )
        contenido_central: ft.Control = ft.Column(
            [tarjeta_contenido],
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    else:
        ancho_tarjeta = interfaz.ancho_adaptable(880, margen=48)
        ancho_panel_izq = 380
        padding_derecho = 40
        ancho_form = max(340, ancho_tarjeta - ancho_panel_izq)
        ancho_boton = ancho_form - (padding_derecho * 2)
        alto_tarjeta = 450

        usuario.width = ancho_boton
        clave.width = ancho_boton

        gradiente_izq = (
            ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.28, ROJO),
                    ft.Colors.with_opacity(0.12, ROJO),
                    ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                    ft.Colors.with_opacity(0.18, ROJO),
                ],
                stops=[0.0, 0.45, 0.62, 1.0],
            )
            if modo_oscuro
            else ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.85, ft.Colors.RED_50),
                    ft.Colors.with_opacity(0.92, ft.Colors.WHITE),
                    ft.Colors.with_opacity(0.75, ft.Colors.RED_100),
                ],
                stops=[0.0, 0.5, 1.0],
            )
        )

        panel_izquierdo = ft.Container(
            width=ancho_panel_izq,
            height=alto_tarjeta,
            padding=36,
            alignment=ft.Alignment.CENTER_LEFT,
            gradient=gradiente_izq,
            border=ft.Border(
                right=ft.BorderSide(
                    1,
                    ft.Colors.with_opacity(0.22 if modo_oscuro else 0.45, ft.Colors.WHITE),
                )
            ),
            content=ft.Column(
                [
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        width=54,
                                        height=54,
                                        border_radius=14,
                                        bgcolor=ft.Colors.with_opacity(0.92, ft.Colors.RED_50),
                                        border=ft.Border.all(
                                            1.5,
                                            ft.Colors.with_opacity(0.65, ft.Colors.WHITE),
                                        ),
                                        shadow=ft.BoxShadow(
                                            blur_radius=12,
                                            color=ft.Colors.with_opacity(0.25, ROJO),
                                            offset=ft.Offset(0, 4),
                                        ),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Image(
                                            src=logo_bytes,
                                            width=44,
                                            height=44,
                                            fit=ft.BoxFit.CONTAIN,
                                        ),
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(
                                                "StockAgent",
                                                size=24,
                                                weight=ft.FontWeight.BOLD,
                                                color=interfaz.texto,
                                            ),
                                            ft.Text(
                                                "Depósito Pasteur",
                                                size=13,
                                                color=interfaz.secundario,
                                            ),
                                        ],
                                        spacing=2,
                                        tight=True,
                                    ),
                                ],
                                spacing=14,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Divider(
                                height=24,
                                color=ft.Colors.with_opacity(0.20, ft.Colors.WHITE)
                                if modo_oscuro
                                else interfaz.borde,
                            ),
                            ft.Text(
                                "Sistema de Gestión de Inventario, Pedidos y Despacho",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=interfaz.texto,
                            ),
                            ft.Text(
                                "Plataforma centralizada para control de stock en tiempo real, preparación de remitos, canjes y sincronización logística.",
                                size=13,
                                color=interfaz.secundario,
                            ),
                            ft.Container(height=4),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, color=ROJO, size=18),
                                            ft.Text("Control de stock y remitos en vivo", size=12, color=interfaz.texto, expand=True),
                                        ],
                                        spacing=10,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.QR_CODE_SCANNER, color=ROJO, size=18),
                                            ft.Text("Etiquetado QR y trazabilidad de bultos", size=12, color=interfaz.texto, expand=True),
                                        ],
                                        spacing=10,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.SHIELD_OUTLINED, color=ROJO, size=18),
                                            ft.Text("Acceso multi-equipo y auditoría por rol", size=12, color=interfaz.texto, expand=True),
                                        ],
                                        spacing=10,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ],
                                spacing=10,
                                tight=True,
                            ),
                        ],
                        spacing=12,
                        tight=True,
                    ),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        border_radius=20,
                        bgcolor=ft.Colors.with_opacity(0.08 if modo_oscuro else 0.55, ft.Colors.WHITE),
                        border=ft.Border.all(
                            1,
                            ft.Colors.with_opacity(0.18 if modo_oscuro else 0.4, ft.Colors.WHITE),
                        ),
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREEN_400, size=10),
                                ft.Text("Servidor web activo en red local", size=12, color=interfaz.secundario),
                            ],
                            spacing=8,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            ),
        )

        panel_derecho = ft.Container(
            width=ancho_form,
            height=alto_tarjeta,
            padding=padding_derecho,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    ft.Column(
                        [
                            ft.Text(
                                "Iniciar sesión",
                                size=28,
                                weight=ft.FontWeight.BOLD,
                                color=interfaz.texto,
                            ),
                            ft.Text(
                                "Ingresa tu usuario y contraseña para acceder al panel de control.",
                                size=14,
                                color=interfaz.secundario,
                            ),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                    ft.Container(height=4),
                    usuario,
                    clave,
                    mensaje,
                    ft.Container(height=4),
                    ft.Button(
                        "Ingresar al sistema",
                        icon=ft.Icons.LOGIN,
                        on_click=iniciar,
                        bgcolor=ROJO,
                        color=ft.Colors.WHITE,
                        width=ancho_boton,
                        height=46,
                    ),
                ],
                width=ancho_boton,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                scroll=ft.ScrollMode.AUTO,
                spacing=16,
            ),
        )

        tarjeta_contenido = ft.Container(
            width=ancho_tarjeta,
            height=alto_tarjeta,
            gradient=_gradiente_tarjeta_espejo(modo_oscuro),
            blur=ft.Blur(22, 22),
            border=_borde_espejo(modo_oscuro),
            border_radius=20,
            shadow=_sombra_espejo(modo_oscuro),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Row(
                [panel_izquierdo, panel_derecho],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        # Reflejo inferior atenuado (efecto espejo sobre superficie)
        reflejo_espejo = ft.Container(
            width=ancho_tarjeta - 16,
            height=28,
            border_radius=ft.BorderRadius.only(top_left=20, top_right=20),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_CENTER,
                end=ft.Alignment.BOTTOM_CENTER,
                colors=[
                    ft.Colors.with_opacity(0.14 if modo_oscuro else 0.25, ft.Colors.WHITE),
                    ft.Colors.with_opacity(0.05 if modo_oscuro else 0.08, ROJO),
                    ft.Colors.TRANSPARENT,
                ],
                stops=[0.0, 0.45, 1.0],
            ),
            blur=ft.Blur(8, 8),
        )

        contenido_central = ft.Column(
            [tarjeta_contenido, reflejo_espejo],
            spacing=2,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    interfaz.page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=interfaz.fondo,
            gradient=_gradiente_fondo_espejo(modo_oscuro),
            padding=12 if es_movil else 24,
            content=contenido_central,
        )
    )
    interfaz.page.update()


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
    msg_error = ft.Text("", color=ft.Colors.RED_400, size=12, visible=False)

    def confirmar_cambio(_e: ft.Event) -> None:
        if not interfaz.usuario_actual:
            return
        if (nueva_input.value or "") != (confirmar_input.value or ""):
            msg_error.value = "La nueva contraseña y su confirmación no coinciden."
            msg_error.visible = True
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
            msg_error.visible = True
            interfaz.page.update()

    interfaz.page.controls.clear()
    interfaz.page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=interfaz.fondo,
            gradient=_gradiente_fondo_espejo(modo_oscuro),
            padding=12 if es_movil else 24,
            content=ft.Container(
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
                        ft.Button(
                            "Actualizar contraseña y continuar",
                            icon=ft.Icons.LOCK_RESET,
                            bgcolor=ROJO,
                            color=ft.Colors.WHITE,
                            width=ancho_boton,
                            height=44,
                            on_click=confirmar_cambio,
                        ),
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
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
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

    usuario = ft.TextField(
        label="Usuario administrador *",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        autofocus=not es_movil,
        width=ancho_boton,
    )
    nombre_input = ft.TextField(
        label="Nombre y apellido (identificador en documentos)",
        prefix_icon=ft.Icons.BADGE_OUTLINED,
        hint_text="Ej: Juan Pérez",
        width=ancho_boton,
    )
    email_input = ft.TextField(
        label="Correo electrónico (opcional)",
        prefix_icon=ft.Icons.EMAIL_OUTLINED,
        hint_text="Ej: admin@ultratech.com",
        width=ancho_boton,
    )
    clave = ft.TextField(
        label="Contraseña (mínimo 10 caracteres) *",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        width=ancho_boton,
    )
    confirmar = ft.TextField(
        label="Confirmar contraseña *",
        prefix_icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
        password=True,
        can_reveal_password=True,
        width=ancho_boton,
    )
    for campo in (usuario, nombre_input, email_input, clave, confirmar):
        _estilizar_campo_espejo(campo, modo_oscuro)
    mensaje = ft.Text(error, color=ft.Colors.RED_400, size=12, visible=bool(error))

    def crear_administrador(_evento: ft.Event) -> None:
        if clave.value != confirmar.value:
            mensaje.value = "Las contraseñas no coinciden."
            mensaje.visible = True
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
            mensaje.visible = True
            interfaz.page.update()
            return
        interfaz.construir()

    interfaz.chat_visible = False
    interfaz.page.floating_action_button = None
    if hasattr(interfaz.page, "drawer"):
        interfaz.page.drawer = None
    if hasattr(interfaz.page, "overlay") and interfaz.page.overlay is not None:
        interfaz.page.overlay.clear()
    interfaz.page.controls.clear()
    interfaz.page.add(
        ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            bgcolor=interfaz.fondo,
            gradient=_gradiente_fondo_espejo(modo_oscuro),
            padding=12 if es_movil else 24,
            content=ft.Container(
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
                                ft.Text(
                                    "Configurar administrador",
                                    size=22 if es_movil else 24,
                                    weight=ft.FontWeight.BOLD,
                                    color=interfaz.texto,
                                ),
                                ft.Text(
                                    "Crea la primera cuenta para proteger el acceso al sistema.",
                                    size=13,
                                    color=interfaz.secundario,
                                ),
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
                        ft.Button(
                            "Crear cuenta y continuar",
                            icon=ft.Icons.PERSON_ADD,
                            on_click=crear_administrador,
                            bgcolor=ROJO,
                            color=ft.Colors.WHITE,
                            width=ancho_boton,
                            height=44,
                        ),
                    ],
                    width=ancho_boton,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            ),
        )
    )
    interfaz.page.update()
