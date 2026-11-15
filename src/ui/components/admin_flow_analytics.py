"""Componente de analítica y flujo operativo de stock (entradas vs salidas) en tiempo real para el Administrador."""

from __future__ import annotations

from typing import Any
import flet as ft

from ..theme import ROJO


def _tarjeta_kpi_flujo(
    interfaz: Any,
    titulo: str,
    control_valor: ft.Text,
    control_subtitulo: ft.Text,
    icono: ft.IconData,
    color_ico: str,
) -> ft.Container:
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    bg_ico = ft.Colors.with_opacity(0.15, color_ico) if es_oscuro else ft.Colors.with_opacity(0.10, color_ico)

    return ft.Container(
        expand=True,
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=ft.Row(
            [
                ft.Container(
                    width=38,
                    height=38,
                    border_radius=10,
                    bgcolor=bg_ico,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(icono, color=color_ico, size=20),
                ),
                ft.Column(
                    [
                        ft.Text(titulo, size=10, weight=ft.FontWeight.W_500, color=interfaz.secundario),
                        control_valor,
                        control_subtitulo,
                    ],
                    spacing=1,
                    tight=True,
                    expand=True,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


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

    # Tarjeta Izquierda: Distribución por Canal, Tendencia Semanal y Entradas
    tarjeta_distribucion = ft.Container(
        expand=not es_movil,
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=12,
        padding=14,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PIE_CHART, size=15, color=ROJO),
                        ft.Text("Mix de Salidas por Canal", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                col_salidas_grafico,
                ft.Divider(height=10, color=ft.Colors.with_opacity(0.1, interfaz.texto)),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TRENDING_UP, size=15, color=ft.Colors.CYAN_400),
                        ft.Text("Evolución de Pedidos (Últimos 7 Días)", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                col_tendencia_dias,
                ft.Divider(height=10, color=ft.Colors.with_opacity(0.1, interfaz.texto)),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.INPUT, size=15, color=ft.Colors.GREEN_500),
                        ft.Text("Distribución de Entradas por Origen", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                col_entradas_grafico,
            ],
            spacing=8,
            tight=True,
        ),
    )

    # Tarjeta Derecha: Top 5 Salidas, Productividad de Armadores y Radar Crítico
    tarjeta_top_movimientos = ft.Container(
        expand=not es_movil,
        bgcolor=interfaz.superficie,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=12,
        padding=14,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT, size=15, color=ft.Colors.AMBER_400),
                        ft.Text("Top 5 Productos con Mayor Rotación", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                col_top_salidas,
                ft.Divider(height=10, color=ft.Colors.with_opacity(0.1, interfaz.texto)),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PEOPLE_ALT, size=15, color=ft.Colors.BLUE_400),
                        ft.Text("Productividad de Armadores en Vivo", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                col_armadores,
                ft.Divider(height=10, color=ft.Colors.with_opacity(0.1, interfaz.texto)),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=15, color=ft.Colors.RED_400),
                        ft.Text("Radar de Reposición (Stock Crítico)", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                col_stock_critico,
            ],
            spacing=8,
            tight=True,
        ),
    )

    if es_movil:
        bloque_graficos = ft.Column([tarjeta_distribucion, tarjeta_top_movimientos], spacing=10)
    else:
        bloque_graficos = ft.Row([tarjeta_distribucion, tarjeta_top_movimientos], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)

    # Encabezado de la sección
    cabecera_seccion = ft.Row(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.ANALYTICS, color=ROJO, size=18),
                    ft.Text("Flujo Operativo y Estadísticas de Stock (Tiempo Real)", size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ],
                spacing=6,
            ),
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.SYNC, size=12, color=ft.Colors.GREEN_400),
                        ft.Text("Actualizado en vivo", size=10, color=ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_800, weight=ft.FontWeight.W_500),
                    ],
                    spacing=4,
                    tight=True,
                ),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_400),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

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
            with product_store._connect() as pconn:
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
    col_sal = ctrls["col_salidas_grafico"]
    col_sal.controls.clear()

    salidas_canales = datos.get("salidas_canales", {})
    colores_canales = {
        "mercado_libre": ft.Colors.AMBER_400,
        "mercado_full": ft.Colors.CYAN_400,
        "mayoristas": ft.Colors.BLUE_400,
        "canjes": ft.Colors.PURPLE_400,
    }

    tiene_salidas = sal_tot > 0
    if not tiene_salidas:
        col_sal.controls.append(ft.Text("Sin salidas registradas en la jornada.", size=11, color=interfaz.secundario))
    else:
        for clave, item in salidas_canales.items():
            u = item["unidades"]
            porc = item["porcentaje"]
            ratio = item["ratio"]
            color_c = colores_canales.get(clave, ft.Colors.GREY_400)

            col_sal.controls.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Row(
                                    [
                                        ft.Container(width=8, height=8, border_radius=2, bgcolor=color_c),
                                        ft.Text(item["etiqueta"], size=11, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                    ],
                                    spacing=4,
                                ),
                                ft.Text(f"{u} un. ({porc}%)", size=10, weight=ft.FontWeight.BOLD, color=color_c),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.ProgressBar(
                            value=ratio,
                            color=color_c,
                            bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_200,
                            height=4,
                            border_radius=2,
                        ),
                    ],
                    spacing=2,
                    tight=True,
                )
            )

    # 2.b Evolución de Pedidos (Últimos 7 Días)
    metricas_dash = None
    if hasattr(order_store, "obtener_metricas_dashboard"):
        try:
            metricas_dash = order_store.obtener_metricas_dashboard()
        except Exception:
            metricas_dash = None

    col_dias = ctrls.get("col_tendencia_dias")
    if col_dias is not None:
        col_dias.controls.clear()
        por_dia = metricas_dash.get("pedidos_por_dia", []) if metricas_dash else []
        if not por_dia:
            col_dias.controls.append(ft.Text("Sin despachos en los últimos 7 días.", size=11, color=interfaz.secundario))
        else:
            max_ped = max((c for _, c, _ in por_dia[:7]), default=1) or 1
            for dia_str, cant_p, bultos_p in por_dia[:7]:
                ancho = max(12, int((cant_p / max_ped) * 140))
                dia_fmt = dia_str
                try:
                    partes = dia_str.split("-")
                    if len(partes) == 3:
                        dia_fmt = f"{partes[2]}/{partes[1]}"
                except Exception:
                    pass
                col_dias.controls.append(
                    ft.Row(
                        [
                            ft.Text(dia_fmt, size=11, width=42, color=interfaz.secundario, weight=ft.FontWeight.W_500),
                            ft.Container(width=ancho, height=12, bgcolor=ft.Colors.CYAN_500, border_radius=3),
                            ft.Text(f"{cant_p} ped. ({bultos_p} bultos)", size=10, color=interfaz.texto, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

    # 3. Gráfico de Barras: Entradas por Origen
    col_ent = ctrls["col_entradas_grafico"]
    col_ent.controls.clear()

    tiene_entradas = ent_tot > 0
    if not tiene_entradas:
        col_ent.controls.append(ft.Text("Sin ingresos registrados en la jornada.", size=11, color=interfaz.secundario))
    else:
        entradas_origen = datos.get("entradas_origen", {})
        for clave, item in entradas_origen.items():
            u = item["unidades"]
            porc = item["porcentaje"]
            ratio = item["ratio"]
            color_e = ft.Colors.GREEN_400

            col_ent.controls.append(
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Row(
                                    [
                                        ft.Container(width=8, height=8, border_radius=2, bgcolor=color_e),
                                        ft.Text(item["etiqueta"], size=11, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                    ],
                                    spacing=4,
                                ),
                                ft.Text(f"{u} un. ({porc}%)", size=10, weight=ft.FontWeight.BOLD, color=color_e),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.ProgressBar(
                            value=ratio,
                            color=color_e,
                            bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_200,
                            height=4,
                            border_radius=2,
                        ),
                    ],
                    spacing=2,
                    tight=True,
                )
            )

    # 4. Top 5 Salidas
    col_top_sal = ctrls["col_top_salidas"]
    col_top_sal.controls.clear()
    top_sal = datos.get("top_salidas", [])
    if not top_sal:
        col_top_sal.controls.append(ft.Text("Sin movimientos de salida.", size=11, color=interfaz.secundario))
    else:
        for idx, it in enumerate(top_sal, start=1):
            col_top_sal.controls.append(
                ft.Row(
                    [
                        ft.Text(f"{idx}.", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400, width=16),
                        ft.Text(f"[{it['codigo']}]", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto, width=65),
                        ft.Text(it["descripcion"], size=11, color=interfaz.secundario, expand=True, no_wrap=True),
                        ft.Text(f"{it['cantidad']} un.", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )

    # 4.b Productividad de Armadores en Vivo
    col_arm = ctrls.get("col_armadores")
    if col_arm is not None:
        col_arm.controls.clear()
        armadores = metricas_dash.get("rendimiento_armadores", []) if metricas_dash else []
        if not armadores:
            col_arm.controls.append(ft.Text("Sin armados registrados en la jornada.", size=11, color=interfaz.secundario))
        else:
            max_arm = max((c for _, c, _ in armadores[:4]), default=1) or 1
            for armador, cant_a, bultos_a in armadores[:4]:
                ratio_a = min(1.0, cant_a / max_arm)
                col_arm.controls.append(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.PERSON_OUTLINE, size=13, color=ft.Colors.BLUE_400),
                                            ft.Text(armador or "Sin asignar", size=11, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                        ],
                                        spacing=4,
                                    ),
                                    ft.Text(f"{cant_a} ped. ({bultos_a} bultos)", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.ProgressBar(
                                value=ratio_a,
                                color=ft.Colors.BLUE_400,
                                bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_200,
                                height=3,
                                border_radius=2,
                            ),
                        ],
                        spacing=2,
                        tight=True,
                    )
                )

    # 4.c Radar de Reposición (Stock Crítico)
    col_crit = ctrls.get("col_stock_critico")
    if col_crit is not None:
        col_crit.controls.clear()
        criticos = []
        product_store = getattr(interfaz, "product_store", None)
        if product_store is not None:
            try:
                if hasattr(product_store, "get_replenishment_analysis"):
                    res = product_store.get_replenishment_analysis(only_critical=True)
                    if isinstance(res, (list, tuple)):
                        criticos = res
            except Exception:
                criticos = []

        for r in criticos[:4]:
            try:
                if isinstance(r, dict) or hasattr(r, "keys"):
                    codigo = str(r["code"])
                    nombre = str(r["name"])
                    stk = int(r["stock"])
                    estado = str(r["estado_inventario"])
                    sug = int(r["cantidad_sugerida_pedir"] or 0)
                else:
                    codigo = str(r[0])
                    nombre = str(r[1])
                    stk = int(r[2])
                    estado = str(r[5])
                    sug = int(r[6] or 0)
            except Exception:
                continue

            es_agotado = estado == "AGOTADO"
            col_badge = ft.Colors.RED_400 if es_agotado else ft.Colors.AMBER_400
            txt_badge = "AGOTADO" if es_agotado else "QUIEBRE"

            col_crit.controls.append(
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(txt_badge, size=9, weight=ft.FontWeight.BOLD, color=col_badge),
                            bgcolor=ft.Colors.with_opacity(0.15, col_badge),
                            padding=ft.Padding.symmetric(horizontal=4, vertical=2),
                            border_radius=4,
                        ),
                        ft.Text(f"[{codigo}]", size=10, weight=ft.FontWeight.BOLD, color=interfaz.texto, width=50),
                        ft.Text(nombre, size=11, color=interfaz.secundario, expand=True, no_wrap=True),
                        ft.Text(f"Stock: {stk} (Pedir: +{sug})", size=10, weight=ft.FontWeight.BOLD, color=col_badge),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        if not col_crit.controls:
            col_crit.controls.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=13, color=ft.Colors.GREEN_400),
                        ft.Text("Todos los productos en niveles óptimos.", size=11, color=ft.Colors.GREEN_400),
                    ],
                    spacing=6,
                )
            )

    # 5. Top 5 Entradas
    col_top_ent = ctrls["col_top_entradas"]
    col_top_ent.controls.clear()
    top_ent = datos.get("top_entradas", [])
    if not top_ent:
        col_top_ent.controls.append(ft.Text("Sin movimientos de entrada.", size=11, color=interfaz.secundario))
    else:
        for idx, it in enumerate(top_ent, start=1):
            col_top_ent.controls.append(
                ft.Row(
                    [
                        ft.Text(f"{idx}.", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400, width=16),
                        ft.Text(f"[{it['codigo']}]", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto, width=65),
                        ft.Text(it["descripcion"], size=11, color=interfaz.secundario, expand=True, no_wrap=True),
                        ft.Text(f"{it['cantidad']} un.", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
            )
