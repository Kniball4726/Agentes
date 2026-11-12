"""Diálogo modal para el Centro Unificado de Reportes de StockAgent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import flet as ft

from ...paths import application_root
from ...stock.reportes_service import (
    generar_reporte_stock_critico,
    generar_reporte_catalogo_stock,
    generar_reporte_pedidos_despacho,
    generar_reporte_cierres_historicos,
)
from ..theme import ROJO

logger = logging.getLogger(__name__)


def mostrar_centro_reportes(interfaz: Any) -> None:
    """Abre la ventana modal del Centro Unificado de Reportes."""
    if not interfaz.usuario_actual:
        interfaz.notificar("Debes iniciar sesión para acceder a los reportes.")
        return

    usuario_nombre = interfaz.usuario_actual.display_name
    carpeta_informes = Path(application_root()) / "data" / "informes"
    carpeta_informes.mkdir(parents=True, exist_ok=True)

    # Estado de selección
    tipo_reporte = ft.Dropdown(
        label="Seleccionar Tipo de Reporte",
        value="stock_critico",
        options=[
            ft.DropdownOption("stock_critico", "📦 Stock Crítico y Reposición (Quiebres y Compras)"),
            ft.DropdownOption("catalogo_stock", "📋 Inventario y Catálogo General"),
            ft.DropdownOption("pedidos_despacho", "🚚 Despacho y Pedidos por Logística"),
            ft.DropdownOption("cierres_historicos", "🔒 Historial de Cierres de Jornada"),
        ],
        dense=True,
        expand=True,
    )

    descripcion_reporte = ft.Text(
        "Detalla los artículos agotados o por debajo del punto de reposición con cantidad sugerida.",
        size=12,
        color=interfaz.secundario,
    )

    transporte_filtro = ft.Dropdown(
        label="Filtrar por Transporte / Logística (Opcional)",
        value="TODOS",
        options=[ft.DropdownOption("TODOS", "Todos los transportes")],
        dense=True,
        visible=False,
    )

    # Cargar transportes disponibles si aplica
    try:
        from ...orders_store import LOGISTICA_OPCIONES
        for log in LOGISTICA_OPCIONES:
            transporte_filtro.options.append(ft.DropdownOption(log, log))
    except Exception:
        pass

    def al_cambiar_tipo(_e: ft.Event | None = None) -> None:
        sel = tipo_reporte.value
        if sel == "stock_critico":
            descripcion_reporte.value = "Detalla los artículos agotados o por debajo del punto de reposición con cantidad sugerida para compras."
            transporte_filtro.visible = False
        elif sel == "catalogo_stock":
            descripcion_reporte.value = "Listado completo del catálogo activo con existencias reales, códigos de barras y ubicaciones."
            transporte_filtro.visible = False
        elif sel == "pedidos_despacho":
            descripcion_reporte.value = "Consolidado de pedidos preparados y despachados con cliente, bultos, armador y logística asignada."
            transporte_filtro.visible = True
        elif sel == "cierres_historicos":
            descripcion_reporte.value = "Registro histórico de jornadas operativas cerradas, métricas de bultos y auditoría de responsables."
            transporte_filtro.visible = False
        if interfaz.page:
            interfaz.page.update()

    tipo_reporte.on_change = al_cambiar_tipo

    estado_indicador = ft.Text("", size=12, color=ft.Colors.GREEN_400, visible=False)
    progreso = ft.ProgressBar(visible=False, height=4)

    def ejecutar_generacion(formato: str) -> None:
        progreso.visible = True
        estado_indicador.visible = True
        estado_indicador.value = f"Generando reporte en formato {formato.upper()}..."
        estado_indicador.color = interfaz.secundario
        if interfaz.page:
            interfaz.page.update()

        try:
            sel = tipo_reporte.value
            ruta_generada: Path | None = None

            if sel == "stock_critico":
                ruta_generada = generar_reporte_stock_critico(
                    product_store=interfaz.product_store,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                )
            elif sel == "catalogo_stock":
                ruta_generada = generar_reporte_catalogo_stock(
                    product_store=interfaz.product_store,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                )
            elif sel == "pedidos_despacho":
                f_trans = None if transporte_filtro.value == "TODOS" else transporte_filtro.value
                ruta_generada = generar_reporte_pedidos_despacho(
                    order_store=interfaz.order_store,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                    filtro_transporte=f_trans,
                )
            elif sel == "cierres_historicos":
                ruta_generada = generar_reporte_cierres_historicos(
                    order_store=interfaz.order_store,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                )

            progreso.visible = False
            if ruta_generada and ruta_generada.exists():
                estado_indicador.value = f"Reporte generado con éxito: {ruta_generada.name}"
                estado_indicador.color = ft.Colors.GREEN_400
                if interfaz.page:
                    interfaz.page.update()

                # Abrir inmediatamente con el visor unificado
                interfaz.abrir_informe(ruta_especifica=ruta_generada)
            else:
                estado_indicador.value = "No se pudo generar el reporte solicitado."
                estado_indicador.color = ft.Colors.RED_400
                if interfaz.page:
                    interfaz.page.update()
        except Exception as exc:
            logger.error("Error al generar reporte: %s", exc, exc_info=True)
            progreso.visible = False
            estado_indicador.value = f"Error al generar reporte: {exc}"
            estado_indicador.color = ft.Colors.RED_400
            if interfaz.page:
                interfaz.page.update()

    btn_pdf = ft.Button(
        "Generar PDF (Ver / Imprimir)",
        icon=ft.Icons.PICTURE_AS_PDF,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        height=42,
        on_click=lambda _: ejecutar_generacion("pdf"),
        tooltip="Abre el informe en el visor web para visualizar o imprimir directamente",
    )

    btn_excel = ft.Button(
        "Exportar Excel (.xlsx)",
        icon=ft.Icons.TABLE_CHART,
        bgcolor=ft.Colors.GREEN_700,
        color=ft.Colors.WHITE,
        height=42,
        on_click=lambda _: ejecutar_generacion("xlsx"),
        tooltip="Exporta los datos tabulados a una planilla de cálculo Excel",
    )

    contenido = ft.Container(
        width=580,
        padding=16,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.ASSESSMENT, size=28, color=ROJO),
                        ft.Column(
                            [
                                ft.Text("Centro Unificado de Reportes", size=18, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                                ft.Text("Genera informes operativos, de stock y despacho para visualización e impresión.", size=11, color=interfaz.secundario),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(color=interfaz.borde),
                ft.Text("Parámetros del Reporte", weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                tipo_reporte,
                ft.Container(
                    content=descripcion_reporte,
                    padding=ft.Padding.only(left=4, bottom=6),
                ),
                transporte_filtro,
                ft.Container(height=6),
                progreso,
                estado_indicador,
                ft.Container(height=10),
                ft.Text("Selecciona el formato de salida:", size=12, weight=ft.FontWeight.W_500, color=interfaz.texto),
                ft.Row(
                    [btn_pdf, btn_excel],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            spacing=10,
            tight=True,
        ),
    )

    dialogo = ft.AlertDialog(
        content=contenido,
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
