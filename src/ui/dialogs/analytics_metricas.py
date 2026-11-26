"""Vistas analíticas de métricas y rendimiento del depósito (dashboard y exportación)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import flet as ft

from ..design import es_viewport_estrecho, grilla_tarjetas_responsiva
from ..theme import ROJO
from .analytics_rotacion import mostrar_estadisticas
from .analytics_widgets import (
    exportar_dashboard_excel as _exportar_dashboard_excel,
    fila_progreso_metrica as _fila_progreso_metrica,
    parsear_fecha_iso as _parsear_fecha_iso,
    resolver_stock_manager_analytics as _resolver_stock_manager,
    tarjeta_kpi_analytics as _tarjeta_kpi,
    tarjeta_tabla_metrica as _tarjeta_tabla_metrica,
)

__all__ = [
    "mostrar_dashboard_metricas",
    "mostrar_estadisticas",
    "_resolver_stock_manager",
    "_parsear_fecha_iso",
    "_tarjeta_kpi",
    "_fila_progreso_metrica",
    "_tarjeta_tabla_metrica",
    "_exportar_dashboard_excel",
]


def _construir_filas_metricas_dashboard(interfaz: Any, m: dict) -> tuple[ft.ResponsiveRow, ft.ResponsiveRow, ft.Container]:
    """Construye los bloques visuales principales (KPIs, tablas y evolución diaria) del dashboard."""
    promedio_bultos = (m["total_bultos"] / m["total_pedidos"]) if m["total_pedidos"] > 0 else 0
    est_desp = m.get("estados_despacho", {})

    kpis = grilla_tarjetas_responsiva(
        [
            _tarjeta_kpi(interfaz, "Total Pedidos", str(m["total_pedidos"]), ft.Icons.INVENTORY, ft.Colors.BLUE_500),
            _tarjeta_kpi(interfaz, "Total Bultos", str(m["total_bultos"]), ft.Icons.LOCAL_SHIPPING, ft.Colors.AMBER_600),
            _tarjeta_kpi(interfaz, "Prom. Bultos", f"{promedio_bultos:.1f}", ft.Icons.CALCULATE, ft.Colors.TEAL_500),
            _tarjeta_kpi(interfaz, "📦 Armados", str(est_desp.get("armado", 0)), ft.Icons.INVENTORY_2, ft.Colors.BLUE_400),
            _tarjeta_kpi(interfaz, "🚚 Despachados", str(est_desp.get("despachado", 0)), ft.Icons.LOCAL_SHIPPING, ft.Colors.AMBER_500),
            _tarjeta_kpi(interfaz, "✔ Entregados", str(est_desp.get("entregado", 0)), ft.Icons.VERIFIED, ft.Colors.GREEN_500),
        ],
        interfaz=interfaz,
        compacto=True,
        spacing=8,
        run_spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    filas_logistica = ft.Column(spacing=6)
    for log, cant, bultos in m["distribucion_logistica"]:
        porc = (cant / m["total_pedidos"] * 100) if m["total_pedidos"] > 0 else 0
        filas_logistica.controls.append(
            _fila_progreso_metrica(interfaz, log, f"{cant} ped. ({porc:.0f}%)", bultos, porc / 100.0, ROJO)
        )

    filas_armadores = ft.Column(spacing=6)
    max_ped_arm = max([cant for _, cant, _ in m["rendimiento_armadores"]], default=1) or 1
    for arm, cant, bultos in m["rendimiento_armadores"]:
        filas_armadores.controls.append(
            _fila_progreso_metrica(interfaz, arm, f"{cant} ped.", bultos, cant / max_ped_arm, ft.Colors.BLUE_500)
        )

    filas_top = ft.Column(spacing=4)
    for idx, (cod, desc, cant) in enumerate(m["top_articulos"], start=1):
        filas_top.controls.append(
            ft.Row(
                [
                    ft.Text(f"{idx}. {cod}", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Text(desc[:26] + ("..." if len(desc) > 26 else ""), size=11, color=interfaz.secundario, expand=True),
                    ft.Text(f"{cant} un.", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600),
                ],
                spacing=6,
            )
        )

    filas_dias = ft.Column(spacing=4)
    por_dia = m.get("pedidos_por_dia", [])
    max_ped_dia = max((c for _, c, _ in por_dia), default=1) or 1
    max_ancho_dia = 80 if es_viewport_estrecho(interfaz, umbral=640.0) else 160
    for dia_str, cant_d, bultos_d in por_dia[:10]:
        ancho = max(10, int((cant_d / max_ped_dia) * max_ancho_dia))
        filas_dias.controls.append(
            ft.Row(
                [
                    ft.Text(dia_str, size=11, width=78, color=interfaz.texto),
                    ft.Container(width=ancho, height=14, bgcolor=ROJO, border_radius=4),
                    ft.Text(
                        f"{cant_d} ped. ({bultos_d} bultos)",
                        size=11,
                        color=interfaz.secundario,
                        expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

    seccion_tablas = grilla_tarjetas_responsiva(
        [
            _tarjeta_tabla_metrica(interfaz, "Despacho por Logística", filas_logistica),
            _tarjeta_tabla_metrica(interfaz, "Rendimiento de Armadores", filas_armadores),
            _tarjeta_tabla_metrica(interfaz, "Top 10 Productos Rotados", filas_top),
        ],
        interfaz=interfaz,
        compacto=False,
        spacing=8,
        run_spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )
    bloque_dias = _tarjeta_tabla_metrica(
        interfaz,
        "Evolución Diaria de Pedidos y Bultos",
        filas_dias,
        mensaje_vacio="Sin registros en este período",
    )
    return kpis, seccion_tablas, bloque_dias


def mostrar_dashboard_metricas(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Dashboard de métricas, rendimiento de operarios y distribución logística."""
    if not interfaz.exigir_roles("administrador"):
        return

    hoy_dt = datetime.now()
    hace_30_dt = hoy_dt - timedelta(days=30)
    input_desde = ft.TextField(label="Desde (DD/MM/AAAA)", value=hace_30_dt.strftime("%d/%m/%Y"), width=155, dense=True)
    input_hasta = ft.TextField(label="Hasta (DD/MM/AAAA)", value=hoy_dt.strftime("%d/%m/%Y"), width=155, dense=True)
    contenedor_cuerpo = ft.Column(spacing=10, tight=True)
    metricas_actuales: list[dict] = [{}]

    def render_dashboard(usar_rango: bool = False) -> None:
        f_d = _parsear_fecha_iso(input_desde.value or "") if usar_rango else None
        f_h = _parsear_fecha_iso(input_hasta.value or "") if usar_rango else None
        m = interfaz.order_store.obtener_metricas_dashboard(fecha_desde=f_d, fecha_hasta=f_h)
        metricas_actuales[0] = m
        kpis, seccion_tablas, bloque_dias = _construir_filas_metricas_dashboard(interfaz, m)
        contenedor_cuerpo.controls.clear()
        contenedor_cuerpo.controls.extend([kpis, seccion_tablas, bloque_dias])
        interfaz.page.update()

    def on_exportar(_ev: ft.Event) -> None:
        m = metricas_actuales[0] or interfaz.order_store.obtener_metricas_dashboard()
        _exportar_dashboard_excel(interfaz, m)

    render_dashboard(usar_rango=False)

    barra_filtros = ft.Row(
        [
            input_desde,
            input_hasta,
            ft.Button("Filtrar rango", icon=ft.Icons.FILTER_ALT, bgcolor=ROJO, color=ft.Colors.WHITE, on_click=lambda _ev: render_dashboard(usar_rango=True)),
            ft.TextButton("Ver histórico completo", icon=ft.Icons.ALL_INCLUSIVE, on_click=lambda _ev: render_dashboard(usar_rango=False)),
            ft.Button("Exportar Excel", icon=ft.Icons.DOWNLOAD, on_click=on_exportar),
        ],
        spacing=8,
        run_spacing=8,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    ancho_dlg = interfaz.ancho_adaptable(900) if hasattr(interfaz, "ancho_adaptable") else 900
    alto_dlg = interfaz.alto_adaptable(540) if hasattr(interfaz, "alto_adaptable") else 540
    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.INSIGHTS, color=ROJO),
                ft.Text("Métricas y Rendimiento del Depósito", weight=ft.FontWeight.BOLD, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=ancho_dlg,
            height=alto_dlg,
            content=ft.Column([barra_filtros, ft.Divider(height=6), contenedor_cuerpo], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _ev: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
