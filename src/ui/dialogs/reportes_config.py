"""Configuración declarativa, resolución de fechas y despacho uniforme de reportes."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import flet as ft

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

DESCRIPCIONES_REPORTE: dict[str, str] = {
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

OPCIONES_REPORTE: tuple[tuple[str, str], ...] = (
    ("stock_critico", "📦 Stock Crítico y Reposición (Quiebres y Compras)"),
    ("catalogo_stock", "📋 Inventario y Catálogo General"),
    ("movimientos_periodo", "📊 Movimientos Estándar (Salidas / Ingresos / Suma Total)"),
    ("descuentos_canales", "🏷️ Descuentos por Canal (Mayoristas / Mercado Libre / Full)"),
    ("planilla_conteo", "📝 Planilla de Toma de Inventario Físico"),
    ("auditoria_fisica", "🔍 Auditoría de Inventario Físico vs. Digital"),
    ("kardex_sku", "📒 Kardex Histórico por Producto (SKU)"),
    ("rotacion_consumo", "🔥 Ranking de Rotación y Cobertura"),
    ("pedidos_despacho", "🚚 Despacho y Pedidos por Logística"),
    ("cierres_historicos", "🔒 Historial de Cierres de Jornada"),
)

REPORTES_CON_PERIODO = frozenset({"movimientos_periodo", "descuentos_canales", "kardex_sku"})

VISIBILIDAD_CAMPOS_REPORTE: dict[str, tuple[str, ...]] = {
    "pedidos_despacho": ("transporte_filtro",),
    "movimientos_periodo": ("modo_movimiento", "orden_movimientos"),
    "kardex_sku": ("sku_kardex_input",),
    "planilla_conteo": ("chk_conteo_ciego", "filtro_ubicacion_input"),
    "rotacion_consumo": ("ventana_rotacion",),
}


def resolver_rango_fechas(
    preset: str,
    f_desde: str,
    f_hasta: str,
    ahora: datetime | None = None,
) -> tuple[str, str]:
    """Convierte el preset seleccionado o rango manual a fechas ISO `AAAA-MM-DD`."""
    ref = ahora or datetime.now()
    if preset == "ayer":
        ayer = (ref - timedelta(days=1)).strftime("%Y-%m-%d")
        return ayer, ayer
    if preset == "7d":
        return (ref - timedelta(days=6)).strftime("%Y-%m-%d"), ref.strftime("%Y-%m-%d")
    if preset == "30d":
        return (ref - timedelta(days=29)).strftime("%Y-%m-%d"), ref.strftime("%Y-%m-%d")
    if preset == "personalizado":
        d1 = (f_desde or "").strip() or ref.strftime("%Y-%m-%d")
        d2 = (f_hasta or "").strip() or d1
        return d1, d2
    hoy = ref.strftime("%Y-%m-%d")
    return hoy, hoy


def opciones_dropdown(pares: tuple[tuple[str, str], ...]) -> list[ft.DropdownOption]:
    """Convierte pares `(clave, etiqueta)` en opciones de Flet Dropdown."""
    return [ft.DropdownOption(clave, etiqueta) for clave, etiqueta in pares]


def _gen_stock_critico(interfaz: Any, carpeta: Path, formato: str, usuario: str, _params: dict[str, Any]) -> Path:
    return generar_reporte_stock_critico(
        product_store=interfaz.product_store,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
    )


def _gen_catalogo_stock(interfaz: Any, carpeta: Path, formato: str, usuario: str, _params: dict[str, Any]) -> Path:
    return generar_reporte_catalogo_stock(
        product_store=interfaz.product_store,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
    )


def _gen_movimientos_periodo(interfaz: Any, carpeta: Path, formato: str, usuario: str, params: dict[str, Any]) -> Path:
    f_desde, f_hasta = params["f_desde"], params["f_hasta"]
    resumen = interfaz.product_store.get_period_movements_summary(
        date_from=f_desde,
        date_to=f_hasta,
        order_by=params["orden"],
    )
    canales_sku: dict[str, Any] = {}
    if hasattr(interfaz.order_store, "obtener_descuentos_operario_por_canal"):
        for ch in interfaz.order_store.obtener_descuentos_operario_por_canal(
            fecha_desde=f_desde,
            fecha_hasta=f_hasta,
        ):
            canales_sku[ch["codigo"]] = ch
    return generar_reporte_movimientos_estandar(
        resumen_periodo=resumen,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
        modo=params["modo"],
        fecha_desde=f_desde,
        fecha_hasta=f_hasta,
        canales_por_sku=canales_sku,
    )


def _gen_descuentos_canales(interfaz: Any, carpeta: Path, formato: str, usuario: str, params: dict[str, Any]) -> Path:
    f_desde, f_hasta = params["f_desde"], params["f_hasta"]
    items_ch = interfaz.order_store.obtener_descuentos_operario_por_canal(
        fecha_desde=f_desde,
        fecha_hasta=f_hasta,
    )
    mapa_orden: dict[str, int] = {}
    if hasattr(interfaz.product_store, "list_products"):
        for idx, p in enumerate(interfaz.product_store.list_products(solo_activos=True) or []):
            mapa_orden[str(p["code"])] = idx
    return generar_reporte_descuento_operario_canales(
        items_canal=items_ch,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
        mapa_orden_catalogo=mapa_orden,
        prefijo_archivo="Descuentos_Canales",
        titulo_documento=f"DESCUENTOS POR CANAL ({f_desde} AL {f_hasta})",
    )


def _gen_planilla_conteo(interfaz: Any, carpeta: Path, formato: str, usuario: str, params: dict[str, Any]) -> Path:
    return generar_reporte_planilla_conteo_fisico(
        product_store=interfaz.product_store,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
        conteo_ciego=bool(params["conteo_ciego"]),
        filtro_ubicacion=params["filtro_ubicacion"],
    )


def _gen_auditoria_fisica(interfaz: Any, carpeta: Path, formato: str, usuario: str, _params: dict[str, Any]) -> Path:
    return generar_reporte_auditoria_inventario_fisico(
        product_store=interfaz.product_store,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
    )


def _gen_kardex_sku(interfaz: Any, carpeta: Path, formato: str, usuario: str, params: dict[str, Any]) -> Path:
    es_custom = params["preset"] == "personalizado"
    return generar_reporte_kardex_producto(
        product_store=interfaz.product_store,
        product_query=params["sku_kardex"],
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
        fecha_desde=params["f_desde"] if es_custom else "",
        fecha_hasta=params["f_hasta"] if es_custom else "",
    )


def _gen_rotacion_consumo(interfaz: Any, carpeta: Path, formato: str, usuario: str, params: dict[str, Any]) -> Path:
    return generar_reporte_rotacion_consumo(
        product_store=interfaz.product_store,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
        dias=int(params["dias_rotacion"]),
    )


def _gen_pedidos_despacho(interfaz: Any, carpeta: Path, formato: str, usuario: str, params: dict[str, Any]) -> Path:
    transporte = params["transporte"]
    return generar_reporte_pedidos_despacho(
        order_store=interfaz.order_store,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
        filtro_transporte=None if transporte == "TODOS" else transporte,
    )


def _gen_cierres_historicos(interfaz: Any, carpeta: Path, formato: str, usuario: str, _params: dict[str, Any]) -> Path:
    return generar_reporte_cierres_historicos(
        order_store=interfaz.order_store,
        carpeta_destino=carpeta,
        formato=formato,
        usuario=usuario,
    )


_GENERADORES_REPORTE: dict[str, Callable[[Any, Path, str, str, dict[str, Any]], Path]] = {
    "stock_critico": _gen_stock_critico,
    "catalogo_stock": _gen_catalogo_stock,
    "movimientos_periodo": _gen_movimientos_periodo,
    "descuentos_canales": _gen_descuentos_canales,
    "planilla_conteo": _gen_planilla_conteo,
    "auditoria_fisica": _gen_auditoria_fisica,
    "kardex_sku": _gen_kardex_sku,
    "rotacion_consumo": _gen_rotacion_consumo,
    "pedidos_despacho": _gen_pedidos_despacho,
    "cierres_historicos": _gen_cierres_historicos,
}


def ejecutar_generacion_reporte(
    tipo: str,
    *,
    interfaz: Any,
    carpeta: Path,
    formato: str,
    usuario: str,
    params: dict[str, Any],
) -> Path | None:
    """Despacha la generación de un reporte según su identificador."""
    generador = _GENERADORES_REPORTE.get(tipo)
    if generador is None:
        return None
    return generador(interfaz, carpeta, formato, usuario, params)
