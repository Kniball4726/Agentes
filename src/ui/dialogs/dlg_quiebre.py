"""Diálogo y banner de alerta adaptativo para productos en quiebre de stock."""

from __future__ import annotations

import logging
from typing import Any
import flet as ft
from ..theme import ROJO

logger = logging.getLogger(__name__)


def actualizar_alerta_quiebre(interfaz: Any, criticos: list | None = None) -> None:
    """Actualiza y renderiza el banner adaptable de alerta de quiebre de stock en el dashboard."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "administrador":
        interfaz.banner_alerta_quiebre.visible = False
        return

    if criticos is None:
        try:
            from ...inventory import StockManager

            sm = StockManager(interfaz.menu.ruta_excel_base)
            criticos = sm.obtener_analisis_reposicion(solo_criticos=True)
        except Exception:
            criticos = []

    if not criticos:
        interfaz.banner_alerta_quiebre.visible = False
        return

    agotados = sum(1 for p in criticos if int(p.get("stock", 0) if isinstance(p, dict) else p["stock"]) <= 0)
    quiebres = len(criticos) - agotados
    total_pedir = sum(int(p.get("cantidad_sugerida_pedir", 0) if isinstance(p, dict) else p["cantidad_sugerida_pedir"]) for p in criticos)

    if not hasattr(interfaz, "_quiebres_telegram_notificados"):
        interfaz._quiebres_telegram_notificados = set()

    # Notificaciones automáticas de Telegram y Webhooks
    for c in criticos:
        item = dict(c) if hasattr(c, "keys") else (c if isinstance(c, dict) else {})
        cod_c = str(item.get("code", "")).strip()
        if cod_c and cod_c not in interfaz._quiebres_telegram_notificados:
            interfaz._quiebres_telegram_notificados.add(cod_c)
            try:
                from ...integrations.telegram_notifier import notificar_quiebre_stock_telegram

                notificar_quiebre_stock_telegram(
                    codigo=cod_c,
                    nombre=str(item.get("name", "")).strip(),
                    stock_actual=int(item.get("stock", 0)),
                    stock_minimo=int(item.get("stock_minimo", item.get("min_stock", 0))),
                )
            except Exception:
                pass
            try:
                from ...webhook_manager import despachar_evento_webhook

                despachar_evento_webhook(
                    "QUIEBRE_STOCK",
                    {
                        "codigo": cod_c,
                        "nombre": str(item.get("name", "")).strip(),
                        "stock_actual": int(item.get("stock", 0)),
                        "stock_minimo": int(item.get("stock_minimo", item.get("min_stock", 0))),
                        "estado": "AGOTADO" if int(item.get("stock", 0)) <= 0 else "CRITICO",
                    },
                )
            except Exception:
                pass

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    ancho_pag = getattr(interfaz.page, "width", 1200) if hasattr(interfaz, "page") and interfaz.page else 1200
    es_pantalla_estrecha = es_movil or (isinstance(ancho_pag, (int, float)) and ancho_pag < 1050)

    interfaz.banner_alerta_quiebre.visible = True
    interfaz.banner_alerta_quiebre.bgcolor = (
        ft.Colors.RED_900 if interfaz.modo_oscuro else ft.Colors.RED_50
    )
    interfaz.banner_alerta_quiebre.border = ft.Border.all(
        1.5, ft.Colors.RED_400 if interfaz.modo_oscuro else ft.Colors.RED_700
    )
    interfaz.banner_alerta_quiebre.border_radius = 12
    interfaz.banner_alerta_quiebre.padding = ft.Padding(12, 10, 12, 10) if es_movil else ft.Padding(16, 12, 16, 12)

    # 1. Badges y métricas visuales del quiebre
    chips_resumen: list[ft.Control] = []
    if agotados > 0:
        chips_resumen.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.BLOCK, color=ft.Colors.WHITE, size=12),
                        ft.Text(f"{agotados} Agotados", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ],
                    spacing=4,
                    tight=True,
                ),
                bgcolor=ft.Colors.RED_700,
                border_radius=8,
                padding=ft.Padding(8, 3, 8, 3),
            )
        )
    if quiebres > 0:
        chips_resumen.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.BLACK, size=13),
                        ft.Text(f"{quiebres} En Quiebre", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                    ],
                    spacing=4,
                    tight=True,
                ),
                bgcolor=ft.Colors.AMBER_400,
                border_radius=8,
                padding=ft.Padding(8, 3, 8, 3),
            )
        )
    if total_pedir > 0:
        chips_resumen.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.FACTORY_OUTLINED,
                            color=ft.Colors.BLUE_200 if interfaz.modo_oscuro else ft.Colors.BLUE_900,
                            size=13,
                        ),
                        ft.Text(
                            f"Sugerido: +{total_pedir} un.",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLUE_200 if interfaz.modo_oscuro else ft.Colors.BLUE_900,
                        ),
                    ],
                    spacing=4,
                    tight=True,
                ),
                bgcolor=ft.Colors.BLUE_900 if interfaz.modo_oscuro else ft.Colors.BLUE_100,
                border_radius=8,
                padding=ft.Padding(8, 3, 8, 3),
            )
        )

    # 2. Bloque de información
    bloque_info_quiebre = ft.Row(
        [
            ft.Icon(
                ft.Icons.WARNING_AMBER_ROUNDED,
                color=ft.Colors.RED_400 if interfaz.modo_oscuro else ft.Colors.RED_700,
                size=26,
            ),
            ft.Column(
                [
                    ft.Text(
                        f"ALERTA DE QUIEBRE DE STOCK ({len(criticos)} producto{'s' if len(criticos) != 1 else ''} en riesgo)",
                        weight=ft.FontWeight.BOLD,
                        size=12 if es_movil else 13,
                        color=ft.Colors.RED_300 if interfaz.modo_oscuro else ft.Colors.RED_800,
                    ),
                    ft.Row(chips_resumen, wrap=True, spacing=6, tight=True),
                ],
                spacing=4,
                expand=True,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        expand=not es_pantalla_estrecha,
    )

    # 3. Vista rápida inline expandible
    contenedor_vista_rapida = ft.Container(visible=False)

    def toggle_vista_rapida(_e: ft.ControlEvent) -> None:
        contenedor_vista_rapida.visible = not contenedor_vista_rapida.visible
        btn_vista_rapida.icon = (
            ft.Icons.KEYBOARD_ARROW_UP if contenedor_vista_rapida.visible else ft.Icons.KEYBOARD_ARROW_DOWN
        )
        btn_vista_rapida.text = (
            "Ocultar lista" if contenedor_vista_rapida.visible else "Vista rápida"
        )
        interfaz.page.update()

    btn_vista_rapida = ft.Button(
        "Vista rápida",
        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
        on_click=toggle_vista_rapida,
        bgcolor=ft.Colors.TRANSPARENT,
        color=ft.Colors.RED_300 if interfaz.modo_oscuro else ft.Colors.RED_800,
    )

    # 4. Bloque de botones de acción
    bloque_botones_quiebre = ft.Row(
        [
            btn_vista_rapida,
            ft.Button(
                "Ver detalle",
                icon=ft.Icons.VISIBILITY,
                on_click=lambda _e, items=criticos: mostrar_detalle_quiebre(interfaz, items),
                bgcolor=ft.Colors.TRANSPARENT,
                color=ft.Colors.RED_300 if interfaz.modo_oscuro else ft.Colors.RED_800,
            ),
            ft.Button(
                "Generar pedido fábrica",
                icon=ft.Icons.FILE_DOWNLOAD,
                on_click=interfaz.generar_pedido_fabrica,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
            ),
        ],
        spacing=6,
        wrap=True,
    )

    # 5. Generar contenido para la vista rápida inline
    items_vista_rapida = []
    # Ordenar por menor stock primero (agotados al inicio)
    criticos_ordenados = sorted(
        criticos,
        key=lambda x: int(x.get("stock", 0) if isinstance(x, dict) else x["stock"]),
    )
    for p in criticos_ordenados[:5]:
        c_cod = str(p.get("code", "") if isinstance(p, dict) else p["code"])
        c_nom = str(p.get("name", "") if isinstance(p, dict) else p["name"])
        c_stk = int(p.get("stock", 0) if isinstance(p, dict) else p["stock"])
        c_min = int(p.get("stock_minimo", 0) if isinstance(p, dict) else p["stock_minimo"])
        c_pedir = int(p.get("cantidad_sugerida_pedir", 0) if isinstance(p, dict) else p["cantidad_sugerida_pedir"])
        es_ag = c_stk <= 0

        badge_inline = ft.Container(
            content=ft.Text("AGOTADO" if es_ag else f"QUIEBRE (Mín {c_min})", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if es_ag else ft.Colors.AMBER_700,
            border_radius=4,
            padding=ft.Padding(5, 2, 5, 2),
        )

        items_vista_rapida.append(
            ft.Container(
                bgcolor=ft.Colors.BLACK_12 if interfaz.modo_oscuro else ft.Colors.WHITE,
                border_radius=6,
                padding=6,
                content=ft.Row(
                    [
                        ft.Text(c_cod, weight=ft.FontWeight.BOLD, size=11, width=70),
                        ft.Text(c_nom, size=11, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        badge_inline,
                        ft.Text(f"Stock: {c_stk}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400 if es_ag else ft.Colors.AMBER_400),
                        ft.Text(f"Pedir: +{c_pedir}", size=11, color=ft.Colors.BLUE_400),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    if len(criticos) > 5:
        items_vista_rapida.append(
            ft.Row(
                [
                    ft.TextButton(
                        f"Ver los {len(criticos) - 5} productos restantes en detalle...",
                        icon=ft.Icons.ARROW_FORWARD,
                        on_click=lambda _e, items=criticos: mostrar_detalle_quiebre(interfaz, items),
                    )
                ],
                alignment=ft.MainAxisAlignment.END,
            )
        )

    contenedor_vista_rapida.content = ft.Column(
        [
            ft.Divider(height=1),
            ft.Column(items_vista_rapida, spacing=4, tight=True),
        ],
        spacing=6,
        tight=True,
    )

    # 6. Renderizado adaptativo superior
    fila_o_columna_principal = (
        ft.Column(
            [bloque_info_quiebre, bloque_botones_quiebre],
            spacing=8,
            tight=True,
        )
        if es_pantalla_estrecha
        else ft.Row(
            [bloque_info_quiebre, bloque_botones_quiebre],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    interfaz.banner_alerta_quiebre.content = ft.Column(
        [fila_o_columna_principal, contenedor_vista_rapida],
        spacing=6,
        tight=True,
    )


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
