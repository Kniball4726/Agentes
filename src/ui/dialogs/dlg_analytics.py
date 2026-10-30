"""Diálogos y vistas analíticas: dashboard ejecutivo, auditoría, estadísticas y notificaciones."""

from datetime import datetime, timedelta
from typing import Any

import flet as ft
import openpyxl

from ..theme import ROJO
import sys
from ...stock_manager import StockManager as _DefaultStockManager

def _get_stock_manager():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager



def mostrar_dashboard_metricas(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Dashboard de métricas, rendimiento de operarios y distribución logística."""
    if not interfaz.exigir_roles("administrador"):
        return

    hoy_dt = datetime.now()
    hace_30_dt = hoy_dt - timedelta(days=30)

    input_desde = ft.TextField(
        label="Desde (DD/MM/AAAA)",
        value=hace_30_dt.strftime("%d/%m/%Y"),
        width=155,
        dense=True,
    )
    input_hasta = ft.TextField(
        label="Hasta (DD/MM/AAAA)",
        value=hoy_dt.strftime("%d/%m/%Y"),
        width=155,
        dense=True,
    )
    contenedor_cuerpo = ft.Column(spacing=10, tight=True)
    metricas_actuales: list[dict] = [{}]

    def _parse_f(txt: str) -> str | None:
        t = (txt or "").strip()
        if not t:
            return None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(t, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def tarjeta_kpi(titulo: str, valor: str, icono: str, color_ico: str) -> ft.Container:
        return ft.Container(
            bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.WHITE,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=10,
            expand=True,
            content=ft.Column(
                [
                    ft.Row([ft.Icon(icono, color=color_ico, size=18), ft.Text(titulo, size=11, color=interfaz.secundario, weight=ft.FontWeight.W_500)], spacing=6),
                    ft.Text(valor, size=18, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                spacing=3,
            ),
        )

    def render_dashboard(usar_rango: bool = False) -> None:
        f_d = _parse_f(input_desde.value or "") if usar_rango else None
        f_h = _parse_f(input_hasta.value or "") if usar_rango else None
        m = interfaz.order_store.obtener_metricas_dashboard(fecha_desde=f_d, fecha_hasta=f_h)
        metricas_actuales[0] = m
        promedio_bultos = (m["total_bultos"] / m["total_pedidos"]) if m["total_pedidos"] > 0 else 0
        est_desp = m.get("estados_despacho", {})

        kpis = ft.Row(
            [
                tarjeta_kpi("Total Pedidos", str(m["total_pedidos"]), ft.Icons.INVENTORY, ft.Colors.BLUE_500),
                tarjeta_kpi("Total Bultos", str(m["total_bultos"]), ft.Icons.LOCAL_SHIPPING, ft.Colors.AMBER_600),
                tarjeta_kpi("Prom. Bultos", f"{promedio_bultos:.1f}", ft.Icons.CALCULATE, ft.Colors.TEAL_500),
                tarjeta_kpi("📦 Armados", str(est_desp.get("armado", 0)), ft.Icons.INVENTORY_2, ft.Colors.BLUE_400),
                tarjeta_kpi("🚚 Despachados", str(est_desp.get("despachado", 0)), ft.Icons.LOCAL_SHIPPING, ft.Colors.AMBER_500),
                tarjeta_kpi("✔ Entregados", str(est_desp.get("entregado", 0)), ft.Icons.VERIFIED, ft.Colors.GREEN_500),
            ],
            spacing=8,
        )

        filas_logistica = ft.Column(spacing=4)
        for log, cant, bultos in m["distribucion_logistica"]:
            porc = (cant / m["total_pedidos"] * 100) if m["total_pedidos"] > 0 else 0
            filas_logistica.controls.append(
                ft.Row(
                    [
                        ft.Text(log, size=12, weight=ft.FontWeight.W_500, expand=True, color=interfaz.texto),
                        ft.Text(f"{cant} ped. ({porc:.0f}%)", size=11, color=interfaz.secundario),
                        ft.Text(f"{bultos} bultos", size=11, weight=ft.FontWeight.BOLD, color=ROJO),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )

        filas_armadores = ft.Column(spacing=4)
        for arm, cant, bultos in m["rendimiento_armadores"]:
            filas_armadores.controls.append(
                ft.Row(
                    [
                        ft.Text(arm, size=12, weight=ft.FontWeight.W_500, expand=True, color=interfaz.texto),
                        ft.Text(f"{cant} ped.", size=11, color=interfaz.secundario),
                        ft.Text(f"{bultos} bultos", size=11, weight=ft.FontWeight.BOLD, color=ROJO),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
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
                ft.Container(
                    bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.WHITE,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=10,
                    expand=True,
                    content=ft.Column(
                        [
                            ft.Text("Despacho por Logística", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                            ft.Divider(height=4),
                            filas_logistica if filas_logistica.controls else ft.Text("Sin datos", size=11, color=interfaz.secundario),
                        ],
                        spacing=4,
                    ),
                ),
                ft.Container(
                    bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.WHITE,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=10,
                    expand=True,
                    content=ft.Column(
                        [
                            ft.Text("Rendimiento de Armadores", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                            ft.Divider(height=4),
                            filas_armadores if filas_armadores.controls else ft.Text("Sin datos", size=11, color=interfaz.secundario),
                        ],
                        spacing=4,
                    ),
                ),
                ft.Container(
                    bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.WHITE,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=10,
                    expand=True,
                    content=ft.Column(
                        [
                            ft.Text("Top 10 Productos Rotados", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                            ft.Divider(height=4),
                            filas_top if filas_top.controls else ft.Text("Sin datos", size=11, color=interfaz.secundario),
                        ],
                        spacing=4,
                    ),
                ),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
        )

        bloque_dias = ft.Container(
            bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.WHITE,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=10,
            content=ft.Column(
                [
                    ft.Text("Evolución Diaria de Pedidos y Bultos", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ft.Divider(height=4),
                    filas_dias if filas_dias.controls else ft.Text("Sin registros en este período", size=11, color=interfaz.secundario),
                ],
                spacing=4,
            ),
        )

        contenedor_cuerpo.controls.clear()
        contenedor_cuerpo.controls.extend([kpis, seccion_tablas, bloque_dias])
        interfaz.page.update()

    def exportar_dashboard_excel(_ev: ft.Event) -> None:
        m = metricas_actuales[0] or interfaz.order_store.obtener_metricas_dashboard()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Dashboard Depósito"
        ws.append(["REPORTE DE MÉTRICAS Y RENDIMIENTO DEL DEPÓSITO"])
        ws.append(["Fecha de generación", datetime.now().strftime("%d/%m/%Y %H:%M")])
        ws.append(["Período filtrado", f"{m.get('fecha_desde') or 'Inicio'} a {m.get('fecha_hasta') or 'Hoy'}"])
        ws.append([])
        ws.append(["INDICADOR", "VALOR"])
        ws.append(["Total Pedidos Activos", m["total_pedidos"]])
        ws.append(["Total Bultos", m["total_bultos"]])
        est = m.get("estados_despacho", {})
        ws.append(["Pedidos Armados", est.get("armado", 0)])
        ws.append(["Pedidos Despachados", est.get("despachado", 0)])
        ws.append(["Pedidos Entregados", est.get("entregado", 0)])
        ws.append(["Cierres de Jornada", m["total_cierres"]])
        ws.append([])
        ws.append(["LOGÍSTICA", "PEDIDOS", "BULTOS"])
        for log, cant, bultos in m["distribucion_logistica"]:
            ws.append([log, cant, bultos])
        ws.append([])
        ws.append(["ARMADOR", "PEDIDOS", "BULTOS"])
        for arm, cant, bultos in m["rendimiento_armadores"]:
            ws.append([arm, cant, bultos])
        ws.append([])
        ws.append(["CÓDIGO", "PRODUCTO", "UNIDADES ROTADAS"])
        for cod, desc, cant in m["top_articulos"]:
            ws.append([cod, desc, cant])

        carpeta_out = interfaz.menu.carpeta_descuentos
        carpeta_out.mkdir(parents=True, exist_ok=True)
        ruta_out = carpeta_out / f"Dashboard_Metricas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(ruta_out)
        wb.close()
        interfaz.actualizar_estado()
        interfaz.abrir_informe(ruta_especifica=ruta_out)

    render_dashboard(usar_rango=False)

    barra_filtros = ft.Row(
        [
            input_desde,
            input_hasta,
            ft.Button(
                "Filtrar rango",
                icon=ft.Icons.FILTER_ALT,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=lambda _ev: render_dashboard(usar_rango=True),
            ),
            ft.TextButton(
                "Ver histórico completo",
                icon=ft.Icons.ALL_INCLUSIVE,
                on_click=lambda _ev: render_dashboard(usar_rango=False),
            ),
            ft.Container(expand=True),
            ft.Button(
                "Exportar Excel",
                icon=ft.Icons.DOWNLOAD,
                on_click=exportar_dashboard_excel,
            ),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.INSIGHTS, color=ROJO),
                ft.Text("Métricas y Rendimiento del Depósito", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=900,
            height=540,
            content=ft.Column(
                [
                    barra_filtros,
                    ft.Divider(height=6),
                    contenedor_cuerpo,
                ],
                tight=True,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _ev: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_registro_auditoria(interfaz: Any, _e: ft.Event | None = None) -> None:
    """Ventana del historial de auditoría y trazabilidad del sistema."""
    if not interfaz.exigir_roles("master"):
        return

    lista_eventos = ft.ListView(expand=True, spacing=6, height=380)
    input_busqueda = ft.TextField(
        hint_text="Filtrar eventos por usuario, acción o detalle...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
    )

    def color_accion(accion: str) -> tuple[str, str]:
        if "CARGA" in accion or "CREAR" in accion:
            return (ft.Colors.BLUE_100 if not interfaz.modo_oscuro else ft.Colors.BLUE_900, ft.Colors.BLUE_800 if not interfaz.modo_oscuro else ft.Colors.BLUE_200)
        if "ANULAR" in accion or "ALERTA" in accion:
            return (ft.Colors.RED_100 if not interfaz.modo_oscuro else ft.Colors.RED_900, ft.Colors.RED_800 if not interfaz.modo_oscuro else ft.Colors.RED_200)
        if "CIERRE" in accion:
            return (ft.Colors.GREEN_100 if not interfaz.modo_oscuro else ft.Colors.GREEN_900, ft.Colors.GREEN_800 if not interfaz.modo_oscuro else ft.Colors.GREEN_200)
        if "BACKUP" in accion:
            return (ft.Colors.PURPLE_100 if not interfaz.modo_oscuro else ft.Colors.PURPLE_900, ft.Colors.PURPLE_800 if not interfaz.modo_oscuro else ft.Colors.PURPLE_200)
        return (ft.Colors.GREY_200 if not interfaz.modo_oscuro else ft.Colors.GREY_800, interfaz.texto)

    def refrescar_lista(_ev: ft.Event | None = None) -> None:
        lista_eventos.controls.clear()
        txt = (input_busqueda.value or "").strip()
        logs = interfaz.order_store.listar_auditoria(limit=200, filtro_texto=txt)
        if not logs:
            lista_eventos.controls.append(ft.Text("No se encontraron registros de auditoría.", size=12, color=interfaz.secundario))
        else:
            for reg in logs:
                bg_col, txt_col = color_accion(reg.accion)
                badge = ft.Container(
                    content=ft.Text(reg.accion, size=9, weight=ft.FontWeight.BOLD, color=txt_col),
                    bgcolor=bg_col,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                )
                lista_eventos.controls.append(
                    ft.Container(
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
                        border=ft.Border.all(1, interfaz.borde),
                        border_radius=6,
                        padding=8,
                        content=ft.Row(
                            [
                                badge,
                                ft.Text(f"[{reg.usuario}]", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                                ft.Text(reg.detalle, size=11, color=interfaz.texto, expand=True),
                                ft.Text(reg.created_at[:16], size=10, color=interfaz.secundario),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
        interfaz.page.update()

    input_busqueda.on_change = refrescar_lista
    refrescar_lista()

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.SECURITY, color=ROJO),
                ft.Text("Registro de Auditoría y Trazabilidad", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=740,
            content=ft.Column(
                [
                    input_busqueda,
                    ft.Divider(height=6),
                    lista_eventos,
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _ev: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_estadisticas(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana de gráficos y estadísticas de rotación de productos."""
    if not interfaz.exigir_roles("administrador"):
        return

    hoy = datetime.now()
    hace_30_dias = hoy - timedelta(days=30)

    campo_desde = ft.TextField(
        label="Desde (DD/MM/AAAA)",
        value=hace_30_dias.strftime("%d/%m/%Y"),
        width=160,
        text_size=13,
    )
    campo_hasta = ft.TextField(
        label="Hasta (DD/MM/AAAA)",
        value=hoy.strftime("%d/%m/%Y"),
        width=160,
        text_size=13,
    )
    campo_top = ft.Dropdown(
        label="Top productos",
        value="15",
        options=[
            ft.DropdownOption("5"),
            ft.DropdownOption("10"),
            ft.DropdownOption("15"),
            ft.DropdownOption("20"),
            ft.DropdownOption("50"),
        ],
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

    contenedor_grafico = ft.Column(
        spacing=4,
        scroll=ft.ScrollMode.AUTO,
        height=350,
    )
    texto_resumen = ft.Text("", size=12, color=interfaz.secundario)

    def parsear_fecha(texto: str) -> str | None:
        texto = texto.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def generar_grafico(_e: ft.Event | None = None) -> None:
        contenedor_grafico.controls.clear()

        desde_iso = parsear_fecha(campo_desde.value or "")
        hasta_iso = parsear_fecha(campo_hasta.value or "")
        if not desde_iso or not hasta_iso:
            contenedor_grafico.controls.append(
                ft.Text(
                    "Formato de fecha inválido. Use DD/MM/AAAA.",
                    color=ft.Colors.RED_400,
                    size=13,
                )
            )
            interfaz.page.update()
            return

        top_n = int(campo_top.value or "15")
        tipo = campo_tipo.value or None
        if tipo == "":
            tipo = None

        try:
            sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            resultados = sm.consultar_movimientos(
                fecha_desde=desde_iso,
                fecha_hasta=hasta_iso,
                tipo=tipo,
                top_n=top_n,
            )
        except Exception as err:
            contenedor_grafico.controls.append(
                ft.Text(f"Error: {err}", color=ft.Colors.RED_400, size=13)
            )
            interfaz.page.update()
            return

        if not resultados:
            contenedor_grafico.controls.append(
                ft.Text(
                    "No se encontraron movimientos en el rango seleccionado.",
                    color=interfaz.secundario,
                    size=13,
                )
            )
            texto_resumen.value = ""
            interfaz.page.update()
            return

        max_cant = max(row["total_quantity"] for row in resultados)
        total_unidades = sum(row["total_quantity"] for row in resultados)
        total_productos = len(resultados)

        colores_barra = [
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
        ]

        for i, row in enumerate(resultados):
            cod = str(row["product_code"])
            nombre = str(row["product_name"])
            cant = int(row["total_quantity"])
            proporcion = cant / max_cant if max_cant > 0 else 0
            ancho_barra = max(8, int(proporcion * 300))
            color_idx = min(i, len(colores_barra) - 1)

            etiqueta = f"{nombre[:25]}" if len(nombre) > 25 else nombre
            fila = ft.Row(
                [
                    ft.Text(cod, width=60, size=11, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        width=ancho_barra,
                        height=20,
                        bgcolor=colores_barra[color_idx],
                        border_radius=ft.BorderRadius(3, 3, 3, 3),
                        alignment=ft.Alignment(-1, 0),
                        padding=ft.Padding(4, 0, 4, 0),
                        content=ft.Text(
                            str(cant),
                            size=10,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ),
                    ft.Text(
                        etiqueta,
                        size=11,
                        color=interfaz.secundario,
                        expand=True,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            contenedor_grafico.controls.append(fila)

        tipo_texto = {
            "descuento": "descontadas",
            "ingreso_fabrica": "ingresadas (fábrica)",
        }.get(tipo or "", "movidas")
        texto_resumen.value = (
            f"📊 {total_productos} productos — {total_unidades} unidades {tipo_texto} "
            f"entre {campo_desde.value} y {campo_hasta.value}"
        )
        interfaz.page.update()

    generar_grafico()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text("Estadísticas de movimiento de stock"),
        content=ft.Column(
            [
                ft.Row(
                    [campo_desde, campo_hasta, campo_top, campo_tipo],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
                ft.Button(
                    "Actualizar gráfico",
                    icon=ft.Icons.REFRESH,
                    on_click=generar_grafico,
                    bgcolor=ROJO,
                    color=ft.Colors.WHITE,
                ),
                ft.Divider(height=1),
                texto_resumen,
                contenedor_grafico,
            ],
            tight=True,
            width=700,
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_notificaciones_admin(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para revisar notificaciones de operarios y avisos de stock."""
    if not interfaz.exigir_roles("administrador"):
        return

    sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
    lista_notificaciones = ft.ListView(
        expand=True,
        spacing=8,
        height=340,
    )

    def recargar_lista() -> None:
        lista_notificaciones.controls.clear()
        items = sm.obtener_notificaciones_admin(solo_no_leidas=False)
        if not items:
            lista_notificaciones.controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    padding=20,
                    content=ft.Text(
                        "No hay notificaciones de operarios registradas.",
                        color=interfaz.secundario,
                        size=13,
                    ),
                )
            )
        else:
            for n in items:
                nid = n["id"]
                leida = bool(n["is_read"])
                operador = n["operator_username"]
                fecha = n["created_at"]
                msg = n["message"]
                tipo_notif = n["notification_type"] if "notification_type" in n.keys() else "descuento"

                def crear_handler_marcar(notif_id: int):
                    def marcar(_e: ft.Event):
                        sm.marcar_notificaciones_leidas(notif_id)
                        recargar_lista()
                        interfaz.page.update()
                    return marcar

                badge_leida = None
                if not leida:
                    badge_leida = ft.Container(
                        content=ft.Text("NUEVA", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        bgcolor=ROJO,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    )

                etiqueta_tipo = "Inventario Físico" if tipo_notif == "stock_fisico" else "Descuento"
                fila_cabecera = [
                    ft.Icon(
                        ft.Icons.ASSIGNMENT_TURNED_IN
                        if tipo_notif == "stock_fisico"
                        else (ft.Icons.NOTIFICATIONS_ACTIVE if not leida else ft.Icons.CHECK_CIRCLE),
                        color=ft.Colors.BLUE_500
                        if (tipo_notif == "stock_fisico" and not leida)
                        else (ROJO if not leida else ft.Colors.GREEN_600),
                        size=16,
                    ),
                    ft.Text(f"[{etiqueta_tipo}] Operario: {operador}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                    ft.Text(f"· {fecha}", size=11, color=interfaz.secundario),
                ]
                if badge_leida:
                    fila_cabecera.append(badge_leida)

                card_content = [
                    ft.Row(fila_cabecera, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    ft.Text(msg, size=12, color=interfaz.texto),
                ]
                acciones_fila = []
                if tipo_notif == "stock_fisico":
                    acciones_fila.append(
                        ft.TextButton(
                            "Ver comparativa",
                            icon=ft.Icons.COMPARE_ARROWS,
                            on_click=lambda _e: (
                                interfaz.page.pop_dialog(),
                                interfaz.mostrar_comparativa_stock_fisico_admin(),
                            ),
                        )
                    )
                if not leida:
                    acciones_fila.append(
                        ft.TextButton(
                            "Marcar como leída",
                            icon=ft.Icons.CHECK,
                            on_click=crear_handler_marcar(nid),
                        )
                    )
                if acciones_fila:
                    card_content.append(
                        ft.Row(acciones_fila, alignment=ft.MainAxisAlignment.END)
                    )

                lista_notificaciones.controls.append(
                    ft.Container(
                        padding=10,
                        border_radius=8,
                        bgcolor=ft.Colors.RED_50 if (not leida and not interfaz.modo_oscuro) else (ft.Colors.WHITE_10 if not leida else ft.Colors.TRANSPARENT),
                        border=ft.Border.all(1, ft.Colors.RED_200 if (not leida and not interfaz.modo_oscuro) else interfaz.borde),
                        content=ft.Column(card_content, spacing=4),
                    )
                )
        interfaz.page.update()

    recargar_lista()

    def marcar_todas_leidas(_e: ft.Event) -> None:
        sm.marcar_notificaciones_leidas(None)
        recargar_lista()
        interfaz.page.update()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.NOTIFICATIONS, color=ROJO),
                ft.Text("Notificaciones de Descuentos de Operarios", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=550,
            content=ft.Column(
                [
                    ft.Text(
                        "Registro de descuentos de stock ejecutados por usuarios con rol de operador.",
                        size=12,
                        color=interfaz.secundario,
                    ),
                    ft.Divider(height=6),
                    lista_notificaciones,
                ],
                tight=True,
                spacing=6,
            ),
        ),
        actions=[
            ft.TextButton("Marcar todas como leídas", icon=ft.Icons.DONE_ALL, on_click=marcar_todas_leidas),
            interfaz.boton_dialogo("Cerrar", lambda _e: (interfaz.page.pop_dialog(), interfaz.actualizar_estado())),
        ],
    )
    interfaz.page.show_dialog(dialogo)
