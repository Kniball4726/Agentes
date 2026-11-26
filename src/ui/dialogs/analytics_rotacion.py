"""Diálogo de gráficos de rotación y movimientos de stock."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import flet as ft

from ..design import es_viewport_estrecho
from ..theme import ROJO
from .analytics_widgets import parsear_fecha_iso, resolver_stock_manager_analytics

_COLORES_BARRA_ROTACION = (
    ft.Colors.RED_700,
    ft.Colors.RED_600,
    ft.Colors.RED_500,
    ft.Colors.RED_400,
    ft.Colors.RED_300,
    ft.Colors.ORANGE_400,
    ft.Colors.ORANGE_300,
    ft.Colors.AMBER_400,
    ft.Colors.AMBER_300,
    ft.Colors.YELLOW_400,
)


def _construir_estado_vacio_estadisticas(interfaz: Any) -> ft.Container:
    """Construye el panel informativo cuando no hay movimientos en el período."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.BAR_CHART_OUTLINED, size=44, color=ft.Colors.GREY_400),
                ft.Text("Sin movimientos en el período", size=13, weight=ft.FontWeight.W_500, color=interfaz.texto),
                ft.Text(
                    "No se detectaron movimientos registrados en las fechas seleccionadas.\n"
                    "Pruebe ampliando el rango o cambiando el tipo de movimiento.",
                    size=11,
                    color=interfaz.secundario,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
        padding=25,
        alignment=ft.Alignment(0, 0),
    )


def mostrar_estadisticas(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana de gráficos y estadísticas de rotación de productos."""
    if not interfaz.exigir_roles("administrador"):
        return

    hoy = datetime.now()
    hace_30_dias = hoy - timedelta(days=30)

    campo_desde = ft.TextField(label="Desde (DD/MM/AAAA)", value=hace_30_dias.strftime("%d/%m/%Y"), width=160, text_size=13)
    campo_hasta = ft.TextField(label="Hasta (DD/MM/AAAA)", value=hoy.strftime("%d/%m/%Y"), width=160, text_size=13)
    campo_top = ft.Dropdown(
        label="Top productos",
        value="15",
        options=[ft.DropdownOption("5"), ft.DropdownOption("10"), ft.DropdownOption("15"), ft.DropdownOption("20"), ft.DropdownOption("50")],
        width=110,
        text_size=13,
    )
    campo_tipo = ft.Dropdown(
        label="Tipo de movimiento",
        value="descuento",
        options=[
            ft.DropdownOption(key="descuento", text="Descuentos (salidas)"),
            ft.DropdownOption(key="ingreso_fabrica", text="Ingresos fábrica"),
            ft.DropdownOption(key="", text="Todos"),
        ],
        width=200,
        text_size=13,
    )

    contenedor_grafico = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=350)
    texto_resumen = ft.Text("", size=12, color=interfaz.secundario)

    def generar_grafico(_e: ft.Event | None = None) -> None:
        contenedor_grafico.controls.clear()

        desde_iso = parsear_fecha_iso(campo_desde.value or "")
        hasta_iso = parsear_fecha_iso(campo_hasta.value or "")
        if not desde_iso or not hasta_iso:
            contenedor_grafico.controls.append(ft.Text("Formato de fecha inválido. Use DD/MM/AAAA.", color=ft.Colors.RED_400, size=13))
            interfaz.page.update()
            return

        top_n = int(campo_top.value or "15")
        tipo = campo_tipo.value or None
        if tipo == "":
            tipo = None

        try:
            sm_cls = resolver_stock_manager_analytics(interfaz)
            try:
                if hasattr(interfaz, "product_store") and hasattr(interfaz.product_store, "database_path"):
                    sm = sm_cls(interfaz.menu.ruta_excel_base, ruta_base_datos=interfaz.product_store.database_path)
                else:
                    sm = sm_cls(interfaz.menu.ruta_excel_base)
            except TypeError:
                sm = sm_cls(interfaz.menu.ruta_excel_base)
            resultados = sm.consultar_movimientos(fecha_desde=desde_iso, fecha_hasta=hasta_iso, tipo=tipo, top_n=top_n)
        except Exception as err:
            contenedor_grafico.controls.append(ft.Text(f"Error: {err}", color=ft.Colors.RED_400, size=13))
            interfaz.page.update()
            return

        if not resultados and (tipo in ("descuento", None)):
            try:
                if hasattr(interfaz, "order_store") and interfaz.order_store:
                    m = interfaz.order_store.obtener_metricas_dashboard(fecha_desde=desde_iso, fecha_hasta=hasta_iso)
                    top_articulos = m.get("top_articulos", [])
                    if top_articulos:
                        resultados = [
                            {"product_code": cod, "product_name": desc, "total_quantity": cant}
                            for cod, desc, cant in top_articulos[:top_n]
                        ]
            except Exception:
                pass

        if not resultados:
            contenedor_grafico.controls.append(_construir_estado_vacio_estadisticas(interfaz))
            texto_resumen.value = "ℹ️ Sin registros en el rango seleccionado."
            interfaz.page.update()
            return

        max_cant = max(row["total_quantity"] for row in resultados)
        total_unidades = sum(row["total_quantity"] for row in resultados)
        total_productos = len(resultados)

        max_barra = 140 if es_viewport_estrecho(interfaz, umbral=640.0) else 340
        for i, row in enumerate(resultados):
            cod = str(row["product_code"])
            nombre = str(row["product_name"] or cod)
            cant = int(row["total_quantity"])
            proporcion = cant / max_cant if max_cant > 0 else 0
            ancho_barra = max(38, int(proporcion * max_barra))
            color_idx = min(i, len(_COLORES_BARRA_ROTACION) - 1)
            etiqueta = f"{nombre[:30]}..." if len(nombre) > 30 else nombre
            contenedor_grafico.controls.append(
                ft.Row(
                    [
                        ft.Text(cod, width=65, size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ft.Container(
                            width=ancho_barra,
                            height=22,
                            bgcolor=_COLORES_BARRA_ROTACION[color_idx],
                            border_radius=ft.BorderRadius(4, 4, 4, 4),
                            alignment=ft.Alignment(-1, 0),
                            padding=ft.Padding(8, 0, 8, 0),
                            content=ft.Text(f"{cant} u.", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                        ),
                        ft.Text(etiqueta, size=11, color=interfaz.secundario, expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        tipo_texto = {"descuento": "descontadas (salidas)", "ingreso_fabrica": "ingresadas (fábrica)"}.get(tipo or "", "movidas")
        texto_resumen.value = (
            f"📊 {total_productos} producto(s) — {total_unidades} unidades {tipo_texto} "
            f"entre {campo_desde.value} y {campo_hasta.value}"
        )
        interfaz.page.update()

    generar_grafico()

    ancho_dlg = interfaz.ancho_adaptable(700) if hasattr(interfaz, "ancho_adaptable") else 700
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Estadísticas de movimiento de stock"),
        content=ft.Column(
            [
                ft.Row([campo_desde, campo_hasta, campo_top, campo_tipo], spacing=8, run_spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
                ft.Button("Actualizar gráfico", icon=ft.Icons.REFRESH, on_click=generar_grafico, bgcolor=ROJO, color=ft.Colors.WHITE),
                ft.Divider(height=1),
                texto_resumen,
                contenedor_grafico,
            ],
            tight=True,
            width=ancho_dlg,
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
