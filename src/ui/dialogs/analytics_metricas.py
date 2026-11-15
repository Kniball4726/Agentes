"""Vistas analíticas de métricas y estadísticas de stock (dashboard y rotación)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Any

import flet as ft
import openpyxl

from ..theme import ROJO
from ._shared import resolve_stock_manager

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


def _resolver_stock_manager():
    """Resuelve StockManager respetando patches sobre dlg_analytics o src.flet_gui."""
    mod_dlg = sys.modules.get("src.ui.dialogs.dlg_analytics")
    if mod_dlg is not None and hasattr(mod_dlg, "_get_stock_manager"):
        return mod_dlg._get_stock_manager()
    return resolve_stock_manager("src.flet_gui")


def _parsear_fecha_iso(texto: str) -> str | None:
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


def _tarjeta_kpi(interfaz: Any, titulo: str, valor: str, icono: str, color_ico: str) -> ft.Container:
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
                        ft.Text(titulo, size=11, color=interfaz.secundario, weight=ft.FontWeight.W_500),
                    ],
                    spacing=6,
                ),
                ft.Text(valor, size=18, weight=ft.FontWeight.BOLD, color=interfaz.texto),
            ],
            spacing=3,
        ),
    )


def _fila_progreso_metrica(
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
                    ft.Text(etiqueta, size=12, weight=ft.FontWeight.W_500, expand=True, color=interfaz.texto),
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


def _tarjeta_tabla_metrica(
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


def _exportar_dashboard_excel(interfaz: Any, metricas: dict) -> None:
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
        promedio_bultos = (m["total_bultos"] / m["total_pedidos"]) if m["total_pedidos"] > 0 else 0
        est_desp = m.get("estados_despacho", {})

        kpis = ft.Row(
            [
                _tarjeta_kpi(interfaz, "Total Pedidos", str(m["total_pedidos"]), ft.Icons.INVENTORY, ft.Colors.BLUE_500),
                _tarjeta_kpi(interfaz, "Total Bultos", str(m["total_bultos"]), ft.Icons.LOCAL_SHIPPING, ft.Colors.AMBER_600),
                _tarjeta_kpi(interfaz, "Prom. Bultos", f"{promedio_bultos:.1f}", ft.Icons.CALCULATE, ft.Colors.TEAL_500),
                _tarjeta_kpi(interfaz, "📦 Armados", str(est_desp.get("armado", 0)), ft.Icons.INVENTORY_2, ft.Colors.BLUE_400),
                _tarjeta_kpi(interfaz, "🚚 Despachados", str(est_desp.get("despachado", 0)), ft.Icons.LOCAL_SHIPPING, ft.Colors.AMBER_500),
                _tarjeta_kpi(interfaz, "✔ Entregados", str(est_desp.get("entregado", 0)), ft.Icons.VERIFIED, ft.Colors.GREEN_500),
            ],
            spacing=8,
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
        for dia_str, cant_d, bultos_d in por_dia[:10]:
            ancho = max(10, int((cant_d / max_ped_dia) * 160))
            filas_dias.controls.append(
                ft.Row(
                    [
                        ft.Text(dia_str, size=11, width=85, color=interfaz.texto),
                        ft.Container(width=ancho, height=14, bgcolor=ROJO, border_radius=4),
                        ft.Text(f"{cant_d} ped. ({bultos_d} bultos)", size=11, color=interfaz.secundario),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        seccion_tablas = ft.Row(
            [
                _tarjeta_tabla_metrica(interfaz, "Despacho por Logística", filas_logistica),
                _tarjeta_tabla_metrica(interfaz, "Rendimiento de Armadores", filas_armadores),
                _tarjeta_tabla_metrica(interfaz, "Top 10 Productos Rotados", filas_top),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
        )
        bloque_dias = _tarjeta_tabla_metrica(
            interfaz,
            "Evolución Diaria de Pedidos y Bultos",
            filas_dias,
            mensaje_vacio="Sin registros en este período",
        )

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
            ft.Container(expand=True),
            ft.Button("Exportar Excel", icon=ft.Icons.DOWNLOAD, on_click=on_exportar),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    dialogo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.INSIGHTS, color=ROJO), ft.Text("Métricas y Rendimiento del Depósito", weight=ft.FontWeight.BOLD)], spacing=8),
        content=ft.Container(
            width=900,
            height=540,
            content=ft.Column([barra_filtros, ft.Divider(height=6), contenedor_cuerpo], tight=True, spacing=8, scroll=ft.ScrollMode.AUTO),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _ev: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)


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

        desde_iso = _parsear_fecha_iso(campo_desde.value or "")
        hasta_iso = _parsear_fecha_iso(campo_hasta.value or "")
        if not desde_iso or not hasta_iso:
            contenedor_grafico.controls.append(ft.Text("Formato de fecha inválido. Use DD/MM/AAAA.", color=ft.Colors.RED_400, size=13))
            interfaz.page.update()
            return

        top_n = int(campo_top.value or "15")
        tipo = campo_tipo.value or None
        if tipo == "":
            tipo = None

        try:
            sm_cls = _resolver_stock_manager()
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
            contenedor_grafico.controls.append(
                ft.Container(
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
            )
            texto_resumen.value = "ℹ️ Sin registros en el rango seleccionado."
            interfaz.page.update()
            return

        max_cant = max(row["total_quantity"] for row in resultados)
        total_unidades = sum(row["total_quantity"] for row in resultados)
        total_productos = len(resultados)

        for i, row in enumerate(resultados):
            cod = str(row["product_code"])
            nombre = str(row["product_name"] or cod)
            cant = int(row["total_quantity"])
            proporcion = cant / max_cant if max_cant > 0 else 0
            ancho_barra = max(38, int(proporcion * 340))
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
                        ft.Text(etiqueta, size=11, color=interfaz.secundario, expand=True),
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

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Estadísticas de movimiento de stock"),
        content=ft.Column(
            [
                ft.Row([campo_desde, campo_hasta, campo_top, campo_tipo], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
                ft.Button("Actualizar gráfico", icon=ft.Icons.REFRESH, on_click=generar_grafico, bgcolor=ROJO, color=ft.Colors.WHITE),
                ft.Divider(height=1),
                texto_resumen,
                contenedor_grafico,
            ],
            tight=True,
            width=700,
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
