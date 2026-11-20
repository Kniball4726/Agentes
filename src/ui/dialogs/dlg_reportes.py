"""Diálogo modal para el Centro Unificado de Reportes de StockAgent."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any

import flet as ft

from ...paths import application_root
from ...stock.reportes_service import (
    generar_reporte_auditoria_inventario_fisico,
    generar_reporte_catalogo_stock,
    generar_reporte_cierres_historicos,
    generar_reporte_descuento_operario_canales,
    generar_reporte_kardex_producto,
    generar_reporte_movimientos_estandar,
    generar_reporte_pedidos_despacho,
    generar_reporte_planilla_conteo_fisico,
    generar_reporte_rotacion_consumo,
    generar_reporte_stock_critico,
)
from ..theme import ROJO

logger = logging.getLogger(__name__)

_DESCRIPCIONES_REPORTE: dict[str, str] = {
    "stock_critico": "Detalla los artículos agotados o por debajo del punto de reposición con cantidad sugerida para compras.",
    "catalogo_stock": "Listado completo del catálogo activo con existencias reales, códigos de barras y ubicaciones.",
    "pedidos_despacho": "Consolidado de pedidos preparados y despachados con cliente, bultos, armador y logística asignada.",
    "cierres_historicos": "Registro histórico de jornadas operativas cerradas, métricas de bultos y auditoría de responsables.",
    "movimientos_periodo": "Reporte estándar de Salidas, Ingresos o Consolidado Administrador (solo productos con movimiento).",
    "descuentos_canales": "Descuentos discriminados en 3 columnas (Mayoristas, Mercado Libre y Full), solo productos descontados.",
    "planilla_conteo": "Planilla imprimible ordenada por ubicación para recuento físico en depósito.",
    "auditoria_fisica": "Comparativa Digital vs. Físico del último inventario relevado con diferencias por artículo.",
    "kardex_sku": "Historial cronológico completo (entradas, salidas y saldos móviles) para un SKU puntual.",
    "rotacion_consumo": "Ranking de productos con mayor salida en el período, promedio diario y días estimados de cobertura.",
}


def _resolver_rango_fechas(preset: str, f_desde: str, f_hasta: str) -> tuple[str, str]:
    ahora = datetime.now()
    if preset == "ayer":
        ayer = (ahora - timedelta(days=1)).strftime("%Y-%m-%d")
        return ayer, ayer
    if preset == "7d":
        return (ahora - timedelta(days=6)).strftime("%Y-%m-%d"), ahora.strftime("%Y-%m-%d")
    if preset == "30d":
        return (ahora - timedelta(days=29)).strftime("%Y-%m-%d"), ahora.strftime("%Y-%m-%d")
    if preset == "personalizado":
        d1 = (f_desde or "").strip() or ahora.strftime("%Y-%m-%d")
        d2 = (f_hasta or "").strip() or d1
        return d1, d2
    hoy = ahora.strftime("%Y-%m-%d")
    return hoy, hoy


def mostrar_centro_reportes(interfaz: Any) -> None:
    """Abre la ventana modal del Centro Unificado de Reportes."""
    if not interfaz.usuario_actual:
        interfaz.notificar("Debes iniciar sesión para acceder a los reportes.")
        return

    usuario_nombre = (
        getattr(interfaz.usuario_actual, "display_name", None)
        or getattr(interfaz.usuario_actual, "username", "Operador")
    )
    carpeta_informes = Path(application_root()) / "data" / "informes"
    carpeta_informes.mkdir(parents=True, exist_ok=True)
    hoy_str = datetime.now().strftime("%Y-%m-%d")

    tipo_reporte = ft.Dropdown(
        label="Seleccionar Tipo de Reporte",
        value="stock_critico",
        options=[
            ft.DropdownOption("stock_critico", "📦 Stock Crítico y Reposición (Quiebres y Compras)"),
            ft.DropdownOption("catalogo_stock", "📋 Inventario y Catálogo General"),
            ft.DropdownOption("movimientos_periodo", "📊 Movimientos Estándar (Salidas / Ingresos / Suma Total)"),
            ft.DropdownOption("descuentos_canales", "🏷️ Descuentos por Canal (Mayoristas / Mercado Libre / Full)"),
            ft.DropdownOption("planilla_conteo", "📝 Planilla de Toma de Inventario Físico"),
            ft.DropdownOption("auditoria_fisica", "🔍 Auditoría de Inventario Físico vs. Digital"),
            ft.DropdownOption("kardex_sku", "📒 Kardex Histórico por Producto (SKU)"),
            ft.DropdownOption("rotacion_consumo", "🔥 Ranking de Rotación y Cobertura"),
            ft.DropdownOption("pedidos_despacho", "🚚 Despacho y Pedidos por Logística"),
            ft.DropdownOption("cierres_historicos", "🔒 Historial de Cierres de Jornada"),
        ],
        dense=True,
        expand=True,
    )

    descripcion_reporte = ft.Text(
        _DESCRIPCIONES_REPORTE["stock_critico"],
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
    try:
        from ...orders import LOGISTICA_OPCIONES
        for log in LOGISTICA_OPCIONES:
            transporte_filtro.options.append(ft.DropdownOption(log, log))
    except Exception:
        pass

    modo_movimiento = ft.Dropdown(
        label="Vista / Contenido del Reporte",
        value="ambos",
        options=[
            ft.DropdownOption("ambos", "Consolidado (Salidas + Ingresos)"),
            ft.DropdownOption("cierre_admin", "Consolidado Administrador (Suma Total)"),
            ft.DropdownOption("salidas", "Sólo Salidas de Stock"),
            ft.DropdownOption("ingresos", "Sólo Ingresos de Stock"),
        ],
        dense=True,
        visible=False,
    )

    orden_movimientos = ft.Dropdown(
        label="Ordenamiento",
        value="catalog",
        options=[
            ft.DropdownOption("catalog", "Orden de Catálogo"),
            ft.DropdownOption("ubicacion", "Por Ubicación"),
            ft.DropdownOption("volume", "Por Mayor Volumen"),
            ft.DropdownOption("alpha", "Alfabético"),
        ],
        dense=True,
        visible=False,
    )

    preset_periodo = ft.Dropdown(
        label="Período",
        value="hoy",
        options=[
            ft.DropdownOption("hoy", "Jornada de Hoy"),
            ft.DropdownOption("ayer", "Ayer"),
            ft.DropdownOption("7d", "Últimos 7 días"),
            ft.DropdownOption("30d", "Últimos 30 días"),
            ft.DropdownOption("personalizado", "Rango personalizado (AAAA-MM-DD)"),
        ],
        dense=True,
        visible=False,
    )

    fecha_desde_input = ft.TextField(label="Desde (AAAA-MM-DD)", value=hoy_str, dense=True, expand=True)
    fecha_hasta_input = ft.TextField(label="Hasta (AAAA-MM-DD)", value=hoy_str, dense=True, expand=True)
    fila_fechas_custom = ft.Row([fecha_desde_input, fecha_hasta_input], spacing=8, visible=False)

    sku_kardex_input = ft.TextField(
        label="Código SKU o nombre del producto",
        hint_text="ej: UT-2156 o Taladro",
        dense=True,
        visible=False,
    )
    chk_conteo_ciego = ft.Checkbox(
        label="Conteo ciego (ocultar stock actual del sistema para control real)",
        value=True,
        visible=False,
    )
    filtro_ubicacion_input = ft.TextField(
        label="Filtrar por pasillo / ubicación (opcional)",
        hint_text="ej: A-01",
        dense=True,
        visible=False,
    )
    ventana_rotacion = ft.Dropdown(
        label="Ventana de análisis",
        value="30",
        options=[
            ft.DropdownOption("7", "Últimos 7 días"),
            ft.DropdownOption("15", "Últimos 15 días"),
            ft.DropdownOption("30", "Últimos 30 días"),
            ft.DropdownOption("60", "Últimos 60 días"),
            ft.DropdownOption("90", "Últimos 90 días"),
        ],
        dense=True,
        visible=False,
    )

    def _actualizar_visibilidad_fechas(_e: ft.Event | None = None) -> None:
        sel = tipo_reporte.value
        usa_fechas = sel in ("movimientos_periodo", "descuentos_canales", "kardex_sku")
        preset_periodo.visible = usa_fechas
        fila_fechas_custom.visible = usa_fechas and preset_periodo.value == "personalizado"
        if interfaz.page:
            interfaz.page.update()

    def al_cambiar_tipo(_e: ft.Event | None = None) -> None:
        sel = str(tipo_reporte.value or "stock_critico")
        descripcion_reporte.value = _DESCRIPCIONES_REPORTE.get(sel, "")
        transporte_filtro.visible = sel == "pedidos_despacho"
        modo_movimiento.visible = sel == "movimientos_periodo"
        orden_movimientos.visible = sel == "movimientos_periodo"
        sku_kardex_input.visible = sel == "kardex_sku"
        chk_conteo_ciego.visible = sel == "planilla_conteo"
        filtro_ubicacion_input.visible = sel == "planilla_conteo"
        ventana_rotacion.visible = sel == "rotacion_consumo"
        _actualizar_visibilidad_fechas()

    tipo_reporte.on_select = al_cambiar_tipo
    preset_periodo.on_select = _actualizar_visibilidad_fechas

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
            f_desde, f_hasta = _resolver_rango_fechas(
                str(preset_periodo.value or "hoy"),
                str(fecha_desde_input.value or ""),
                str(fecha_hasta_input.value or ""),
            )

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
            elif sel == "movimientos_periodo":
                resumen = interfaz.product_store.get_period_movements_summary(
                    date_from=f_desde,
                    date_to=f_hasta,
                    order_by=str(orden_movimientos.value or "catalog"),
                )
                canales_sku = {}
                if hasattr(interfaz.order_store, "obtener_descuentos_operario_por_canal"):
                    for ch in interfaz.order_store.obtener_descuentos_operario_por_canal(
                        fecha_desde=f_desde,
                        fecha_hasta=f_hasta,
                    ):
                        canales_sku[ch["codigo"]] = ch
                ruta_generada = generar_reporte_movimientos_estandar(
                    resumen_periodo=resumen,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                    modo=str(modo_movimiento.value or "ambos"),
                    fecha_desde=f_desde,
                    fecha_hasta=f_hasta,
                    canales_por_sku=canales_sku,
                )
            elif sel == "descuentos_canales":
                items_ch = interfaz.order_store.obtener_descuentos_operario_por_canal(
                    fecha_desde=f_desde,
                    fecha_hasta=f_hasta,
                )
                mapa_orden: dict[str, int] = {}
                if hasattr(interfaz.product_store, "list_products"):
                    for idx, p in enumerate(interfaz.product_store.list_products(solo_activos=True) or []):
                        mapa_orden[str(p["code"])] = idx
                ruta_generada = generar_reporte_descuento_operario_canales(
                    items_canal=items_ch,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                    mapa_orden_catalogo=mapa_orden,
                    prefijo_archivo="Descuentos_Canales",
                    titulo_documento=f"DESCUENTOS POR CANAL ({f_desde} AL {f_hasta})",
                )
            elif sel == "planilla_conteo":
                ruta_generada = generar_reporte_planilla_conteo_fisico(
                    product_store=interfaz.product_store,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                    conteo_ciego=bool(chk_conteo_ciego.value),
                    filtro_ubicacion=str(filtro_ubicacion_input.value or ""),
                )
            elif sel == "auditoria_fisica":
                ruta_generada = generar_reporte_auditoria_inventario_fisico(
                    product_store=interfaz.product_store,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                )
            elif sel == "kardex_sku":
                ruta_generada = generar_reporte_kardex_producto(
                    product_store=interfaz.product_store,
                    product_query=str(sku_kardex_input.value or ""),
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                    fecha_desde=f_desde if preset_periodo.value == "personalizado" else "",
                    fecha_hasta=f_hasta if preset_periodo.value == "personalizado" else "",
                )
            elif sel == "rotacion_consumo":
                ruta_generada = generar_reporte_rotacion_consumo(
                    product_store=interfaz.product_store,
                    carpeta_destino=carpeta_informes,
                    formato=formato,
                    usuario=usuario_nombre,
                    dias=int(ventana_rotacion.value or 30),
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
        width=600,
        padding=16,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.ASSESSMENT, size=28, color=ROJO),
                        ft.Column(
                            [
                                ft.Text("Centro Unificado de Reportes", size=18, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                                ft.Text("Genera informes operativos, de stock, movimientos y auditoría para imprimir o exportar.", size=11, color=interfaz.secundario),
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
                modo_movimiento,
                orden_movimientos,
                preset_periodo,
                fila_fechas_custom,
                sku_kardex_input,
                chk_conteo_ciego,
                filtro_ubicacion_input,
                ventana_rotacion,
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
            scroll=ft.ScrollMode.AUTO,
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
