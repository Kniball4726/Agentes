"""Componente de navegación móvil optimizado para la 'Zona del Pulgar' (Thumb Zone)."""

from __future__ import annotations
from typing import Any
import flet as ft


def _crear_punto_chat_movil() -> ft.Container:
    return ft.Container(
        width=9,
        height=9,
        border_radius=4.5,
        bgcolor=ft.Colors.RED_500,
        border=ft.Border.all(1.5, ft.Colors.WHITE),
        right=-3,
        top=-3,
        visible=False,
    )


def _destino_chat_movil(dest_cls: Any, interfaz: Any) -> Any:
    return dest_cls(
        icon=ft.Stack(
            [
                ft.Icon(ft.Icons.SMART_TOY_OUTLINED),
                interfaz.punto_nuevo_chat_movil,
            ],
            width=26,
            height=24,
            clip_behavior=ft.ClipBehavior.NONE,
        ),
        selected_icon=ft.Stack(
            [
                ft.Icon(ft.Icons.SMART_TOY),
                interfaz.punto_nuevo_chat_movil_sel,
            ],
            width=26,
            height=24,
            clip_behavior=ft.ClipBehavior.NONE,
        ),
        label="Chat",
    )


def construir_navigation_bar_movil(interfaz: Any) -> ft.NavigationBar:
    """Crea la barra inferior anclada para operación con una sola mano en depósitos, adaptada por rol."""
    modo_oscuro = getattr(interfaz, "modo_oscuro", True)
    superficie = getattr(interfaz, "superficie", ft.Colors.BLUE_GREY_900)
    interfaz.punto_nuevo_chat_movil = _crear_punto_chat_movil()
    interfaz.punto_nuevo_chat_movil_sel = _crear_punto_chat_movil()

    def _al_cambiar(e: Any) -> None:
        manejar_cambio_navegacion_movil(interfaz, e)

    dest_cls = getattr(ft, "NavigationBarDestination", getattr(ft, "NavigationDestination", None))
    chat_dest = _destino_chat_movil(dest_cls, interfaz)

    rol = str(getattr(getattr(interfaz, "usuario_actual", None), "role", "")).strip().lower()
    if rol == "despachador":
        destinos = [
            dest_cls(icon=ft.Icons.LOCAL_SHIPPING_OUTLINED, selected_icon=ft.Icons.LOCAL_SHIPPING, label="Despacho"),
            chat_dest,
        ]
    elif rol == "picker":
        destinos = [
            dest_cls(icon=ft.Icons.WAVES, selected_icon=ft.Icons.WAVES, label="Ola Picking"),
            dest_cls(icon=ft.Icons.QR_CODE_SCANNER, selected_icon=ft.Icons.QR_CODE_SCANNER, label="Escanear ML"),
            dest_cls(icon=ft.Icons.LOCAL_SHIPPING_OUTLINED, selected_icon=ft.Icons.LOCAL_SHIPPING, label="Full"),
            dest_cls(icon=ft.Icons.INVENTORY_2_OUTLINED, selected_icon=ft.Icons.INVENTORY_2, label="Fábrica"),
            chat_dest,
        ]
    elif rol == "administrador":
        destinos = [
            dest_cls(icon=ft.Icons.RECEIPT_LONG_OUTLINED, selected_icon=ft.Icons.RECEIPT_LONG, label="Pedidos"),
            dest_cls(icon=ft.Icons.INVENTORY_2_OUTLINED, selected_icon=ft.Icons.INVENTORY_2, label="Stock"),
            dest_cls(icon=ft.Icons.FACT_CHECK_OUTLINED, selected_icon=ft.Icons.FACT_CHECK, label="Cierres"),
            dest_cls(icon=ft.Icons.ASSESSMENT_OUTLINED, selected_icon=ft.Icons.ASSESSMENT, label="Reportes"),
            chat_dest,
        ]
    elif rol == "master":
        destinos = [
            dest_cls(icon=ft.Icons.MANAGE_ACCOUNTS_OUTLINED, selected_icon=ft.Icons.MANAGE_ACCOUNTS, label="Usuarios"),
            dest_cls(icon=ft.Icons.SECURITY_OUTLINED, selected_icon=ft.Icons.SECURITY, label="Auditoría"),
            dest_cls(icon=ft.Icons.API_OUTLINED, selected_icon=ft.Icons.API, label="API REST"),
            dest_cls(icon=ft.Icons.BACKUP_OUTLINED, selected_icon=ft.Icons.BACKUP, label="Backup"),
            chat_dest,
        ]
    elif rol == "consulta":
        destinos = [
            dest_cls(icon=ft.Icons.INVENTORY_2_OUTLINED, selected_icon=ft.Icons.INVENTORY_2, label="Stock"),
            dest_cls(icon=ft.Icons.ASSESSMENT_OUTLINED, selected_icon=ft.Icons.ASSESSMENT, label="Reportes"),
            dest_cls(icon=ft.Icons.OPEN_IN_NEW, selected_icon=ft.Icons.OPEN_IN_NEW, label="Informes"),
            chat_dest,
        ]
    else:
        destinos = [
            dest_cls(icon=ft.Icons.RECEIPT_LONG_OUTLINED, selected_icon=ft.Icons.RECEIPT_LONG, label="Pedidos"),
            dest_cls(icon=ft.Icons.QR_CODE_SCANNER, selected_icon=ft.Icons.QR_CODE_SCANNER, label="Escanear ML"),
            dest_cls(icon=ft.Icons.INVENTORY_2_OUTLINED, selected_icon=ft.Icons.INVENTORY_2, label="Fábrica"),
            dest_cls(icon=ft.Icons.TASK_ALT_OUTLINED, selected_icon=ft.Icons.TASK_ALT, label="Cierre"),
            chat_dest,
        ]

    return ft.NavigationBar(
        bgcolor=superficie,
        indicator_color=ft.Colors.RED_900 if modo_oscuro else ft.Colors.RED_100,
        destinations=destinos,
        on_change=_al_cambiar,
    )


def manejar_cambio_navegacion_movil(interfaz: Any, e: Any) -> None:
    """Enruta la acción seleccionada en la barra Thumb Zone inferior según el rol activo."""
    ctrl = getattr(e, "control", None)
    idx = getattr(ctrl, "selected_index", None)
    rol = str(getattr(getattr(interfaz, "usuario_actual", None), "role", "")).strip().lower()
    if rol == "despachador":
        if idx == 0:
            interfaz.mostrar_modulo_despacho()
        elif idx == 1:
            interfaz.alternar_chat_flotante()
        return
    if rol == "picker":
        if idx == 0:
            interfaz.mostrar_dialogo_ola_picking()
        elif idx == 1:
            interfaz.mostrar_descuento_mercado_libre()
        elif idx == 2:
            interfaz.mostrar_picking_guiado_full()
        elif idx == 3:
            interfaz.mostrar_ingreso_fabrica()
        elif idx == 4:
            interfaz.alternar_chat_flotante()
        return
    if rol == "administrador":
        if idx == 0:
            interfaz.mostrar_historial_pedidos()
        elif idx == 1:
            interfaz.mostrar_ver_stock()
        elif idx == 2:
            interfaz.mostrar_historial_cierres_admin()
        elif idx == 3:
            interfaz.mostrar_centro_reportes()
        elif idx == 4:
            interfaz.alternar_chat_flotante()
        return
    if rol == "master":
        if idx == 0:
            interfaz.mostrar_gestion_usuarios()
        elif idx == 1:
            interfaz.mostrar_registro_auditoria()
        elif idx == 2:
            interfaz.mostrar_gestion_api_keys()
        elif idx == 3:
            interfaz.mostrar_dialogo_backup()
        elif idx == 4:
            interfaz.alternar_chat_flotante()
        return
    if rol == "consulta":
        if idx == 0:
            interfaz.mostrar_ver_stock()
        elif idx == 1:
            interfaz.mostrar_centro_reportes()
        elif idx == 2:
            interfaz.abrir_informe()
        elif idx == 3:
            interfaz.alternar_chat_flotante()
        return
    if idx == 0:
        interfaz.mostrar_historial_pedidos()
    elif idx == 1:
        interfaz.mostrar_descuento_mercado_libre()
    elif idx == 2:
        interfaz.mostrar_ingreso_fabrica()
    elif idx == 3:
        interfaz.mostrar_cierre_jornada()
    elif idx == 4:
        interfaz.alternar_chat_flotante()
