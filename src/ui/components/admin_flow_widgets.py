"""Subcomponentes visuales reutilizables para el panel de analítica de flujo del Administrador."""

from __future__ import annotations

from typing import Any
import flet as ft

from ..design import tono_legible
from ..theme import ROJO


def tarjeta_kpi_flujo(
    interfaz: Any,
    titulo: str,
    control_valor: ft.Text,
    control_subtitulo: ft.Text,
    icono: ft.IconData,
    color_ico: str,
) -> ft.Container:
    """Construye una tarjeta KPI compacta con ícono temático y subtítulo."""
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


def construir_cabecera_flujo(interfaz: Any, es_oscuro: bool) -> ft.Row:
    """Construye la cabecera del panel de analítica operativa en tiempo real."""
    c_verde = tono_legible("GREEN", es_oscuro)
    return ft.Row(
        [
            ft.Row(
                [
                    ft.Icon(ft.Icons.ANALYTICS, color=ROJO, size=18),
                    ft.Text(
                        "Flujo Operativo y Estadísticas de Stock (Tiempo Real)",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=interfaz.texto,
                    ),
                ],
                spacing=6,
            ),
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.SYNC, size=12, color=c_verde),
                        ft.Text(
                            "Actualizado en vivo",
                            size=10,
                            color=c_verde,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=4,
                    tight=True,
                ),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.12, c_verde),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def construir_tarjetas_graficos_flujo(
    interfaz: Any,
    es_movil: bool,
    ctrls: dict[str, Any],
) -> tuple[ft.Container, ft.Container]:
    """Construye las tarjetas izquierda (distribución) y derecha (top rotación y radar)."""
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
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
                ctrls["col_salidas_grafico"],
                ft.Divider(height=10, color=ft.Colors.with_opacity(0.1, interfaz.texto)),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TRENDING_UP, size=15, color=tono_legible("CYAN", es_oscuro)),
                        ft.Text("Evolución de Pedidos (Últimos 7 Días)", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                ctrls["col_tendencia_dias"],
                ft.Divider(height=10, color=ft.Colors.with_opacity(0.1, interfaz.texto)),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.INPUT, size=15, color=tono_legible("GREEN", es_oscuro)),
                        ft.Text("Distribución de Entradas por Origen", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                ctrls["col_entradas_grafico"],
            ],
            spacing=8,
            tight=True,
        ),
    )

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
                        ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT, size=15, color=tono_legible("AMBER", es_oscuro)),
                        ft.Text("Top 5 Productos con Mayor Rotación", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                ctrls["col_top_salidas"],
                ft.Divider(height=10, color=ft.Colors.with_opacity(0.1, interfaz.texto)),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.PEOPLE_ALT, size=15, color=tono_legible("BLUE", es_oscuro)),
                        ft.Text("Productividad de Armadores en Vivo", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                ctrls["col_armadores"],
                ft.Divider(height=10, color=ft.Colors.with_opacity(0.1, interfaz.texto)),
                ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=15, color=tono_legible("RED", es_oscuro)),
                        ft.Text("Radar de Reposición (Stock Crítico)", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                    ],
                    spacing=6,
                ),
                ctrls["col_stock_critico"],
            ],
            spacing=8,
            tight=True,
        ),
    )
    return tarjeta_distribucion, tarjeta_top_movimientos


def renderizar_barras_distribucion(
    columna: ft.Column,
    interfaz: Any,
    items_dict: dict[str, dict[str, Any]],
    mensaje_vacio: str,
    es_oscuro: bool,
    colores_por_clave: dict[str, str] | None = None,
    color_default: str = ft.Colors.GREEN_400,
) -> None:
    """Renderiza filas con etiqueta, unidades, porcentaje y barra de progreso."""
    columna.controls.clear()
    if not items_dict:
        columna.controls.append(ft.Text(mensaje_vacio, size=11, color=interfaz.secundario))
        return

    for clave, item in items_dict.items():
        u = item["unidades"]
        porc = item["porcentaje"]
        ratio = item["ratio"]
        color_c = colores_por_clave.get(clave, color_default) if colores_por_clave else color_default
        columna.controls.append(
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


def renderizar_tendencia_7_dias(
    col_dias: ft.Column | None,
    interfaz: Any,
    por_dia: list[tuple[str, int, int]],
) -> None:
    """Renderiza el minigráfico de barras horizontales con la evolución semanal de pedidos."""
    if col_dias is None:
        return
    col_dias.controls.clear()
    if not por_dia:
        col_dias.controls.append(ft.Text("Sin despachos en los últimos 7 días.", size=11, color=interfaz.secundario))
        return

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


def renderizar_top_movimientos(
    columna: ft.Column,
    interfaz: Any,
    items: list[dict[str, Any]],
    mensaje_vacio: str,
    color_valor: str,
) -> None:
    """Renderiza el ranking Top 5 de salidas o entradas."""
    columna.controls.clear()
    if not items:
        columna.controls.append(ft.Text(mensaje_vacio, size=11, color=interfaz.secundario))
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    c_ambar = tono_legible("AMBER", es_oscuro)
    for idx, it in enumerate(items, start=1):
        columna.controls.append(
            ft.Row(
                [
                    ft.Text(f"{idx}.", size=11, weight=ft.FontWeight.BOLD, color=c_ambar, width=16),
                    ft.Text(f"[{it['codigo']}]", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto, width=65),
                    ft.Text(it["descripcion"], size=11, color=interfaz.secundario, expand=True, no_wrap=True),
                    ft.Text(f"{it['cantidad']} un.", size=11, weight=ft.FontWeight.BOLD, color=color_valor),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
        )


def renderizar_productividad_armadores(
    col_arm: ft.Column | None,
    interfaz: Any,
    armadores: list[tuple[str, int, int]],
    es_oscuro: bool,
) -> None:
    """Renderiza barras comparativas de productividad por armador."""
    if col_arm is None:
        return
    col_arm.controls.clear()
    if not armadores:
        col_arm.controls.append(ft.Text("Sin armados registrados en la jornada.", size=11, color=interfaz.secundario))
        return

    c_azul = tono_legible("BLUE", es_oscuro)
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
                                    ft.Icon(ft.Icons.PERSON_OUTLINE, size=13, color=c_azul),
                                    ft.Text(armador or "Sin asignar", size=11, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                ],
                                spacing=4,
                            ),
                            ft.Text(f"{cant_a} ped. ({bultos_a} bultos)", size=10, weight=ft.FontWeight.BOLD, color=c_azul),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.ProgressBar(
                        value=ratio_a,
                        color=c_azul,
                        bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_200,
                        height=3,
                        border_radius=2,
                    ),
                ],
                spacing=2,
                tight=True,
            )
        )


def renderizar_radar_criticos(
    col_crit: ft.Column | None,
    interfaz: Any,
    product_store: Any,
) -> None:
    """Renderiza alertas de reposición (AGOTADO / QUIEBRE) desde ProductStore."""
    if col_crit is None:
        return
    col_crit.controls.clear()
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    criticos: list[Any] = []
    if product_store is not None:
        try:
            if hasattr(product_store, "get_replenishment_analysis"):
                res = product_store.get_replenishment_analysis(only_critical=True)
                if isinstance(res, (list, tuple)):
                    criticos = list(res)
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
        col_badge = tono_legible("RED" if es_agotado else "AMBER", es_oscuro)
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
        c_verde = tono_legible("GREEN", es_oscuro)
        col_crit.controls.append(
            ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=13, color=c_verde),
                    ft.Text("Todos los productos en niveles óptimos.", size=11, color=c_verde),
                ],
                spacing=6,
            )
        )
