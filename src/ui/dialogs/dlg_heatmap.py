"""Diálogo modal interactivo para el Mapa de Calor de Depósito, Matriz ABC y Optimización de Slotting."""

from __future__ import annotations

from typing import Any, List, Optional

import flet as ft

from ...warehouse_slotting import (
    HeatmapSlot,
    ProductoRotacion,
    SlottingSuggestion,
    SugerenciaReposicionPicking,
    WarehouseMetrics,
    analizar_rotacion_abc,
    aplicar_reubicacion_slotting,
    calcular_metricas_deposito,
    generar_mapa_calor,
    generar_sugerencias_reposicion_picking,
    generar_sugerencias_slotting,
)
from ..design import grilla_tarjetas_responsiva, par_accion_tarjeta
from ..theme import ROJO
from .heatmap_fefo_render import renderizar_panel_reposicion_y_fefo
from .heatmap_render import (
    kpi_heatmap_card,
    leyenda_termica_heatmap,
    renderizar_layout_heatmap,
    renderizar_lista_abc,
    renderizar_lista_sugerencias,
)


def mostrar_dialogo_heatmap(interfaz: Any, _e: Optional[ft.Event] = None) -> None:
    """Ventana visual interactiva para la rotación de picking y layout térmico del depósito."""
    if not interfaz.exigir_roles("administrador", "master"):
        return

    analisis_actual: List[ProductoRotacion] = []
    mapa_calor_actual: List[HeatmapSlot] = []
    sugerencias_actuales: List[SlottingSuggestion] = []
    reposicion_actual: List[SugerenciaReposicionPicking] = []
    alertas_fefo_actuales: list[dict[str, Any]] = []
    p_store_activo: Any = getattr(interfaz, "product_store", None)

    kpi_eficiencia = ft.Text("0%", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    kpi_picks = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_400)
    kpi_clases = ft.Text("0 / 0 / 0", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)
    kpi_sugerencias = ft.Text("0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400)

    layout_heatmap_container = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True, spacing=12)
    lista_abc_container = ft.ListView(expand=True, spacing=6, height=340)
    lista_sugerencias_container = ft.ListView(expand=True, spacing=8, height=340)
    reposicion_fefo_container = ft.ListView(expand=True, spacing=8, height=310)

    filtro_fefo_nivel = ft.Dropdown(
        label="Alerta FEFO",
        value="TODOS",
        options=[
            ft.dropdown.Option("TODOS", "Todas las alertas"),
            ft.dropdown.Option("VENCIDO", "Solo vencidos"),
            ft.dropdown.Option("CRITICO", "Críticos (<= 7 días)"),
            ft.dropdown.Option("PROXIMO", "Próximos (<= 30 días)"),
        ],
        width=210,
        dense=True,
    )

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
    buscador_abc = ft.TextField(label="Buscar SKU o nombre...", prefix_icon=ft.Icons.SEARCH, dense=True, expand=True)
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

    def _refrescar_abc(_e=None) -> None:
        renderizar_lista_abc(
            interfaz,
            lista_abc_container,
            analisis_actual,
            buscador_abc.value or "",
            filtro_abc_categoria.value or "TODAS",
        )
        if hasattr(interfaz, "page") and interfaz.page:
            interfaz.page.update()

    def _refrescar_fefo(_e=None) -> None:
        renderizar_panel_reposicion_y_fefo(
            interfaz,
            reposicion_fefo_container,
            reposicion_actual,
            alertas_fefo_actuales,
            filtro_fefo_nivel.value or "TODOS",
            ejecutar_traslado_reposicion,
        )
        if hasattr(interfaz, "page") and interfaz.page:
            interfaz.page.update()

    def _resolver_product_store() -> Any:
        p_store = getattr(interfaz, "product_store", None)
        if p_store is None:
            try:
                from ...inventory import StockManager
                p_store = StockManager(getattr(interfaz.menu, "ruta_excel_base", "Productos.xlsx")).product_store
            except Exception:
                from ...paths import application_root
                from ...products import ProductStore
                p_store = ProductStore(application_root() / "data" / "productos.sqlite3")
        return p_store

    def reubicar_item(sug: SlottingSuggestion) -> None:
        nonlocal p_store_activo
        if p_store_activo is None:
            p_store_activo = _resolver_product_store()
        if p_store_activo is not None and aplicar_reubicacion_slotting(p_store_activo, sug.sku, sug.ubicacion_sugerida):
            interfaz.notificar(f"✅ Producto [{sug.sku}] reubicado con éxito a {sug.ubicacion_sugerida}", color=ft.Colors.GREEN_600)
            cargar_datos()
        else:
            interfaz.notificar(f"Error al reubicar producto [{sug.sku}]", color=ft.Colors.RED_600)

    def ejecutar_traslado_reposicion(sug: SugerenciaReposicionPicking) -> None:
        nonlocal p_store_activo
        if p_store_activo is None:
            p_store_activo = _resolver_product_store()
        if p_store_activo is None or not hasattr(p_store_activo, "transferir_entre_ubicaciones"):
            interfaz.notificar("ProductStore no soporta transferencias multi-ubicación.", color=ft.Colors.RED_600)
            return
        try:
            res = p_store_activo.transferir_entre_ubicaciones(
                sug.product_code,
                sug.ubicacion_origen,
                sug.ubicacion_destino,
                sug.cantidad_sugerida,
            )
            interfaz.notificar(
                f"✅ Trasladadas {res['cantidad']} u. de [{sug.product_code}] ({sug.ubicacion_origen} -> {sug.ubicacion_destino})",
                color=ft.Colors.GREEN_600,
            )
            cargar_datos()
        except Exception as exc:
            interfaz.notificar(f"Error al trasladar [{sug.product_code}]: {exc}", color=ft.Colors.RED_600)

    def cargar_datos() -> None:
        nonlocal analisis_actual, mapa_calor_actual, sugerencias_actuales, reposicion_actual, alertas_fefo_actuales, p_store_activo

        order_store = getattr(interfaz, "order_store", None)
        p_store = _resolver_product_store()
        p_store_activo = p_store

        analisis_actual = analizar_rotacion_abc(p_store, order_store=order_store, dias=30)
        mapa_calor_actual = generar_mapa_calor(analisis_actual)
        sugerencias_actuales = generar_sugerencias_slotting(analisis_actual)
        metrics = calcular_metricas_deposito(analisis_actual, mapa_calor_actual)

        reposicion_actual = generar_sugerencias_reposicion_picking(p_store, dias_alerta_vencimiento=30)
        alertas_fefo_actuales = []
        if p_store is not None and hasattr(p_store, "listar_lotes_proximos_vencer"):
            try:
                cand_alertas = p_store.listar_lotes_proximos_vencer(dias=30, incluir_vencidos=True)
                if isinstance(cand_alertas, list):
                    alertas_fefo_actuales = cand_alertas
            except Exception:
                alertas_fefo_actuales = []

        refrescar_metricas_ui(metrics)
        renderizar_layout_heatmap(interfaz, layout_heatmap_container, mapa_calor_actual, seleccionar_slot_heatmap)
        renderizar_lista_abc(interfaz, lista_abc_container, analisis_actual, buscador_abc.value or "", filtro_abc_categoria.value or "TODAS")
        renderizar_lista_sugerencias(interfaz, lista_sugerencias_container, sugerencias_actuales, reubicar_item)
        renderizar_panel_reposicion_y_fefo(
            interfaz,
            reposicion_fefo_container,
            reposicion_actual,
            alertas_fefo_actuales,
            filtro_fefo_nivel.value or "TODOS",
            ejecutar_traslado_reposicion,
        )

        try:
            if hasattr(interfaz, "page") and interfaz.page:
                interfaz.page.update()
        except Exception:
            pass

    buscador_abc.on_change = _refrescar_abc
    filtro_abc_categoria.on_select = filtro_abc_categoria.on_change = _refrescar_abc
    filtro_fefo_nivel.on_select = filtro_fefo_nivel.on_change = _refrescar_fefo

    fila_kpis = grilla_tarjetas_responsiva(
        [
            kpi_heatmap_card(interfaz, "Eficiencia Slotting", kpi_eficiencia),
            kpi_heatmap_card(interfaz, "Picks Analizados", kpi_picks),
            kpi_heatmap_card(interfaz, "Pareto (A / B / C)", kpi_clases),
            kpi_heatmap_card(interfaz, "Reubicaciones", kpi_sugerencias),
        ],
        interfaz=interfaz,
        compacto=True,
        spacing=8,
        run_spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    filtro_abc_row = par_accion_tarjeta(interfaz, buscador_abc, filtro_abc_categoria, umbral=560.0, spacing=8)
    tabs = ft.Tabs(
        length=4,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Mapa Térmico (Layout)", icon=ft.Icons.GRID_VIEW_ROUNDED),
                        ft.Tab(label="Matriz Rotación ABC", icon=ft.Icons.ANALYTICS_OUTLINED),
                        ft.Tab(label="Plan de Reubicación", icon=ft.Icons.ALT_ROUTE_ROUNDED),
                        ft.Tab(label="Reposición y FEFO", icon=ft.Icons.INVENTORY_2_OUTLINED),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Column([leyenda_termica_heatmap(interfaz), info_slot_seleccionado, ft.Container(content=layout_heatmap_container, height=320)], spacing=8, expand=True),
                        ft.Column([filtro_abc_row, lista_abc_container], spacing=8, expand=True),
                        ft.Column([ft.Text("Sugerencias automáticas para eliminar sobre-recorridos y fatiga física de operarios:", size=11, color=interfaz.secundario), lista_sugerencias_container], spacing=8, expand=True),
                        ft.Column([ft.Row([ft.Text("Reposición entre zonas y control de vencimientos FEFO:", size=11, color=interfaz.secundario, expand=True), filtro_fefo_nivel], spacing=8), reposicion_fefo_container], spacing=8, expand=True),
                    ],
                ),
            ],
        ),
    )

    ancho_dlg = interfaz.ancho_adaptable(760) if hasattr(interfaz, "ancho_adaptable") else 760
    alto_dlg = interfaz.alto_adaptable(490) if hasattr(interfaz, "alto_adaptable") else 490
    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WAREHOUSE_ROUNDED, color=ROJO, size=24),
                ft.Column(
                    [
                        ft.Text("Mapa de Calor y Rotación de Picking (Slotting)", size=16, weight=ft.FontWeight.BOLD, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text("Análisis ABC de Pareto, flujo térmico de estanterías y ergonomía de depósito", size=11, color=interfaz.secundario, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ],
                    spacing=1,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
        content=ft.Container(content=ft.Column([fila_kpis, ft.Divider(height=1, color=interfaz.borde), tabs], spacing=10, expand=True), width=ancho_dlg, height=alto_dlg),
        actions=[
            ft.TextButton("Actualizar Análisis", icon=ft.Icons.REFRESH, on_click=lambda _e: cargar_datos()),
            ft.Button("Cerrar", on_click=lambda _e: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    interfaz.page.show_dialog(dialogo)
    cargar_datos()
