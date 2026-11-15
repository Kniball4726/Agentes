"""Componente para mostrar el avance y estado de Mercado Full y de Ingreso de Fábrica en el panel superior del Administrador."""

from __future__ import annotations

from typing import Any
import flet as ft


def construir_panel_seguimiento_admin(interfaz: Any, es_movil: bool = False) -> ft.Control | None:
    """
    Construye la barra o contenedor de seguimiento operativo exclusivo para el Administrador.
    Si el usuario no tiene rol 'administrador', retorna None (excluyendo a 'master', 'picker', etc.).
    """
    usuario = getattr(interfaz, "usuario_actual", None)
    if not usuario or getattr(usuario, "role", "") != "administrador":
        return None

    fila = ft.Row(
        [],
        spacing=8 if not es_movil else 4,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    contenedor = ft.Container(
        content=fila,
        padding=ft.Padding.symmetric(horizontal=0, vertical=2),
        visible=True,
    )
    if es_movil:
        interfaz.panel_seguimiento_admin_movil = contenedor
    else:
        interfaz.panel_seguimiento_admin = contenedor

    actualizar_seguimiento_operativo_admin(interfaz)
    return contenedor


def actualizar_seguimiento_operativo_admin(interfaz: Any) -> None:
    """
    Actualiza los badges de Mercado Full e Ingreso de Fábrica para el usuario Administrador.
    Muestra:
    - Estado en proceso con porcentaje de avance mientras se controla/prepara.
    - Cierre total con 'Cerrado con XX%' una vez completado por el picker, persistiendo hasta que se monte un nuevo archivo.
    """
    usuario = getattr(interfaz, "usuario_actual", None)
    if not usuario or getattr(usuario, "role", "") != "administrador":
        return

    order_store = getattr(interfaz, "order_store", None)
    if not order_store:
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))

    # 1. Obtener el último plan de Mercado Full
    ultimo_full = None
    try:
        planes_full = order_store.listar_planes_mercado_full()
        if planes_full:
            ultimo_full = planes_full[0]
    except Exception:
        pass

    # 2. Obtener el último plan de Ingreso de Fábrica
    ultimo_fabrica = None
    try:
        planes_fabrica = order_store.listar_planes_ingreso_fabrica()
        if planes_fabrica:
            ultimo_fabrica = planes_fabrica[0]
    except Exception:
        pass

    badges: list[ft.Control] = []

    # -----------------------------------------------------------------
    # BADGE: MERCADO ENVIOS FULL
    # -----------------------------------------------------------------
    if ultimo_full:
        estado_full = str(ultimo_full.get("estado", "")).lower()
        porc_full = float(ultimo_full.get("porcentaje", 0.0))
        tot_full = int(ultimo_full.get("articulos_totales", 0))
        pick_full = int(ultimo_full.get("articulos_pickeados", 0))
        nom_full = ultimo_full.get("nombre_envio", "Mercado Full")

        porc_str = f"{porc_full:.1f}%" if porc_full % 1 != 0 else f"{int(porc_full)}%"
        if estado_full == "completado":
            texto_full = f"Full: Cerrado con {porc_str}"
            icono_full = ft.Icons.CHECK_CIRCLE
            color_full = ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_700
            bg_full = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_400)
            borde_full = ft.Colors.GREEN_700 if es_oscuro else ft.Colors.GREEN_300
            tip_full = f"Mercado Full #{ultimo_full['id']} ({nom_full}): Cerrado ({pick_full}/{tot_full} un.). Clic para ver."
        elif estado_full in ("en_proceso", "pendiente"):
            texto_full = f"Full: {porc_str} (En preparación)"
            icono_full = ft.Icons.LOCAL_SHIPPING
            color_full = ft.Colors.AMBER_400 if es_oscuro else ft.Colors.AMBER_800
            bg_full = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_400)
            borde_full = ft.Colors.AMBER_600 if es_oscuro else ft.Colors.AMBER_400
            tip_full = f"Mercado Full #{ultimo_full['id']} ({nom_full}): En preparación ({pick_full}/{tot_full} un.). Clic para monitorear."
        else:
            texto_full = "Full: Cancelado"
            icono_full = ft.Icons.CANCEL
            color_full = ft.Colors.GREY_400
            bg_full = ft.Colors.with_opacity(0.12, ft.Colors.GREY_400)
            borde_full = ft.Colors.GREY_500
            tip_full = f"Mercado Full #{ultimo_full['id']} ({nom_full}): {estado_full}."

        badge_full = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icono_full, size=13, color=color_full),
                    ft.Text(texto_full, size=11, weight=ft.FontWeight.BOLD, color=color_full),
                ],
                spacing=5,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=12,
            bgcolor=bg_full,
            border=ft.Border.all(1, borde_full),
            tooltip=tip_full,
            ink=True,
            on_click=lambda _e: interfaz.mostrar_planificar_full() if hasattr(interfaz, "mostrar_planificar_full") else None,
        )
        badges.append(badge_full)
    else:
        badge_full_vacio = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.LOCAL_SHIPPING, size=14, color=ft.Colors.BLUE_GREY_400),
                    ft.Text("Full: Sin envíos activos", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_400 if es_oscuro else ft.Colors.BLUE_GREY_700),
                ],
                spacing=5,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_GREY_400),
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_700 if es_oscuro else ft.Colors.GREY_300),
            tooltip="No hay planes de Mercado Full activos. Clic para planificar.",
            ink=True,
            on_click=lambda _e: interfaz.mostrar_planificar_full() if hasattr(interfaz, "mostrar_planificar_full") else None,
        )
        badges.append(badge_full_vacio)

    # -----------------------------------------------------------------
    # BADGE: INGRESO DE FABRICA
    # -----------------------------------------------------------------
    if ultimo_fabrica:
        estado_fab = str(ultimo_fabrica.get("estado", "")).lower()
        porc_fab = float(ultimo_fabrica.get("porcentaje", 0.0))
        tot_fab = int(ultimo_fabrica.get("articulos_esperados", 0))
        ctrl_fab = int(ultimo_fabrica.get("articulos_controlados", 0))
        nom_fab = ultimo_fabrica.get("nombre_remito", "Remito Fábrica")

        porc_str_fab = f"{porc_fab:.1f}%" if porc_fab % 1 != 0 else f"{int(porc_fab)}%"
        if estado_fab == "completado":
            texto_fab = f"Fábrica: Cerrado con {porc_str_fab}"
            icono_fab = ft.Icons.CHECK_CIRCLE
            color_fab = ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_700
            bg_fab = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_400)
            borde_fab = ft.Colors.GREEN_700 if es_oscuro else ft.Colors.GREEN_300
            tip_fab = f"Ingreso Fábrica #{ultimo_fabrica['id']} ({nom_fab}): Cerrado ({ctrl_fab}/{tot_fab} un.). Clic para ver."
        elif estado_fab in ("en_proceso", "pendiente"):
            texto_fab = f"Fábrica: {porc_str_fab} (En control)"
            icono_fab = ft.Icons.INVENTORY_2
            color_fab = ft.Colors.BLUE_400 if es_oscuro else ft.Colors.BLUE_800
            bg_fab = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_400)
            borde_fab = ft.Colors.BLUE_600 if es_oscuro else ft.Colors.BLUE_400
            tip_fab = f"Ingreso Fábrica #{ultimo_fabrica['id']} ({nom_fab}): En control ({ctrl_fab}/{tot_fab} un.). Clic para monitorear."
        else:
            texto_fab = "Fábrica: Cancelado"
            icono_fab = ft.Icons.CANCEL
            color_fab = ft.Colors.GREY_400
            bg_fab = ft.Colors.with_opacity(0.12, ft.Colors.GREY_400)
            borde_fab = ft.Colors.GREY_500
            tip_fab = f"Ingreso Fábrica #{ultimo_fabrica['id']} ({nom_fab}): {estado_fab}."

        badge_fab = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icono_fab, size=13, color=color_fab),
                    ft.Text(texto_fab, size=11, weight=ft.FontWeight.BOLD, color=color_fab),
                ],
                spacing=5,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=12,
            bgcolor=bg_fab,
            border=ft.Border.all(1, borde_fab),
            tooltip=tip_fab,
            ink=True,
            on_click=lambda _e: interfaz.mostrar_planificar_ingreso_fabrica() if hasattr(interfaz, "mostrar_planificar_ingreso_fabrica") else None,
        )
        badges.append(badge_fab)
    else:
        badge_fab_vacio = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.INVENTORY_2, size=14, color=ft.Colors.BLUE_GREY_400),
                    ft.Text("Fábrica: Sin remitos activos", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_GREY_400 if es_oscuro else ft.Colors.BLUE_GREY_700),
                ],
                spacing=5,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE_GREY_400),
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_700 if es_oscuro else ft.Colors.GREY_300),
            tooltip="No hay remitos de fábrica activos. Clic para planificar.",
            ink=True,
            on_click=lambda _e: interfaz.mostrar_planificar_ingreso_fabrica() if hasattr(interfaz, "mostrar_planificar_ingreso_fabrica") else None,
        )
        badges.append(badge_fab_vacio)

    # Actualizar contenedor en desktop si existe
    if hasattr(interfaz, "panel_seguimiento_admin") and interfaz.panel_seguimiento_admin:
        fila = getattr(interfaz.panel_seguimiento_admin, "content", None)
        if fila and hasattr(fila, "controls"):
            fila.controls = list(badges)
            interfaz.panel_seguimiento_admin.visible = True

    # Actualizar contenedor en móvil si existe
    if hasattr(interfaz, "panel_seguimiento_admin_movil") and interfaz.panel_seguimiento_admin_movil:
        fila_m = getattr(interfaz.panel_seguimiento_admin_movil, "content", None)
        if fila_m and hasattr(fila_m, "controls"):
            fila_m.controls = list(badges)
            interfaz.panel_seguimiento_admin_movil.visible = True
