"""Pantalla principal de inicio de sesión."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

import flet as ft

from ..theme import ROJO
from .auth_styles import (
    _borde_espejo,
    _estilizar_campo_espejo,
    _gradiente_tarjeta_espejo,
    _sombra_espejo,
    limpiar_chrome_auth,
    renderizar_en_fondo_espejo,
)

logger = logging.getLogger("stockagent")


def _logo_badge(logo_bytes: bytes, container_size: int, image_size: int, radius: int, with_shadow: bool = False) -> ft.Container:
    return ft.Container(
        width=container_size,
        height=container_size,
        border_radius=radius,
        bgcolor=ft.Colors.with_opacity(0.92, ft.Colors.RED_50),
        border=ft.Border.all(1.5, ft.Colors.with_opacity(0.65, ft.Colors.WHITE)),
        shadow=(
            ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.25, ROJO), offset=ft.Offset(0, 4))
            if with_shadow
            else None
        ),
        alignment=ft.Alignment.CENTER,
        content=ft.Image(src=logo_bytes, width=image_size, height=image_size, fit=ft.BoxFit.CONTAIN),
    )


def _construir_panel_izquierdo_login(interfaz: Any, modo_oscuro: bool, logo_bytes: bytes, ancho_panel_izq: int, alto_tarjeta: int) -> ft.Container:
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

    items_branding = [
        (ft.Icons.INVENTORY_2_OUTLINED, "Control de stock y remitos en vivo"),
        (ft.Icons.QR_CODE_SCANNER, "Etiquetado QR y trazabilidad de bultos"),
        (ft.Icons.SHIELD_OUTLINED, "Acceso multi-equipo y auditoría por rol"),
    ]
    features_col = ft.Column(
        [
            ft.Row(
                [ft.Icon(icono, color=ROJO, size=18), ft.Text(label, size=12, color=interfaz.texto, expand=True)],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            for icono, label in items_branding
        ],
        spacing=10,
        tight=True,
    )

    return ft.Container(
        width=ancho_panel_izq,
        height=alto_tarjeta,
        padding=36,
        alignment=ft.Alignment.CENTER_LEFT,
        gradient=gradiente_izq,
        border=ft.Border(right=ft.BorderSide(1, ft.Colors.with_opacity(0.22 if modo_oscuro else 0.45, ft.Colors.WHITE))),
        content=ft.Column(
            [
                ft.Column(
                    [
                        ft.Row(
                            [
                                _logo_badge(logo_bytes, 54, 44, 14, with_shadow=True),
                                ft.Column(
                                    [
                                        ft.Text("StockAgent", size=24, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                                        ft.Text("Depósito Pasteur", size=13, color=interfaz.secundario),
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
                            color=ft.Colors.with_opacity(0.20, ft.Colors.WHITE) if modo_oscuro else interfaz.borde,
                        ),
                        ft.Text("Sistema de Gestión de Inventario, Pedidos y Despacho", size=16, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ft.Text(
                            "Plataforma centralizada para control de stock en tiempo real, preparación de remitos, canjes y sincronización logística.",
                            size=13,
                            color=interfaz.secundario,
                        ),
                        ft.Container(height=4),
                        features_col,
                    ],
                    spacing=12,
                    tight=True,
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=20,
                    bgcolor=ft.Colors.with_opacity(0.08 if modo_oscuro else 0.55, ft.Colors.WHITE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.18 if modo_oscuro else 0.4, ft.Colors.WHITE)),
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

    mensaje = ft.Text(error, color=ft.Colors.RED_400, size=12, visible=bool(error))

    def iniciar(_evento: ft.Event) -> None:
        nom_intento = (usuario.value or "").strip() or "desconocido"
        res = interfaz.user_store.authenticate_detailed(usuario.value or "", clave.value or "")
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

    limpiar_chrome_auth(interfaz)

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
            encabezado_movil.append(_logo_badge(logo_bytes, 42, 32, 12))
        encabezado_movil.append(
            ft.Column(
                [
                    ft.Text("StockAgent", size=19, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Text("Depósito Pasteur · Iniciar sesión", size=12, color=interfaz.secundario),
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
                    ft.Row(encabezado_movil, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    usuario,
                    clave,
                    mensaje,
                    ft.Button("Ingresar", icon=ft.Icons.LOGIN, on_click=iniciar, bgcolor=ROJO, color=ft.Colors.WHITE, width=ancho_boton, height=42),
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

        panel_izquierdo = _construir_panel_izquierdo_login(interfaz, modo_oscuro, logo_bytes, ancho_panel_izq, alto_tarjeta)
        panel_derecho = ft.Container(
            width=ancho_form,
            height=alto_tarjeta,
            padding=padding_derecho,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    ft.Column(
                        [
                            ft.Text("Iniciar sesión", size=28, weight=ft.FontWeight.BOLD, color=interfaz.texto),
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
            content=ft.Row([panel_izquierdo, panel_derecho], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )
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

    renderizar_en_fondo_espejo(interfaz, contenido_central, es_movil, modo_oscuro)
