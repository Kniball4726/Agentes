"""Diálogo y banner de alerta adaptativo para productos en quiebre de stock."""

from __future__ import annotations

import logging
from typing import Any
import flet as ft
from ..theme import ROJO
from .quiebre_banner import actualizar_alerta_quiebre as _actualizar_alerta_quiebre_banner

logger = logging.getLogger(__name__)


def actualizar_alerta_quiebre(interfaz: Any, criticos: list | None = None) -> None:
    """Actualiza y renderiza el banner adaptable de alerta de quiebre de stock en el dashboard."""
    _actualizar_alerta_quiebre_banner(interfaz, criticos, on_ver_detalle=mostrar_detalle_quiebre)


def mostrar_detalle_quiebre(interfaz: Any, criticos: list | None = None) -> None:
    """Muestra el modal detallado, responsivo y con búsqueda para productos en quiebre."""
    if not interfaz.exigir_roles("administrador"):
        return

    if criticos is None:
        try:
            from ...inventory import StockManager

            sm = StockManager(interfaz.menu.ruta_excel_base)
            criticos = sm.obtener_analisis_reposicion(solo_criticos=True)
        except Exception:
            criticos = []

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    ancho_modal = (
        interfaz.ancho_adaptable(720, margen=16)
        if hasattr(interfaz, "ancho_adaptable")
        else (340 if es_movil else 680)
    )

    col_items = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=360)
    filtro_activo = ["todos"]  # "todos", "agotados", "quiebres"
    filtro_texto = ft.TextField(
        hint_text="Buscar por SKU o descripción...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
    )

    def renderizar_lista() -> None:
        col_items.controls.clear()
        query = (filtro_texto.value or "").strip().lower()

        filtrados = []
        for p in criticos:
            cod = str(p.get("code", "") if isinstance(p, dict) else p["code"]).strip()
            nom = str(p.get("name", "") if isinstance(p, dict) else p["name"]).strip()
            stk = int(p.get("stock", 0) if isinstance(p, dict) else p["stock"])
            es_agotado = stk <= 0

            # Filtro por estado
            if filtro_activo[0] == "agotados" and not es_agotado:
                continue
            if filtro_activo[0] == "quiebres" and es_agotado:
                continue

            # Filtro por texto
            if query and query not in cod.lower() and query not in nom.lower():
                continue

            filtrados.append(p)

        for p in filtrados:
            cod = str(p.get("code", "") if isinstance(p, dict) else p["code"]).strip()
            nom = str(p.get("name", "") if isinstance(p, dict) else p["name"]).strip()
            stk = int(p.get("stock", 0) if isinstance(p, dict) else p["stock"])
            s_min = int(p.get("stock_minimo", 0) if isinstance(p, dict) else p["stock_minimo"])
            pedir = int(p.get("cantidad_sugerida_pedir", 0) if isinstance(p, dict) else p["cantidad_sugerida_pedir"])
            es_ag = stk <= 0

            tag_txt = "AGOTADO" if es_ag else f"QUIEBRE (Mín: {s_min})"
            tag_color = ft.Colors.RED_400 if es_ag else ft.Colors.AMBER_400
            tag_bg = ft.Colors.RED_900 if es_ag else ft.Colors.AMBER_900

            # En pantallas móviles o estrechas, tarjeta vertical de 2 filas
            if es_movil or ancho_modal < 520:
                contenido_card = ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(cod, weight=ft.FontWeight.BOLD, size=12),
                                ft.Container(
                                    content=ft.Text(tag_txt, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    bgcolor=tag_bg,
                                    border_radius=4,
                                    padding=ft.Padding(5, 2, 5, 2),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(nom, size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Row(
                            [
                                ft.Text(f"Stock: {stk} un.", size=11, color=tag_color, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Mín: {s_min} un.", size=11, color=interfaz.secundario),
                                ft.Text(f"Pedir: +{pedir} un.", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=4,
                    tight=True,
                )
            else:
                # En pantallas normales, fila horizontal equilibrada
                contenido_card = ft.Row(
                    [
                        ft.Text(cod, width=75, weight=ft.FontWeight.BOLD, size=12),
                        ft.Text(nom, expand=True, size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{stk} un.", width=65, color=tag_color, weight=ft.FontWeight.BOLD, size=12),
                        ft.Container(
                            content=ft.Text(tag_txt, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=tag_bg,
                            border_radius=4,
                            padding=ft.Padding(6, 2, 6, 2),
                            width=120,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text(
                            f"Pedir: +{pedir} un.",
                            width=95,
                            color=ft.Colors.BLUE_300 if interfaz.modo_oscuro else ft.Colors.BLUE_700,
                            size=11,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                )

            col_items.controls.append(
                ft.Container(
                    padding=8,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    bgcolor=interfaz.superficie,
                    content=contenido_card,
                )
            )

        if not col_items.controls:
            col_items.controls.append(
                ft.Container(
                    padding=20,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("No se encontraron productos críticos con el filtro actual.", color=interfaz.secundario),
                )
            )

        lbl_conteo.value = f"Mostrando {len(filtrados)} de {len(criticos)} productos en riesgo"
        interfaz.page.update()

    filtro_texto.on_change = lambda _e: renderizar_lista()

    def set_filtro(modo: str) -> None:
        filtro_activo[0] = modo
        btn_filtro_todos.style = estilo_activo if modo == "todos" else estilo_inactivo
        btn_filtro_agotados.style = estilo_activo if modo == "agotados" else estilo_inactivo
        btn_filtro_quiebres.style = estilo_activo if modo == "quiebres" else estilo_inactivo
        renderizar_lista()

    estilo_activo = ft.ButtonStyle(bgcolor=ROJO, color=ft.Colors.WHITE)
    estilo_inactivo = ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT, color=interfaz.texto)

    tot_ag = sum(1 for p in criticos if int(p.get("stock", 0) if isinstance(p, dict) else p["stock"]) <= 0)
    tot_qb = len(criticos) - tot_ag
    tot_pd = sum(int(p.get("cantidad_sugerida_pedir", 0) if isinstance(p, dict) else p["cantidad_sugerida_pedir"]) for p in criticos)

    btn_filtro_todos = ft.Button(f"Todos ({len(criticos)})", style=estilo_activo, on_click=lambda _e: set_filtro("todos"))
    btn_filtro_agotados = ft.Button(f"Agotados ({tot_ag})", style=estilo_inactivo, on_click=lambda _e: set_filtro("agotados"))
    btn_filtro_quiebres = ft.Button(f"En Quiebre ({tot_qb})", style=estilo_inactivo, on_click=lambda _e: set_filtro("quiebres"))

    lbl_conteo = ft.Text(f"Mostrando {len(criticos)} productos en riesgo", size=11, color=interfaz.secundario)

    banner_resumen_modal = ft.Container(
        bgcolor=ft.Colors.BLUE_900 if interfaz.modo_oscuro else ft.Colors.BLUE_50,
        border=ft.Border.all(1, ft.Colors.BLUE_700 if interfaz.modo_oscuro else ft.Colors.BLUE_200),
        border_radius=8,
        padding=8,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.BLUE_400, size=18),
                ft.Text(
                    f"Volumen sugerido a fabricar para restablecer stock de seguridad: {tot_pd:,} unidades.",
                    size=11,
                    weight=ft.FontWeight.W_500,
                    color=ft.Colors.BLUE_200 if interfaz.modo_oscuro else ft.Colors.BLUE_900,
                    expand=True,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    renderizar_lista()

    contenido_modal = ft.Container(
        width=ancho_modal,
        content=ft.Column(
            [
                banner_resumen_modal,
                ft.Row([filtro_texto], tight=True),
                ft.Row([btn_filtro_todos, btn_filtro_agotados, btn_filtro_quiebres], wrap=True, spacing=6),
                lbl_conteo,
                ft.Divider(height=1),
                col_items,
            ],
            tight=True,
            spacing=8,
        ),
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_400, size=24),
                ft.Text(f"Productos en quiebre de stock ({len(criticos)})", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=contenido_modal,
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
            interfaz.boton_dialogo(
                "Generar pedido Excel",
                lambda _e: (interfaz.page.pop_dialog(), interfaz.generar_pedido_fabrica()),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
