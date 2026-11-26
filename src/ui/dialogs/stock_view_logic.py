"""Lógica de dominio y constructores de tarjetas para el visor interactivo de stock."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ..design import par_accion_tarjeta
from ..theme import ROJO


def cargar_catalogo_stock(interfaz: Any) -> list[dict[str, Any]]:
    """Obtiene el catálogo de productos desde ProductStore o StockManager como respaldo."""
    if hasattr(interfaz, "product_store") and interfaz.product_store:
        filas = interfaz.product_store.list_products()
        return [dict(f) if not isinstance(f, dict) else f for f in filas]
    if hasattr(interfaz, "menu") and hasattr(interfaz.menu, "ruta_excel_base"):
        from ...inventory import StockManager

        sm = StockManager(interfaz.menu.ruta_excel_base)
        return sm.obtener_catalogo_completo()
    return []


def calcular_resumen_stock(productos: list[dict[str, Any]]) -> dict[str, int]:
    """Calcula métricas agregadas (totales, unidades, quiebres, bajos y normales)."""
    total_prods = len(productos)
    total_unidades = 0
    quiebres = 0
    bajos = 0
    for p in productos:
        stock = int(p.get("stock") or 0)
        stock_min = int(p.get("stock_minimo") or 5)
        total_unidades += stock
        if stock <= 0:
            quiebres += 1
        elif stock <= stock_min:
            bajos += 1
    return {
        "total": total_prods,
        "unidades": total_unidades,
        "quiebres": quiebres,
        "bajos": bajos,
        "normales": total_prods - quiebres - bajos,
    }


def filtrar_productos_stock(
    productos: list[dict[str, Any]],
    termino: str = "",
    estado: str = "todos",
) -> list[dict[str, Any]]:
    """Filtra productos por estado de stock y término multicriterio (con tolerancia a ceros)."""
    q = (termino or "").strip().lower()
    q_sin_ceros = q.lstrip("0")
    filtrados: list[dict[str, Any]] = []

    for p in productos:
        stock = int(p.get("stock") or 0)
        stock_min = int(p.get("stock_minimo") or 5)

        if estado == "quiebre" and stock > 0:
            continue
        if estado == "bajo" and not (0 < stock <= stock_min):
            continue
        if estado == "normal" and stock <= stock_min:
            continue

        if q:
            codigo = str(p.get("code") or "").lower()
            nombre = str(p.get("name") or "").lower()
            barras = str(p.get("cod_barras") or "").lower()
            ubicacion = str(p.get("ubicacion") or "").lower()
            codigo_sin_ceros = codigo.lstrip("0")
            coincide_codigo = q in codigo or (q_sin_ceros != "" and q_sin_ceros == codigo_sin_ceros)
            if not coincide_codigo and q not in nombre and q not in barras and q not in ubicacion:
                continue

        filtrados.append(p)
    return filtrados


def clasificar_estado_stock(stock: int, stock_min: int) -> tuple[str, Any, Any]:
    """Devuelve `(etiqueta, color, color_fondo_badge)` para un nivel de existencias."""
    if stock <= 0:
        return "QUIEBRE", ROJO, ft.Colors.with_opacity(0.15, ROJO)
    if stock <= stock_min:
        return "STOCK BAJO", ft.Colors.AMBER_600, ft.Colors.with_opacity(0.15, ft.Colors.AMBER_600)
    return "NORMAL", ft.Colors.GREEN_600, ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)


def construir_chip_kpi(
    interfaz: Any,
    label: str,
    valor: str | int,
    color: Any,
    clave_filtro: str,
    filtro_activo: str,
    on_click_filtro: Callable[[str], None],
) -> ft.Container:
    """Construye una píldora KPI interactiva que permite filtrar por estado de inventario."""
    seleccionado = filtro_activo == clave_filtro
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(width=8, height=8, border_radius=4, bgcolor=color),
                ft.Text(f"{label}:", size=11, color=interfaz.secundario),
                ft.Text(
                    str(valor),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=color if seleccionado else interfaz.texto,
                ),
            ],
            spacing=6,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
        border_radius=20,
        bgcolor=ft.Colors.with_opacity(0.18 if seleccionado else 0.07, color),
        border=ft.Border.all(
            1,
            color if seleccionado else ft.Colors.with_opacity(0.2, color),
        ),
        ink=True,
        on_click=lambda _e: on_click_filtro(clave_filtro),
        tooltip=f"Filtrar por {label}",
    )


def construir_tarjeta_producto_stock(
    interfaz: Any,
    producto: dict[str, Any],
    es_oscuro: bool,
) -> ft.Container:
    """Construye la tarjeta visual de un artículo con código, ubicación, barras y estado."""
    stock = int(producto.get("stock") or 0)
    stock_min = int(producto.get("stock_minimo") or 5)
    codigo = str(producto.get("code") or "")
    nombre = str(producto.get("name") or "")
    barras = str(producto.get("cod_barras") or "")
    ubicacion = str(producto.get("ubicacion") or "")
    estado_texto, color_stock, bg_badge = clasificar_estado_stock(stock, stock_min)

    chips_secundarios: list[ft.Control] = [
        ft.Container(
            content=ft.Text(f"Cód: {codigo}", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto),
            bgcolor=ft.Colors.with_opacity(0.08, interfaz.texto),
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=4,
        )
    ]
    if ubicacion:
        chips_secundarios.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.LOCATION_ON, size=11, color=ft.Colors.PURPLE_300),
                        ft.Text(ubicacion, size=11, color=ft.Colors.PURPLE_300),
                    ],
                    spacing=2,
                    tight=True,
                ),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_500),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
            )
        )
    if barras:
        chips_secundarios.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.QR_CODE, size=11, color=interfaz.secundario),
                        ft.Text(barras, size=11, color=interfaz.secundario),
                    ],
                    spacing=2,
                    tight=True,
                ),
                bgcolor=ft.Colors.with_opacity(0.06, interfaz.texto),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
            )
        )

    info_prod = ft.Column(
        [
            ft.Text(
                nombre,
                size=13,
                weight=ft.FontWeight.W_600,
                color=interfaz.texto,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Row(chips_secundarios, spacing=6, wrap=True, run_spacing=4),
        ],
        spacing=4,
        expand=True,
    )
    bloque_stock = ft.Column(
        [
            ft.Container(
                content=ft.Text(f"{stock}", size=18, weight=ft.FontWeight.BOLD, color=color_stock),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(
                content=ft.Text(estado_texto, size=9, weight=ft.FontWeight.BOLD, color=color_stock),
                bgcolor=bg_badge,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=6,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Text(f"Mín: {stock_min}", size=10, color=interfaz.secundario),
        ],
        spacing=2,
        horizontal_alignment=ft.CrossAxisAlignment.END,
    )
    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.04 if es_oscuro else 0.02, interfaz.texto),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, interfaz.borde)),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        content=par_accion_tarjeta(interfaz, info_prod, bloque_stock, umbral=420.0, spacing=12),
    )
