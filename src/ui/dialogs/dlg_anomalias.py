"""Diálogo modal para el Radar de Consumo Anómalo y Detección de Desvíos de Demanda."""

from datetime import datetime
from typing import Any
import flet as ft

from ...anomaly_detector import (
    AlertaConsumoAnomalo,
    ejecutar_diagnostico_integral_anomalias,
    notificar_anomalias_detectadas,
)
from ..theme import ROJO


def mostrar_dialogo_anomalias(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Ventana analítica para visualizar desvíos de demanda, picos inusuales y velocidad de agotamiento."""
    if not interfaz.exigir_roles("administrador", "master"):
        return

    # Contenedores de las 3 categorías
    lista_picos = ft.ListView(expand=True, spacing=6, height=330)
    lista_masivos = ft.ListView(expand=True, spacing=6, height=330)
    lista_agotamiento = ft.ListView(expand=True, spacing=6, height=330)

    # Indicadores KPI
    kpi_picos = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)
    kpi_masivos = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)
    kpi_agotamiento = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400)

    alertas_actuales: dict[str, list[AlertaConsumoAnomalo]] = {"picos": [], "descuentos_masivos": [], "agotamiento": []}

    def crear_tarjeta_alerta(alerta: AlertaConsumoAnomalo) -> ft.Container:
        color_sev = ft.Colors.RED_400 if alerta.severidad == "CRITICA" else (
            ft.Colors.AMBER_400 if alerta.severidad == "ALTA" else ft.Colors.BLUE_400
        )
        bg_sev = ft.Colors.RED_900 if alerta.severidad == "CRITICA" else (
            ft.Colors.AMBER_900 if alerta.severidad == "ALTA" else ft.Colors.BLUE_900
        )

        return ft.Container(
            bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
            border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
            border_radius=8,
            padding=10,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"[{alerta.codigo}]", weight=ft.FontWeight.BOLD, size=12),
                                    ft.Text(alerta.nombre, weight=ft.FontWeight.W_500, size=12, expand=True, no_wrap=True),
                                ],
                                expand=True,
                                spacing=6,
                            ),
                            ft.Container(
                                content=ft.Text(alerta.severidad, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                bgcolor=bg_sev,
                                padding=ft.Padding(6, 2, 6, 2),
                                border_radius=4,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(alerta.mensaje, size=11, color=interfaz.secundario),
                    ft.Row(
                        [
                            ft.Text(
                                f"Consumo: {alerta.consumo_detectado} un. | Stock actual: {alerta.stock_actual} un.",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=color_sev,
                            ),
                            ft.Text(
                                f"Cobertura: {alerta.dias_cobertura} días" if alerta.dias_cobertura is not None else "",
                                size=11,
                                color=interfaz.secundario,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=4,
            ),
        )

    def actualizar_datos() -> None:
        try:
            from ...stock_manager import StockManager
            sm = StockManager(interfaz.menu.ruta_excel_base)
            diag = ejecutar_diagnostico_integral_anomalias(sm.product_store)
        except Exception as e:
            interfaz.notificar(f"Error al analizar anomalías: {e}")
            return

        alertas_actuales["picos"] = diag.get("picos", [])
        alertas_actuales["descuentos_masivos"] = diag.get("descuentos_masivos", [])
        alertas_actuales["agotamiento"] = diag.get("agotamiento", [])

        # Actualizar contadores KPI
        kpi_picos.value = str(len(alertas_actuales["picos"]))
        kpi_masivos.value = str(len(alertas_actuales["descuentos_masivos"]))
        kpi_agotamiento.value = str(len(alertas_actuales["agotamiento"]))

        # Renderizar Picos
        lista_picos.controls.clear()
        if not alertas_actuales["picos"]:
            lista_picos.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("✅ No se detectaron picos anómalos de demanda hoy.", color=interfaz.secundario),
                )
            )
        else:
            for a in alertas_actuales["picos"]:
                lista_picos.controls.append(crear_tarjeta_alerta(a))

        # Renderizar Descuentos Masivos
        lista_masivos.controls.clear()
        if not alertas_actuales["descuentos_masivos"]:
            lista_masivos.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("✅ No hay comprobantes con salidas individuales superiores al 50% de stock.", color=interfaz.secundario),
                )
            )
        else:
            for a in alertas_actuales["descuentos_masivos"]:
                lista_masivos.controls.append(crear_tarjeta_alerta(a))

        # Renderizar Agotamiento Acelerado
        lista_agotamiento.controls.clear()
        if not alertas_actuales["agotamiento"]:
            lista_agotamiento.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("✅ Ningún artículo presenta proyección crítica de agotamiento (< 3 días).", color=interfaz.secundario),
                )
            )
        else:
            for a in alertas_actuales["agotamiento"]:
                lista_agotamiento.controls.append(crear_tarjeta_alerta(a))

        interfaz.page.update()

    def enviar_alertas_telegram(_e: ft.Event | None = None) -> None:
        todas = alertas_actuales["picos"] + alertas_actuales["descuentos_masivos"] + alertas_actuales["agotamiento"]
        if not todas:
            interfaz.notificar("No hay anomalías detectadas para notificar.")
            return

        from ...stock_manager import StockManager
        sm = StockManager(interfaz.menu.ruta_excel_base)
        enviadas = notificar_anomalias_detectadas(todas, sm.product_store, notificar_telegram=True)
        interfaz.notificar(f"Se registraron y despacharon {enviadas} alertas analíticas correctamente.")

    # Cabecera KPI
    def crear_caja_kpi(titulo: str, control_val: ft.Text, icon_name: str, color_ico: str) -> ft.Container:
        return ft.Container(
            bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
            border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
            border_radius=8,
            padding=8,
            expand=True,
            content=ft.Row(
                [
                    ft.Icon(icon_name, color=color_ico, size=24),
                    ft.Column(
                        [
                            ft.Text(titulo, size=11, color=interfaz.secundario),
                            control_val,
                        ],
                        spacing=1,
                    ),
                ],
                spacing=8,
            ),
        )

    fila_kpis = ft.Row(
        [
            crear_caja_kpi("Picos de Demanda", kpi_picos, ft.Icons.BOLT, ft.Colors.AMBER_400),
            crear_caja_kpi("Descuentos > 50%", kpi_masivos, ft.Icons.WARNING_ROUNDED, ft.Colors.RED_400),
            crear_caja_kpi("Agotamiento < 3d", kpi_agotamiento, ft.Icons.HOURGLASS_BOTTOM, ft.Colors.ORANGE_400),
        ],
        spacing=8,
    )

    tabs = ft.Tabs(
        length=3,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Picos Inusuales", icon=ft.Icons.BOLT),
                        ft.Tab(label="Descuentos Masivos", icon=ft.Icons.OUTPUT),
                        ft.Tab(label="Agotamiento Acelerado", icon=ft.Icons.HOURGLASS_EMPTY),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[lista_picos, lista_masivos, lista_agotamiento],
                ),
            ],
        ),
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.AUTO_GRAPH, color=ROJO),
                ft.Text("Radar de Consumo Anómalo y Desvíos de Demanda", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            content=ft.Column(
                [
                    fila_kpis,
                    ft.Divider(height=10, color=interfaz.borde),
                    tabs,
                ],
                spacing=6,
                expand=True,
            ),
            width=680,
            height=480,
        ),
        actions=[
            ft.OutlinedButton(
                "Notificar por Telegram",
                icon=ft.Icons.SEND,
                on_click=enviar_alertas_telegram,
            ),
            ft.Button(
                "Actualizar",
                icon=ft.Icons.REFRESH,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=lambda _e: actualizar_datos(),
            ),
            ft.TextButton("Cerrar", on_click=lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
    actualizar_datos()
