"""Diálogo modal interactivo para el Mapa de Calor de Depósito, Matriz ABC y Optimización de Slotting."""

from typing import Any, List, Optional
import flet as ft

from ...warehouse_slotting import (
    DEFAULT_RACKS,
    HeatmapSlot,
    ProductoRotacion,
    SlottingSuggestion,
    WarehouseMetrics,
    analizar_rotacion_abc,
    aplicar_reubicacion_slotting,
    calcular_metricas_deposito,
    generar_mapa_calor,
    generar_sugerencias_slotting,
)
from ..theme import ROJO


def mostrar_dialogo_heatmap(interfaz: Any, _e: Optional[ft.Event] = None) -> None:
    """Ventana visual interactiva para la rotación de picking y layout térmico del depósito."""
    if not interfaz.exigir_roles("administrador", "master"):
        return

    # Estado de la vista
    analisis_actual: List[ProductoRotacion] = []
    mapa_calor_actual: List[HeatmapSlot] = []
    sugerencias_actuales: List[SlottingSuggestion] = []

    # Indicadores KPI superiores
    kpi_eficiencia = ft.Text("0%", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    kpi_picks = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_400)
    kpi_clases = ft.Text("0 / 0 / 0", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)
    kpi_sugerencias = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400)

    # Contenedores para las 3 pestañas
    layout_heatmap_container = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=12)
    lista_abc_container = ft.ListView(expand=True, spacing=6, height=340)
    lista_sugerencias_container = ft.ListView(expand=True, spacing=8, height=340)

    # Filtros para pestaña ABC
    filtro_abc_categoria = ft.Dropdown(
        label="Categoría ABC",
        value="TODAS",
        options=[
            ft.dropdown.Option("TODAS", "Todas las categorías"),
            ft.dropdown.Option("A", "Clase A (Alta Rotación)"),
            ft.dropdown.Option("B", "Clase B (Rotación Media)"),
            ft.dropdown.Option("C", "Clase C (Baja / Reposición)"),
        ],
        width=200,
        dense=True,
    )
    buscador_abc = ft.TextField(
        label="Buscar SKU o nombre...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
    )

    # Detalle de celda seleccionada en Heatmap
    info_slot_seleccionado = ft.Text(
        "Haz clic en cualquier ubicación del mapa para ver los productos almacenados.",
        size=11,
        italic=True,
        color=interfaz.secundario,
    )

    def refrescar_metricas_ui(metrics: WarehouseMetrics) -> None:
        kpi_eficiencia.value = f"{metrics.eficiencia_slotting_pct}%"
        kpi_eficiencia.color = (
            ft.Colors.GREEN_400 if metrics.eficiencia_slotting_pct >= 85.0
            else (ft.Colors.AMBER_400 if metrics.eficiencia_slotting_pct >= 70.0 else ft.Colors.RED_400)
        )
        kpi_picks.value = str(metrics.total_picks)
        kpi_clases.value = f"{metrics.skus_clase_a}A · {metrics.skus_clase_b}B · {metrics.skus_clase_c}C"
        kpi_sugerencias.value = str(metrics.reubicaciones_sugeridas)

    def seleccionar_slot_heatmap(slot: HeatmapSlot) -> None:
        prods_text = ", ".join(slot.skus_alojados) if slot.skus_alojados else "Sin productos asignados"
        dorada_tag = " ⭐ (Zona Dorada - Altura Ergonómica)" if slot.es_zona_dorada else ""
        info_slot_seleccionado.value = (
            f"📍 Ubicación {slot.ubicacion}{dorada_tag} | Picks: {slot.picks_totales} | "
            f"Unidades: {slot.unidades_totales} | Productos: {prods_text}"
        )
        info_slot_seleccionado.italic = False
        dialogo.page.update()

    def construir_layout_heatmap() -> None:
        layout_heatmap_container.controls.clear()

        # Agrupar slots por Rack
        slots_por_rack: dict[str, list[HeatmapSlot]] = {r: [] for r in DEFAULT_RACKS}
        for s in mapa_calor_actual:
            if s.rack in slots_por_rack:
                slots_por_rack[s.rack].append(s)

        rack_descriptions = {
            "A": "RACK A — Cabecera de Empaque / Despacho (Zona Prime)",
            "B": "RACK B — Sector Central Frontal",
            "C": "RACK C — Sector Central Posterior",
            "D": "RACK D — Fondo de Depósito (Almacenamiento Lejano)",
        }

        for rack_id in DEFAULT_RACKS:
            rack_slots = slots_por_rack[rack_id]
            # Ordenar por nivel descendente (3 arriba, 2 al medio, 1 abajo)
            filas_niveles: dict[int, list[HeatmapSlot]] = {3: [], 2: [], 1: []}
            for s in rack_slots:
                if s.nivel in filas_niveles:
                    filas_niveles[s.nivel].append(s)

            columnas_estantes: list[ft.Control] = []
            level_names = {3: "Nivel 3 (Alto)", 2: "Nivel 2 (⭐ Dorada)", 1: "Nivel 1 (Piso)"}

            for nivel_num in (3, 2, 1):
                celdas = []
                # Etiqueta de nivel
                celdas.append(
                    ft.Container(
                        content=ft.Text(
                            level_names[nivel_num],
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=interfaz.secundario,
                        ),
                        width=110,
                        alignment=ft.Alignment(-1, 0),
                    )
                )

                # Celdas de módulos
                sorted_modulos = sorted(filas_niveles[nivel_num], key=lambda x: x.modulo)
                for slot in sorted_modulos:
                    # Capturar slot para el callback de click
                    current_slot = slot

                    # Tooltip informativo
                    tip = f"{slot.ubicacion}\nPicks: {slot.picks_totales}\nArtículos: {len(slot.skus_alojados)}"

                    cell = ft.Container(
                        tooltip=tip,
                        content=ft.Column(
                            [
                                ft.Text(
                                    f"M{slot.modulo:02d}",
                                    size=9,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE,
                                ),
                                ft.Text(
                                    f"{slot.picks_totales}p",
                                    size=10,
                                    color=ft.Colors.WHITE,
                                    weight=ft.FontWeight.W_500,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=1,
                        ),
                        bgcolor=slot.color_hex,
                        border=ft.Border.all(
                            1.5 if slot.es_zona_dorada else 1,
                            ft.Colors.AMBER_ACCENT if slot.es_zona_dorada else ft.Colors.WHITE_24,
                        ),
                        border_radius=6,
                        width=62,
                        height=44,
                        alignment=ft.Alignment(0, 0),
                        on_click=lambda _e, s=current_slot: seleccionar_slot_heatmap(s),
                        ink=True,
                    )
                    celdas.append(cell)

                columnas_estantes.append(ft.Row(celdas, spacing=6))

            card_rack = ft.Container(
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=8,
                padding=10,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.GRID_ON, size=16, color=ROJO),
                                ft.Text(rack_descriptions[rack_id], size=12, weight=ft.FontWeight.BOLD),
                            ],
                            spacing=6,
                        ),
                        ft.Container(height=4),
                        ft.Column(columnas_estantes, spacing=4),
                    ],
                    spacing=2,
                ),
            )
            layout_heatmap_container.controls.append(card_rack)

    def renderizar_lista_abc() -> None:
        lista_abc_container.controls.clear()
        query = buscador_abc.value.strip().lower() if buscador_abc.value else ""
        cat_sel = filtro_abc_categoria.value or "TODAS"

        filtrados = [
            p for p in analisis_actual
            if (cat_sel == "TODAS" or p.categoria_abc == cat_sel)
            and (not query or query in p.codigo.lower() or query in p.nombre.lower())
        ]

        if not filtrados:
            lista_abc_container.controls.append(
                ft.Container(
                    content=ft.Text("No se encontraron productos coincidentes.", italic=True, size=12, color=interfaz.secundario),
                    padding=16,
                    alignment=ft.Alignment(0, 0),
                )
            )
            return

        for prod in filtrados:
            color_badge = (
                ft.Colors.RED_400 if prod.categoria_abc == "A"
                else (ft.Colors.AMBER_400 if prod.categoria_abc == "B" else ft.Colors.BLUE_GREY_300)
            )
            bg_badge = (
                ft.Colors.RED_900 if prod.categoria_abc == "A"
                else (ft.Colors.AMBER_900 if prod.categoria_abc == "B" else ft.Colors.BLUE_GREY_900)
            )

            tag_desalineado = ft.Container()
            if prod.desalineado:
                tag_desalineado = ft.Container(
                    content=ft.Text("DESALINEADO", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.ORANGE_900,
                    padding=ft.Padding(5, 2, 5, 2),
                    border_radius=4,
                )

            item = ft.Container(
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=6,
                padding=8,
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(f"Clase {prod.categoria_abc}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=bg_badge,
                            padding=ft.Padding(6, 4, 6, 4),
                            border_radius=4,
                            width=60,
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(f"[{prod.codigo}]", weight=ft.FontWeight.BOLD, size=12),
                                        ft.Text(prod.nombre, weight=ft.FontWeight.W_500, size=12, expand=True, no_wrap=True),
                                        tag_desalineado,
                                    ],
                                    spacing=6,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(f"Picks: {prod.total_despachos}", size=11, weight=ft.FontWeight.BOLD, color=color_badge),
                                        ft.Text(f"Unidades: {prod.unidades_despachadas}", size=11, color=interfaz.secundario),
                                        ft.Text(f"Acumulado: {prod.porcentaje_acumulado}%", size=11, color=interfaz.secundario),
                                        ft.Text(f"📍 Actual: {prod.ubicacion_actual}", size=11, weight=ft.FontWeight.BOLD),
                                        ft.Text(f"➔ Sugerida: {prod.ubicacion_sugerida}", size=11, color=ft.Colors.GREEN_400),
                                    ],
                                    spacing=12,
                                ),
                            ],
                            expand=True,
                            spacing=3,
                        ),
                    ],
                    spacing=10,
                ),
            )
            lista_abc_container.controls.append(item)

    def reubicar_item(sug: SlottingSuggestion) -> None:
        exito = aplicar_reubicacion_slotting(interfaz.product_store, sug.sku, sug.ubicacion_sugerida)
        if exito:
            interfaz.notificar(
                f"✅ Producto [{sug.sku}] reubicado con éxito a {sug.ubicacion_sugerida}",
                color=ft.Colors.GREEN_600,
            )
            # Recalcular análisis completo
            cargar_datos()
        else:
            interfaz.notificar(f"Error al reubicar producto [{sug.sku}]", color=ft.Colors.RED_600)

    def renderizar_lista_sugerencias() -> None:
        lista_sugerencias_container.controls.clear()

        if not sugerencias_actuales:
            lista_sugerencias_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.VERIFIED, color=ft.Colors.GREEN_400, size=36),
                            ft.Text("¡Depósito 100% Optimizado!", weight=ft.FontWeight.BOLD, size=14),
                            ft.Text("Todos los artículos de alta rotación residen en ubicaciones estratégicas y ergonómicas.", size=12, color=interfaz.secundario),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=24,
                    alignment=ft.Alignment(0, 0),
                )
            )
            return

        for sug in sugerencias_actuales:
            current_sug = sug
            badge_color = ft.Colors.RED_400 if sug.categoria_abc == "A" else ft.Colors.BLUE_GREY_400

            card = ft.Container(
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=8,
                padding=10,
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.SWAP_HORIZ,
                            size=24,
                            color=ft.Colors.ORANGE_400 if sug.categoria_abc == "A" else ft.Colors.CYAN_400,
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(f"[{sug.sku}]", weight=ft.FontWeight.BOLD, size=12),
                                        ft.Text(sug.nombre, weight=ft.FontWeight.W_500, size=12, expand=True, no_wrap=True),
                                        ft.Container(
                                            content=ft.Text(f"Clase {sug.categoria_abc}", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            bgcolor=badge_color,
                                            padding=ft.Padding(5, 2, 5, 2),
                                            border_radius=4,
                                        ),
                                    ],
                                    spacing=6,
                                ),
                                ft.Text(sug.motivo, size=11, color=interfaz.secundario),
                                ft.Row(
                                    [
                                        ft.Text(f"📍 Actual: {sug.ubicacion_actual}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_300),
                                        ft.Icon(ft.Icons.ARROW_FORWARD, size=12, color=interfaz.secundario),
                                        ft.Text(f"🎯 Sugerida: {sug.ubicacion_sugerida}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                                        ft.Text(f"({sug.impacto})", size=10, color=interfaz.secundario),
                                    ],
                                    spacing=8,
                                ),
                            ],
                            expand=True,
                            spacing=3,
                        ),
                        ft.Button(
                            "Reubicar",
                            icon=ft.Icons.CHECK,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.GREEN_700,
                                color=ft.Colors.WHITE,
                                padding=ft.Padding(10, 6, 10, 6),
                            ),
                            on_click=lambda _e, s=current_sug: reubicar_item(s),
                        ),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            )
            lista_sugerencias_container.controls.append(card)

    def cargar_datos() -> None:
        nonlocal analisis_actual, mapa_calor_actual, sugerencias_actuales

        order_store = getattr(interfaz, "order_store", None)
        p_store = getattr(interfaz, "product_store", None)
        if p_store is None:
            try:
                from ...stock_manager import StockManager
                sm = StockManager(getattr(interfaz.menu, "ruta_excel_base", "Productos.xlsx"))
                p_store = sm.product_store
            except Exception:
                from ...product_store import ProductStore
                from ...paths import application_root
                p_store = ProductStore(application_root() / "data" / "productos.sqlite3")
        analisis_actual = analizar_rotacion_abc(p_store, order_store=order_store, dias=30)
        mapa_calor_actual = generar_mapa_calor(analisis_actual)
        sugerencias_actuales = generar_sugerencias_slotting(analisis_actual)
        metrics = calcular_metricas_deposito(analisis_actual, mapa_calor_actual)

        refrescar_metricas_ui(metrics)
        construir_layout_heatmap()
        renderizar_lista_abc()
        renderizar_lista_sugerencias()

        try:
            if hasattr(interfaz, "page") and interfaz.page:
                interfaz.page.update()
        except Exception:
            pass

    # Callbacks de búsqueda y filtros
    buscador_abc.on_change = lambda _e: (
        renderizar_lista_abc(),
        interfaz.page.update() if hasattr(interfaz, "page") and interfaz.page else None,
    )
    filtro_abc_categoria.on_change = lambda _e: (
        renderizar_lista_abc(),
        interfaz.page.update() if hasattr(interfaz, "page") and interfaz.page else None,
    )

    # Fila de tarjetas KPI
    fila_kpis = ft.Row(
        [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Eficiencia Slotting", size=11, color=interfaz.secundario),
                        kpi_eficiencia,
                    ],
                    spacing=2,
                ),
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=8,
                padding=10,
                expand=True,
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Picks Analizados", size=11, color=interfaz.secundario),
                        kpi_picks,
                    ],
                    spacing=2,
                ),
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=8,
                padding=10,
                expand=True,
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Pareto (A / B / C)", size=11, color=interfaz.secundario),
                        kpi_clases,
                    ],
                    spacing=2,
                ),
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=8,
                padding=10,
                expand=True,
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Reubicaciones", size=11, color=interfaz.secundario),
                        kpi_sugerencias,
                    ],
                    spacing=2,
                ),
                bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                border=ft.Border.all(1, ft.Colors.WHITE_24 if interfaz.modo_oscuro else ft.Colors.GREY_300),
                border_radius=8,
                padding=10,
                expand=True,
            ),
        ],
        spacing=8,
    )

    # Leyenda térmica del Heatmap
    leyenda_termica = ft.Row(
        [
            ft.Text("Leyenda térmica:", size=11, weight=ft.FontWeight.BOLD, color=interfaz.secundario),
            ft.Container(width=12, height=12, bgcolor="#D32F2F", border_radius=2),
            ft.Text("Muy Caliente (>70%)", size=10, color=interfaz.secundario),
            ft.Container(width=12, height=12, bgcolor="#FF9800", border_radius=2),
            ft.Text("Caliente (40-70%)", size=10, color=interfaz.secundario),
            ft.Container(width=12, height=12, bgcolor="#FFC107", border_radius=2),
            ft.Text("Medio (15-40%)", size=10, color=interfaz.secundario),
            ft.Container(width=12, height=12, bgcolor="#37474F", border_radius=2),
            ft.Text("Frío (<15%)", size=10, color=interfaz.secundario),
            ft.Text("· ⭐ Zona Dorada", size=10, color=ft.Colors.AMBER_400, weight=ft.FontWeight.BOLD),
        ],
        spacing=6,
        wrap=True,
    )

    # Contenido de la pestaña 1 (Heatmap)
    tab_heatmap_content = ft.Column(
        [
            leyenda_termica,
            info_slot_seleccionado,
            ft.Container(
                content=layout_heatmap_container,
                height=320,
            ),
        ],
        spacing=8,
        expand=True,
    )

    # Contenido de la pestaña 2 (Matriz ABC)
    tab_abc_content = ft.Column(
        [
            ft.Row([buscador_abc, filtro_abc_categoria], spacing=8),
            lista_abc_container,
        ],
        spacing=8,
        expand=True,
    )

    # Contenido de la pestaña 3 (Plan de Reubicación)
    tab_sugerencias_content = ft.Column(
        [
            ft.Text(
                "Sugerencias automáticas para eliminar sobre-recorridos y fatiga física de operarios:",
                size=11,
                color=interfaz.secundario,
            ),
            lista_sugerencias_container,
        ],
        spacing=8,
        expand=True,
    )

    # Pestañas principales
    tabs = ft.Tabs(
        length=3,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Mapa Térmico (Layout)", icon=ft.Icons.GRID_VIEW_ROUNDED),
                        ft.Tab(label="Matriz Rotación ABC", icon=ft.Icons.ANALYTICS_OUTLINED),
                        ft.Tab(label="Plan de Reubicación", icon=ft.Icons.ALT_ROUTE_ROUNDED),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        tab_heatmap_content,
                        tab_abc_content,
                        tab_sugerencias_content,
                    ],
                ),
            ],
        ),
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WAREHOUSE_ROUNDED, color=ROJO, size=24),
                ft.Column(
                    [
                        ft.Text("Mapa de Calor y Rotación de Picking (Slotting)", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            "Análisis ABC de Pareto, flujo térmico de estanterías y ergonomía de depósito",
                            size=11,
                            color=interfaz.secundario,
                        ),
                    ],
                    spacing=1,
                ),
            ],
            spacing=8,
        ),
        content=ft.Container(
            content=ft.Column(
                [
                    fila_kpis,
                    ft.Divider(height=1, color=interfaz.borde),
                    tabs,
                ],
                spacing=10,
                expand=True,
            ),
            width=760,
            height=490,
        ),
        actions=[
            ft.TextButton("Actualizar Análisis", icon=ft.Icons.REFRESH, on_click=lambda _e: cargar_datos()),
            ft.Button("Cerrar", on_click=lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
    cargar_datos()
