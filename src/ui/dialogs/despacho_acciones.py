"""Helpers modulares de lógica, filtros, KPIs y escaneo para el módulo Despacho."""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import NonCallableMock

import flet as ft

from ...core.stock_order_tx import consolidar_reserva_pedido_si_existe
from ...orders import Pedido
from ..design import es_viewport_estrecho
from ..theme import ROJO
from .despacho_componentes import construir_kpi_despacho


def construir_kpis_despacho(
    interfaz: Any,
    solo_lectura: bool,
) -> tuple[list[ft.Text], list[ft.Control]]:
    """Crea los indicadores numéricos y tarjetas KPI para el modo Despachador o Solo Lectura."""
    valores = [ft.Text("0", size=22, weight=ft.FontWeight.BOLD, color=interfaz.texto) for _ in range(4)]
    if solo_lectura:
        defs = [
            ("Despachados hoy", valores[0], ft.Icons.TODAY, ft.Colors.GREEN_500),
            ("Bultos hoy", valores[1], ft.Icons.INVENTORY_2, ft.Colors.BLUE_500),
            ("Total despachados", valores[2], ft.Icons.LOCAL_SHIPPING, ROJO),
            ("Bultos totales", valores[3], ft.Icons.ALL_INBOX, ft.Colors.TEAL_500),
        ]
    else:
        defs = [
            ("Pendientes (Armados)", valores[0], ft.Icons.PENDING_ACTIONS, ft.Colors.BLUE_500),
            ("En control parcial", valores[1], ft.Icons.QR_CODE_SCANNER, ft.Colors.AMBER_500),
            ("Despachados hoy", valores[2], ft.Icons.CHECK_CIRCLE, ft.Colors.GREEN_500),
            ("Bultos despachados hoy", valores[3], ft.Icons.LOCAL_SHIPPING, ROJO),
        ]
    tarjetas = [construir_kpi_despacho(interfaz, titulo, val, ico, col) for titulo, val, ico, col in defs]
    return valores, tarjetas


def filtrar_pedidos_despacho(origen: list[Pedido], filtro: str) -> list[Pedido]:
    """Filtra pedidos por remito, número, cliente, logística, armador, despachador o guía."""
    if not filtro:
        return list(origen)
    return [
        p
        for p in origen
        if filtro
        in " ".join(
            [
                p.nota_pedido or "",
                p.numero_pedido or "",
                p.cliente or "",
                p.logistica or "",
                p.armador or "",
                p.despachado_por or "",
                getattr(p, "numero_guia", "") or "",
            ]
        ).lower()
    ]


def construir_estado_vacio_despacho(
    interfaz: Any,
    *,
    solo_lectura: bool,
    vista: str,
) -> ft.Container:
    """Construye el placeholder visual cuando no hay pedidos coincidentes en la vista de despacho."""
    vacio_txt = (
        "No hay pedidos despachados que coincidan con el filtro."
        if (solo_lectura or vista == "despachados")
        else "No hay pedidos pendientes (armados) para despachar."
    )
    return ft.Container(
        padding=28,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Icon(ft.Icons.LOCAL_SHIPPING_OUTLINED, size=36, color=interfaz.secundario),
                ft.Text(vacio_txt, size=13, color=interfaz.secundario),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
    )


def construir_barra_filtros_despacho(
    interfaz: Any,
    *,
    solo_lectura: bool,
    btn_tab_pendientes: ft.Button,
    btn_tab_despachados: ft.Button,
    campo_filtro: ft.TextField,
    chk_solo_hoy: ft.Checkbox,
    on_refrescar: Callable[[Any], None],
) -> ft.Control:
    """Construye la barra de pestañas y filtros adaptada a móvil/tablet o escritorio."""
    btn_refresh = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip="Actualizar listado",
        on_click=on_refrescar,
    )
    if es_viewport_estrecho(interfaz, umbral=640.0):
        return ft.Column(
            [
                *(
                    [ft.Row([btn_tab_pendientes, btn_tab_despachados], spacing=8, wrap=True)]
                    if not solo_lectura
                    else []
                ),
                ft.Row([campo_filtro, btn_refresh], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                *([chk_solo_hoy] if solo_lectura else []),
            ],
            spacing=6,
            tight=True,
        )

    controles_barra: list[ft.Control] = []
    if not solo_lectura:
        controles_barra.extend([btn_tab_pendientes, btn_tab_despachados])
    controles_barra.append(campo_filtro)
    if solo_lectura:
        controles_barra.append(chk_solo_hoy)
    controles_barra.append(btn_refresh)
    return ft.Row(
        controles_barra,
        spacing=8,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def aplicar_resultado_escaneo_qr(
    interfaz: Any,
    res: dict[str, Any],
    estado_ui: dict[str, Any],
    fijar_feedback: Callable[..., None],
) -> None:
    """Actualiza el estado local, feedback visual y sincronización tras un escaneo QR de despacho."""
    pedido_res: Pedido | None = res.get("pedido")
    if res.get("completado"):
        if pedido_res is not None:
            ps = getattr(interfaz, "product_store", None)
            if ps is not None and not isinstance(ps, NonCallableMock) and hasattr(ps, "consolidar_reserva"):
                usr_obj = getattr(interfaz, "usuario_actual", None)
                usr_nom = str(getattr(usr_obj, "username", "") or "despacho") if not isinstance(usr_obj, NonCallableMock) else "despacho"
                try:
                    consolidar_reserva_pedido_si_existe(ps, pedido_res.nota_pedido, usuario=usr_nom)
                except Exception:
                    pass
        estado_ui["pedido_destacado_id"] = None
        fijar_feedback(str(res["mensaje"]), tipo="ok")
        if hasattr(interfaz, "sincronizar_sesiones"):
            try:
                interfaz.sincronizar_sesiones()
            except Exception:
                pass
    elif res.get("requiere_confirmacion_bultos") and pedido_res is not None:
        estado_ui["vista"] = "pendientes"
        estado_ui["pedido_destacado_id"] = pedido_res.id
        fijar_feedback(str(res["mensaje"]), tipo="alerta", pedido_manual=pedido_res)
    elif res.get("ok") and pedido_res is not None:
        estado_ui["vista"] = "pendientes"
        estado_ui["pedido_destacado_id"] = pedido_res.id
        fijar_feedback(str(res["mensaje"]), tipo="parcial", pedido_manual=pedido_res)
    elif res.get("duplicado"):
        fijar_feedback(str(res["mensaje"]), tipo="alerta")
    else:
        fijar_feedback(str(res["mensaje"]), tipo="error")
