"""Widgets compartidos y exportación Excel para las vistas analíticas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import flet as ft
import openpyxl

from ..theme import ROJO
from ._shared import resolve_stock_manager


def resolver_stock_manager_analytics(interfaz: Any = None):
    """Resuelve StockManager mediante inyección en `interfaz`."""
    return resolve_stock_manager(interfaz)


def parsear_fecha_iso(texto: str) -> str | None:
    """Convierte una fecha DD/MM/AAAA, DD-MM-AAAA o YYYY-MM-DD a ISO YYYY-MM-DD."""
    limpio = (texto or "").strip()
    if not limpio:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(limpio, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def tarjeta_kpi_analytics(
    interfaz: Any,
    titulo: str,
    valor: str,
    icono: str,
    color_ico: str,
) -> ft.Container:
    """Construye una tarjeta KPI uniforme para el dashboard."""
    return ft.Container(
        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.WHITE,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=10,
        expand=True,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(icono, color=color_ico, size=18),
                        ft.Text(
                            titulo,
                            size=11,
                            color=interfaz.secundario,
                            weight=ft.FontWeight.W_500,
                            expand=True,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Text(valor, size=18, weight=ft.FontWeight.BOLD, color=interfaz.texto, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=3,
        ),
    )


def fila_progreso_metrica(
    interfaz: Any,
    etiqueta: str,
    cant_texto: str,
    bultos: int,
    ratio: float,
    color_barra: str,
) -> ft.Column:
    """Construye una fila con barra de progreso para distribución logística o armadores."""
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text(etiqueta, size=12, weight=ft.FontWeight.W_500, expand=True, color=interfaz.texto, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(cant_texto, size=11, color=interfaz.secundario),
                    ft.Text(f"{bultos} bultos", size=11, weight=ft.FontWeight.BOLD, color=ROJO),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.ProgressBar(
                value=max(0.01, min(1.0, ratio)),
                color=color_barra,
                bgcolor=ft.Colors.GREY_800 if interfaz.modo_oscuro else ft.Colors.GREY_200,
                height=4,
                border_radius=2,
            ),
        ],
        spacing=2,
    )


def tarjeta_tabla_metrica(
    interfaz: Any,
    titulo: str,
    contenido: ft.Column,
    mensaje_vacio: str = "Sin datos",
) -> ft.Container:
    """Envuelve una lista de métricas dentro de una tarjeta del dashboard."""
    return ft.Container(
        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.WHITE,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=10,
        expand=True,
        content=ft.Column(
            [
                ft.Text(titulo, size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ft.Divider(height=4),
                contenido if contenido.controls else ft.Text(mensaje_vacio, size=11, color=interfaz.secundario),
            ],
            spacing=4,
        ),
    )


def exportar_dashboard_excel(interfaz: Any, metricas: dict) -> None:
    """Genera y abre el Excel resumen de métricas del dashboard."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dashboard Depósito"
    ws.append(["REPORTE DE MÉTRICAS Y RENDIMIENTO DEL DEPÓSITO"])
    ws.append(["Fecha de generación", datetime.now().strftime("%d/%m/%Y %H:%M")])
    ws.append(["Período filtrado", f"{metricas.get('fecha_desde') or 'Inicio'} a {metricas.get('fecha_hasta') or 'Hoy'}"])
    ws.append([])
    ws.append(["INDICADOR", "VALOR"])
    ws.append(["Total Pedidos Activos", metricas["total_pedidos"]])
    ws.append(["Total Bultos", metricas["total_bultos"]])
    est = metricas.get("estados_despacho", {})
    ws.append(["Pedidos Armados", est.get("armado", 0)])
    ws.append(["Pedidos Despachados", est.get("despachado", 0)])
    ws.append(["Pedidos Entregados", est.get("entregado", 0)])
    ws.append(["Cierres de Jornada", metricas["total_cierres"]])
    ws.append([])
    ws.append(["LOGÍSTICA", "PEDIDOS", "BULTOS"])
    for log, cant, bultos in metricas["distribucion_logistica"]:
        ws.append([log, cant, bultos])
    ws.append([])
    ws.append(["ARMADOR", "PEDIDOS", "BULTOS"])
    for arm, cant, bultos in metricas["rendimiento_armadores"]:
        ws.append([arm, cant, bultos])
    ws.append([])
    ws.append(["CÓDIGO", "PRODUCTO", "UNIDADES ROTADAS"])
    for cod, desc, cant in metricas["top_articulos"]:
        ws.append([cod, desc, cant])

    carpeta_out = interfaz.menu.carpeta_descuentos
    carpeta_out.mkdir(parents=True, exist_ok=True)
    ruta_out = carpeta_out / f"Dashboard_Metricas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(ruta_out)
    wb.close()
    interfaz.actualizar_estado()
    interfaz.abrir_informe(ruta_especifica=ruta_out)
