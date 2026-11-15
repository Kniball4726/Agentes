"""Componente de analítica y flujo operativo de stock (entradas vs salidas) en tiempo real para el Administrador."""

from __future__ import annotations

from contextlib import closing
from typing import Any
import flet as ft

from .admin_flow_widgets import (
    construir_cabecera_flujo,
    construir_tarjetas_graficos_flujo,
    renderizar_barras_distribucion,
    renderizar_productividad_armadores,
    renderizar_radar_criticos,
    renderizar_tendencia_7_dias,
    renderizar_top_movimientos,
    tarjeta_kpi_flujo,
)

# Alias de compatibilidad interna
_tarjeta_kpi_flujo = tarjeta_kpi_flujo


def construir_panel_analitica_flujo_admin(interfaz: Any) -> ft.Control | None:
    """
    Construye el panel completo de estadísticas y gráficos de flujo en tiempo real
    exclusivamente para el Administrador.
    """
    usuario = getattr(interfaz, "usuario_actual", None)
    if not usuario or getattr(usuario, "role", "") != "administrador":
        return None

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))

    # Controles dinámicos de KPIs
    txt_entradas_val = ft.Text("0 un.", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    txt_entradas_sub = ft.Text("Fábrica y ajustes", size=10, color=interfaz.secundario)

    txt_salidas_val = ft.Text("0 un.", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)
    txt_salidas_sub = ft.Text("Despachos y envíos", size=10, color=interfaz.secundario)

    txt_balance_val = ft.Text("0 un.", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)
    txt_balance_sub = ft.Text("Balance del día", size=10, color=interfaz.secundario)

    txt_bultos_val = ft.Text("0 bultos", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)
    txt_bultos_sub = ft.Text("Cajas movilizadas", size=10, color=interfaz.secundario)

    txt_semaforo_val = ft.Text("0 SKUs", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_400)
    txt_semaforo_sub = ft.Text("Catálogo supervisado", size=10, color=interfaz.secundario)

    # Columnas de gráficos de distribución y tendencias
    col_salidas_grafico = ft.Column(spacing=6)
    col_tendencia_dias = ft.Column(spacing=4)
    col_entradas_grafico = ft.Column(spacing=6)

    # Listas de Top 5, Armadores y Stock Crítico
    col_top_salidas = ft.Column(spacing=4)
    col_armadores = ft.Column(spacing=4)
    col_stock_critico = ft.Column(spacing=4)
    col_top_entradas = ft.Column(spacing=4)

    # Guardar referencias en la interfaz para actualización en vivo
    interfaz.controles_flujo_admin = {
        "entradas_val": txt_entradas_val,
        "entradas_sub": txt_entradas_sub,
        "salidas_val": txt_salidas_val,
        "salidas_sub": txt_salidas_sub,
        "balance_val": txt_balance_val,
        "balance_sub": txt_balance_sub,
        "bultos_val": txt_bultos_val,
        "bultos_sub": txt_bultos_sub,
        "semaforo_val": txt_semaforo_val,
        "semaforo_sub": txt_semaforo_sub,
        "col_salidas_grafico": col_salidas_grafico,
        "col_tendencia_dias": col_tendencia_dias,
        "col_entradas_grafico": col_entradas_grafico,
        "col_top_salidas": col_top_salidas,
        "col_armadores": col_armadores,
        "col_stock_critico": col_stock_critico,
        "col_top_entradas": col_top_entradas,
    }

    # Tarjetas KPI superiores
    kpi_entradas = _tarjeta_kpi_flujo(interfaz, "ENTRADAS HOY", txt_entradas_val, txt_entradas_sub, ft.Icons.MOVE_TO_INBOX, ft.Colors.GREEN_500)
    kpi_salidas = _tarjeta_kpi_flujo(interfaz, "SALIDAS HOY", txt_salidas_val, txt_salidas_sub, ft.Icons.OUTBOX, ft.Colors.RED_500)
    kpi_balance = _tarjeta_kpi_flujo(interfaz, "BALANCE NETO", txt_balance_val, txt_balance_sub, ft.Icons.COMPARE_ARROWS, ft.Colors.AMBER_500)
    kpi_bultos = _tarjeta_kpi_flujo(interfaz, "BULTOS TOTALES", txt_bultos_val, txt_bultos_sub, ft.Icons.INVENTORY_2, ft.Colors.BLUE_500)
    kpi_semaforo = _tarjeta_kpi_flujo(interfaz, "SALUD DE STOCK", txt_semaforo_val, txt_semaforo_sub, ft.Icons.HEALTH_AND_SAFETY, ft.Colors.TEAL_400)
    kpi_semaforo.tooltip = "Click para consultar inventario y catálogo"
    kpi_semaforo.on_click = lambda _: interfaz.mostrar_ver_stock() if hasattr(interfaz, "mostrar_ver_stock") else None
    kpi_semaforo.ink = True

    if es_movil:
        for k in (kpi_entradas, kpi_salidas, kpi_balance, kpi_bultos, kpi_semaforo):
            k.expand = False
            k.col = 6
        fila_kpis = ft.ResponsiveRow([kpi_entradas, kpi_salidas, kpi_balance, kpi_bultos, kpi_semaforo], spacing=8, run_spacing=8)
    else:
        fila_kpis = ft.Row([kpi_entradas, kpi_salidas, kpi_balance, kpi_bultos, kpi_semaforo], spacing=10)

    # Tarjeta Izquierda y Derecha delegadas al módulo de widgets
    tarjeta_distribucion, tarjeta_top_movimientos = construir_tarjetas_graficos_flujo(
        interfaz, es_movil, interfaz.controles_flujo_admin
    )

    if es_movil:
        bloque_graficos = ft.Column([tarjeta_distribucion, tarjeta_top_movimientos], spacing=10)
    else:
        bloque_graficos = ft.Row([tarjeta_distribucion, tarjeta_top_movimientos], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)

    cabecera_seccion = construir_cabecera_flujo(interfaz, es_oscuro)

    panel_completo = ft.Column(
        [
            cabecera_seccion,
            fila_kpis,
            bloque_graficos,
        ],
        spacing=10,
        tight=True,
    )

    actualizar_panel_analitica_flujo_admin(interfaz)
    return panel_completo


def actualizar_panel_analitica_flujo_admin(interfaz: Any) -> None:
    """
    Recalcula las estadísticas de entradas y salidas y actualiza en tiempo real
    los gráficos de barras, KPIs y listados Top 5 del Administrador.
    """
    usuario = getattr(interfaz, "usuario_actual", None)
    if not usuario or getattr(usuario, "role", "") != "administrador":
        return

    order_store = getattr(interfaz, "order_store", None)
    if not order_store or not hasattr(order_store, "obtener_flujo_stock_diario"):
        return

    ctrls = getattr(interfaz, "controles_flujo_admin", None)
    if not ctrls:
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))

    try:
        datos = order_store.obtener_flujo_stock_diario()
        if not isinstance(datos, dict):
            return
    except Exception as err:
        print(f"[WARN] Error al obtener flujo de stock diario: {err}")
        return

    # 1. Actualizar KPIs
    ent_tot = datos.get("entradas_totales", 0)
    sal_tot = datos.get("salidas_totales", 0)
    bal_net = datos.get("balance_neto", 0)
    bul_tot = datos.get("bultos_totales", 0)

    ctrls["entradas_val"].value = f"{ent_tot} un."
    ctrls["salidas_val"].value = f"{sal_tot} un."

    signo = "+" if bal_net > 0 else ""
    ctrls["balance_val"].value = f"{signo}{bal_net} un."
    if bal_net > 0:
        ctrls["balance_val"].color = ft.Colors.GREEN_400
        ctrls["balance_sub"].value = "Superávit de stock"
    elif bal_net < 0:
        ctrls["balance_val"].color = ft.Colors.RED_400
        ctrls["balance_sub"].value = "Demanda mayor a entradas"
    else:
        ctrls["balance_val"].color = ft.Colors.AMBER_400
        ctrls["balance_sub"].value = "Stock equilibrado"

    ctrls["bultos_val"].value = f"{bul_tot} bultos"

    # 1.b Semáforo de Catálogo
    product_store = getattr(interfaz, "product_store", None)
    if "semaforo_val" in ctrls and product_store is not None:
        try:
            with closing(product_store._connect()) as pconn:
                c_row = pconn.execute("""
                    SELECT 
                        COUNT(CASE WHEN estado_inventario IN ('OPTIMO', 'SOBRESTOCK') THEN 1 END) as optimos,
                        COUNT(CASE WHEN estado_inventario = 'QUIEBRE_INMINENTE' THEN 1 END) as alertas,
                        COUNT(CASE WHEN estado_inventario = 'AGOTADO' THEN 1 END) as quiebres
                    FROM v_analisis_reposicion
                """).fetchone()
                if c_row:
                    opt, ale, quieb = int(c_row[0]), int(c_row[1]), int(c_row[2])
                    ctrls["semaforo_val"].value = f"{opt} ópt. · {quieb} quieb."
                    ctrls["semaforo_sub"].value = f"🟢 {opt}  🟡 {ale}  🔴 {quieb}"
        except Exception:
            pass

    # 2. Gráfico de Barras: Salidas por Canal
    colores_canales = {
        "mercado_libre": ft.Colors.AMBER_400,
        "mercado_full": ft.Colors.CYAN_400,
        "mayoristas": ft.Colors.BLUE_400,
        "canjes": ft.Colors.PURPLE_400,
    }
    salidas_canales = datos.get("salidas_canales", {}) if sal_tot > 0 else {}
    renderizar_barras_distribucion(
        ctrls["col_salidas_grafico"],
        interfaz,
        salidas_canales,
        "Sin salidas registradas en la jornada.",
        es_oscuro,
        colores_por_clave=colores_canales,
        color_default=ft.Colors.GREY_400,
    )

    # 2.b Evolución de Pedidos (Últimos 7 Días)
    metricas_dash = None
    if hasattr(order_store, "obtener_metricas_dashboard"):
        try:
            metricas_dash = order_store.obtener_metricas_dashboard()
        except Exception:
            metricas_dash = None

    por_dia = metricas_dash.get("pedidos_por_dia", []) if metricas_dash else []
    renderizar_tendencia_7_dias(ctrls.get("col_tendencia_dias"), interfaz, por_dia)

    # 3. Gráfico de Barras: Entradas por Origen
    entradas_origen = datos.get("entradas_origen", {}) if ent_tot > 0 else {}
    renderizar_barras_distribucion(
        ctrls["col_entradas_grafico"],
        interfaz,
        entradas_origen,
        "Sin ingresos registrados en la jornada.",
        es_oscuro,
        color_default=ft.Colors.GREEN_400,
    )

    # 4. Top 5 Salidas, Armadores y Radar Crítico
    renderizar_top_movimientos(
        ctrls["col_top_salidas"],
        interfaz,
        datos.get("top_salidas", []),
        "Sin movimientos de salida.",
        ft.Colors.RED_400,
    )
    armadores = metricas_dash.get("rendimiento_armadores", []) if metricas_dash else []
    renderizar_productividad_armadores(ctrls.get("col_armadores"), interfaz, armadores, es_oscuro)
    renderizar_radar_criticos(ctrls.get("col_stock_critico"), interfaz, product_store)

    # 5. Top 5 Entradas
    renderizar_top_movimientos(
        ctrls["col_top_entradas"],
        interfaz,
        datos.get("top_entradas", []),
        "Sin movimientos de entrada.",
        ft.Colors.GREEN_400,
    )
