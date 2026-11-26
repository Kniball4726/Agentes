"""Utilidades compartidas para grillas y tarjetas responsivas en Flet."""

from __future__ import annotations

from typing import Any, Sequence

import flet as ft


def ancho_viewport(interfaz: Any) -> float | None:
    """Devuelve el ancho numérico actual de ``page`` si está disponible."""
    page = getattr(interfaz, "page", None)
    w = getattr(page, "width", None)
    if isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0:
        return float(w)
    return None


def _bool_estricto(valor: Any) -> bool:
    """Devuelve True solo para booleanos verdaderos (evita falsos positivos en MagicMock)."""
    return isinstance(valor, bool) and valor


def es_viewport_estrecho(interfaz: Any, umbral: float = 768.0) -> bool:
    """Indica si el viewport es móvil o menor que ``umbral`` píxeles."""
    if _bool_estricto(getattr(interfaz, "es_pantalla_movil", False)):
        return True
    w = ancho_viewport(interfaz)
    return bool(w is not None and w < umbral)


def resolver_columnas_grilla(
    cantidad: int,
    *,
    compacto: bool = False,
    forzar_movil: bool = False,
) -> tuple[int, dict[str, int]]:
    """Calcula ``(columns, col_map)`` sin huecos para grillas de ``1..N`` tarjetas.

    Cuando ``forzar_movil`` es True (p. ej. WebView móvil que reporta un ancho
    inicial amplio), limita el número de columnas por fila para evitar tarjetas
    comprimidas.
    """
    n = max(1, int(cantidad))

    if forzar_movil:
        if compacto:
            return 12, {"xs": 6 if n > 1 else 12}
        return 12, {"xs": 12}

    if n == 1:
        return 12, {"xs": 12}

    if n == 2:
        if compacto:
            return 12, {"xs": 6}
        return 12, {"xs": 12, "md": 6}

    if n == 3:
        if compacto:
            return 12, {"xs": 6, "sm": 4}
        return 12, {"xs": 12, "sm": 6, "md": 4}

    if n == 4:
        if compacto:
            return 12, {"xs": 6, "md": 3}
        return 12, {"xs": 12, "sm": 6, "lg": 3}

    if n == 5:
        # 60 columnas virtuales dividen exactamente por 2 (30), 3 (20) y 5 (12).
        if compacto:
            return 60, {"xs": 30, "md": 20, "lg": 12}
        return 60, {"xs": 60, "sm": 30, "lg": 12}

    if n == 6:
        if compacto:
            return 12, {"xs": 6, "sm": 4, "lg": 2}
        return 12, {"xs": 12, "sm": 6, "md": 4}

    if compacto:
        return 12, {"xs": 6, "sm": 4, "lg": 3}
    return 12, {"xs": 12, "sm": 6, "lg": 4}


def grilla_tarjetas_responsiva(
    tarjetas: Sequence[ft.Control],
    *,
    interfaz: Any = None,
    compacto: bool = False,
    cols: dict[str, int] | int | None = None,
    columns: int | None = None,
    spacing: int = 10,
    run_spacing: int = 10,
    vertical_alignment: ft.CrossAxisAlignment = ft.CrossAxisAlignment.START,
) -> ft.ResponsiveRow:
    """Organiza tarjetas en un ``ft.ResponsiveRow`` adaptable a todos los breakpoints."""
    items = list(tarjetas)
    forzar_movil = _bool_estricto(getattr(interfaz, "es_pantalla_movil", False)) if interfaz is not None else False
    auto_cols_total, auto_col = resolver_columnas_grilla(
        len(items),
        compacto=compacto,
        forzar_movil=forzar_movil,
    )
    cols_total = columns if columns is not None else auto_cols_total
    col_span = cols if cols is not None else auto_col

    for tarjeta in items:
        if hasattr(tarjeta, "expand"):
            tarjeta.expand = False
        tarjeta.col = dict(col_span) if isinstance(col_span, dict) else col_span

    # En Flet 1.0.x, ResponsiveRow sin scroll/alto acotado construye un Row con
    # CrossAxisAlignment.stretch cuando sum(col) <= columns (modo PC), lo que
    # lanza `BoxConstraints forces an infinite height` dentro de Column(scroll=AUTO).
    alineacion_segura = (
        ft.CrossAxisAlignment.START
        if vertical_alignment == ft.CrossAxisAlignment.STRETCH
        else vertical_alignment
    )

    return ft.ResponsiveRow(
        items,
        columns=cols_total,
        spacing=spacing,
        run_spacing=run_spacing,
        vertical_alignment=alineacion_segura,
    )


def fila_cabecera_responsiva(
    izquierda: ft.Control,
    derecha: ft.Control | Sequence[ft.Control] | None = None,
    *,
    spacing: int = 8,
    run_spacing: int = 6,
) -> ft.Row:
    """Fila de cabecera con ``wrap=True`` para evitar desbordes horizontales en tarjetas."""
    controles: list[ft.Control] = [izquierda]
    if derecha is not None:
        if isinstance(derecha, (list, tuple)):
            controles.extend(derecha)
        else:
            controles.append(derecha)
    return ft.Row(
        controles,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        wrap=True,
        spacing=spacing,
        run_spacing=run_spacing,
    )


def barra_chips_responsiva(
    controles: Sequence[ft.Control],
    *,
    spacing: int = 6,
    run_spacing: int = 6,
) -> ft.Row:
    """Agrupa chips, badges o botones secundarios permitiendo salto de línea fluido."""
    return ft.Row(
        list(controles),
        wrap=True,
        spacing=spacing,
        run_spacing=run_spacing,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def par_accion_tarjeta(
    interfaz: Any,
    contenido_principal: ft.Control,
    accion: ft.Control,
    *,
    umbral: float = 560.0,
    spacing: int = 10,
) -> ft.Control:
    """Alinea contenido expandible y botón de acción en fila o columna según el ancho."""
    if es_viewport_estrecho(interfaz, umbral=umbral):
        return ft.Column(
            [contenido_principal, accion],
            spacing=max(6, spacing - 2),
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
    return ft.Row(
        [contenido_principal, accion],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=spacing,
    )
