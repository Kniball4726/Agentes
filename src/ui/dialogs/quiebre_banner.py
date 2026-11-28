"""Banner adaptativo y notificación automática de quiebres de stock para el dashboard."""

from __future__ import annotations

import logging
import sys
import threading
from typing import Any, Callable

import flet as ft

from ..theme import ROJO

logger = logging.getLogger("stockagent.ui.quiebre")


def _leer_campo_critico(item: Any, clave: str, default: Any = 0) -> Any:
    if isinstance(item, dict):
        return item.get(clave, default)
    try:
        return item[clave]
    except (KeyError, IndexError, TypeError):
        return default


def _enviar_notificaciones_quiebre_batch(pendientes: list[tuple[str, str, int, int]]) -> None:
    for cod, nom, st, st_min in pendientes:
        try:
            from ...integrations.telegram_notifier import notificar_quiebre_stock_telegram

            notificar_quiebre_stock_telegram(
                codigo=cod,
                nombre=nom,
                stock_actual=st,
                stock_minimo=st_min,
            )
        except Exception as exc:
            logger.debug("No se pudo enviar alerta Telegram de quiebre para '%s': %s", cod, exc)
        try:
            from ...webhook_manager import despachar_evento_webhook

            despachar_evento_webhook(
                "QUIEBRE_STOCK",
                {
                    "codigo": cod,
                    "nombre": nom,
                    "stock_actual": st,
                    "stock_minimo": st_min,
                    "estado": "AGOTADO" if st <= 0 else "CRITICO",
                },
            )
        except Exception as exc:
            logger.debug("No se pudo despachar webhook QUIEBRE_STOCK para '%s': %s", cod, exc)


def _despachar_notificaciones_quiebre(interfaz: Any, criticos: list[Any]) -> None:
    """Deduplica alertas ya enviadas y despacha Telegram/Webhooks sin bloquear el hilo UI."""
    if not hasattr(interfaz, "_quiebres_telegram_notificados"):
        interfaz._quiebres_telegram_notificados = set()

    notificaciones_pendientes: list[tuple[str, str, int, int]] = []
    for c in criticos:
        item = dict(c) if hasattr(c, "keys") else (c if isinstance(c, dict) else {})
        cod_c = str(item.get("code", "")).strip()
        if cod_c and cod_c not in interfaz._quiebres_telegram_notificados:
            interfaz._quiebres_telegram_notificados.add(cod_c)
            notificaciones_pendientes.append(
                (
                    cod_c,
                    str(item.get("name", "")).strip(),
                    int(item.get("stock", 0)),
                    int(item.get("stock_minimo", item.get("min_stock", 0))),
                )
            )

    if not notificaciones_pendientes:
        return

    es_test = getattr(interfaz, "_is_mock", False) or "pytest" in sys.modules
    if es_test:
        _enviar_notificaciones_quiebre_batch(notificaciones_pendientes)
    else:
        threading.Thread(
            target=_enviar_notificaciones_quiebre_batch,
            args=(notificaciones_pendientes,),
            daemon=True,
        ).start()


def _construir_chips_resumen(modo_oscuro: bool, agotados: int, quiebres: int, total_pedir: int) -> list[ft.Control]:
    chips: list[ft.Control] = []
    if agotados > 0:
        chips.append(
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
        chips.append(
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
        color_sug = ft.Colors.BLUE_200 if modo_oscuro else ft.Colors.BLUE_900
        chips.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.FACTORY_OUTLINED, color=color_sug, size=13),
                        ft.Text(f"Sugerido: +{total_pedir} un.", size=11, weight=ft.FontWeight.BOLD, color=color_sug),
                    ],
                    spacing=4,
                    tight=True,
                ),
                bgcolor=ft.Colors.BLUE_900 if modo_oscuro else ft.Colors.BLUE_100,
                border_radius=8,
                padding=ft.Padding(8, 3, 8, 3),
            )
        )
    return chips


def _construir_item_vista_rapida(
    interfaz: Any,
    item: Any,
    mapa_runway: dict[str, float],
    es_pantalla_estrecha: bool,
) -> ft.Container:
    c_cod = str(_leer_campo_critico(item, "code", ""))
    c_nom = str(_leer_campo_critico(item, "name", ""))
    c_stk = int(_leer_campo_critico(item, "stock", 0))
    c_min = int(_leer_campo_critico(item, "stock_minimo", 0))
    c_pedir = int(_leer_campo_critico(item, "cantidad_sugerida_pedir", 0))
    es_ag = c_stk <= 0
    runway_val = mapa_runway.get(c_cod)
    txt_runway = f"⏳ {runway_val}d" if runway_val is not None else ""

    badge_inline = ft.Container(
        content=ft.Text("AGOTADO" if es_ag else f"QUIEBRE (Mín {c_min})", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        bgcolor=ft.Colors.RED_700 if es_ag else ft.Colors.AMBER_700,
        border_radius=4,
        padding=ft.Padding(5, 2, 5, 2),
    )
    txt_runway_ctrl = (
        ft.Text(
            txt_runway,
            size=10,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.PURPLE_300 if interfaz.modo_oscuro else ft.Colors.PURPLE_700,
            tooltip="Días estimados de inventario restante según consumo reciente",
        )
        if txt_runway
        else None
    )

    if es_pantalla_estrecha:
        meta_fila: list[ft.Control] = [
            ft.Text(f"Stock: {c_stk}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400 if es_ag else ft.Colors.AMBER_400),
            ft.Text(f"Pedir: +{c_pedir}", size=11, color=ft.Colors.BLUE_400),
        ]
        if txt_runway_ctrl is not None:
            meta_fila.append(txt_runway_ctrl)
        contenido_item: ft.Control = ft.Column(
            [
                ft.Row(
                    [ft.Text(c_cod, weight=ft.FontWeight.BOLD, size=11), badge_inline],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    wrap=True,
                    spacing=6,
                ),
                ft.Text(c_nom, size=11, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Row(meta_fila, spacing=10, wrap=True, run_spacing=2),
            ],
            spacing=3,
            tight=True,
        )
    else:
        controles_fila: list[ft.Control] = [
            ft.Text(c_cod, weight=ft.FontWeight.BOLD, size=11, width=70),
            ft.Text(c_nom, size=11, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            badge_inline,
            ft.Text(f"Stock: {c_stk}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400 if es_ag else ft.Colors.AMBER_400),
            ft.Text(f"Pedir: +{c_pedir}", size=11, color=ft.Colors.BLUE_400),
        ]
        if txt_runway_ctrl is not None:
            controles_fila.append(txt_runway_ctrl)
        contenido_item = ft.Row(controles_fila, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    return ft.Container(
        bgcolor=ft.Colors.BLACK_12 if interfaz.modo_oscuro else ft.Colors.WHITE,
        border_radius=6,
        padding=6,
        content=contenido_item,
    )


def _construir_contenido_vista_rapida(
    interfaz: Any,
    criticos: list[Any],
    es_pantalla_estrecha: bool,
    on_ver_detalle: Callable[[Any, list | None], None],
) -> ft.Column:
    criticos_ordenados = sorted(criticos, key=lambda x: int(_leer_campo_critico(x, "stock", 0)))
    mapa_runway: dict[str, float] = {}
    if hasattr(interfaz, "stock_manager") and hasattr(interfaz.stock_manager, "obtener_mapa_runway_inventario"):
        try:
            mapa_runway = interfaz.stock_manager.obtener_mapa_runway_inventario(dias_ventana=14)
        except Exception as exc:
            logger.debug("No se pudo calcular mapa de runway para vista rápida: %s", exc)
            mapa_runway = {}

    items_vista_rapida: list[ft.Control] = [
        _construir_item_vista_rapida(interfaz, p, mapa_runway, es_pantalla_estrecha)
        for p in criticos_ordenados[:5]
    ]
    if len(criticos) > 5:
        items_vista_rapida.append(
            ft.Row(
                [
                    ft.TextButton(
                        f"Ver los {len(criticos) - 5} productos restantes en detalle...",
                        icon=ft.Icons.ARROW_FORWARD,
                        on_click=lambda _e, items=criticos: on_ver_detalle(interfaz, items),
                    )
                ],
                alignment=ft.MainAxisAlignment.END,
            )
        )
    return ft.Column([ft.Divider(height=1), ft.Column(items_vista_rapida, spacing=4, tight=True)], spacing=6, tight=True)


def _cargar_criticos_si_faltan(interfaz: Any, criticos: list | None) -> list[Any]:
    if criticos is not None:
        return criticos
    try:
        from ...inventory import StockManager

        sm = StockManager(interfaz.menu.ruta_excel_base)
        return sm.obtener_analisis_reposicion(solo_criticos=True)
    except Exception as exc:
        logger.debug("No se pudo obtener análisis de reposición para banner: %s", exc)
        return []


def actualizar_alerta_quiebre(
    interfaz: Any,
    criticos: list | None = None,
    on_ver_detalle: Callable[[Any, list | None], None] | None = None,
) -> None:
    """Actualiza y renderiza el banner adaptable de alerta de quiebre de stock en el dashboard."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "administrador":
        interfaz.banner_alerta_quiebre.visible = False
        return

    criticos_res = _cargar_criticos_si_faltan(interfaz, criticos)
    if not criticos_res:
        interfaz.banner_alerta_quiebre.visible = False
        return

    if on_ver_detalle is None:
        from .dlg_quiebre import mostrar_detalle_quiebre

        on_ver_detalle = mostrar_detalle_quiebre

    agotados = sum(1 for p in criticos_res if int(_leer_campo_critico(p, "stock", 0)) <= 0)
    quiebres = len(criticos_res) - agotados
    total_pedir = sum(int(_leer_campo_critico(p, "cantidad_sugerida_pedir", 0)) for p in criticos_res)

    _despachar_notificaciones_quiebre(interfaz, criticos_res)

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    ancho_pag = getattr(interfaz.page, "width", 1200) if hasattr(interfaz, "page") and interfaz.page else 1200
    es_pantalla_estrecha = es_movil or (isinstance(ancho_pag, (int, float)) and ancho_pag < 1050)

    banner = interfaz.banner_alerta_quiebre
    banner.visible = True
    banner.bgcolor = ft.Colors.RED_900 if interfaz.modo_oscuro else ft.Colors.RED_50
    banner.border = ft.Border.all(1.5, ft.Colors.RED_400 if interfaz.modo_oscuro else ft.Colors.RED_700)
    banner.border_radius = 12
    banner.padding = ft.Padding(12, 10, 12, 10) if es_movil else ft.Padding(16, 12, 16, 12)

    chips_resumen = _construir_chips_resumen(interfaz.modo_oscuro, agotados, quiebres, total_pedir)
    bloque_info_quiebre = ft.Row(
        [
            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_400 if interfaz.modo_oscuro else ft.Colors.RED_700, size=26),
            ft.Column(
                [
                    ft.Text(
                        f"ALERTA DE QUIEBRE DE STOCK ({len(criticos_res)} producto{'s' if len(criticos_res) != 1 else ''} en riesgo)",
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

    contenedor_vista_rapida = ft.Container(
        visible=False,
        content=_construir_contenido_vista_rapida(interfaz, criticos_res, es_pantalla_estrecha, on_ver_detalle),
    )

    def toggle_vista_rapida(_e: ft.ControlEvent) -> None:
        contenedor_vista_rapida.visible = not contenedor_vista_rapida.visible
        btn_vista_rapida.icon = ft.Icons.KEYBOARD_ARROW_UP if contenedor_vista_rapida.visible else ft.Icons.KEYBOARD_ARROW_DOWN
        btn_vista_rapida.content = "Ocultar lista" if contenedor_vista_rapida.visible else "Vista rápida"
        interfaz.page.update()

    color_btn = ft.Colors.RED_300 if interfaz.modo_oscuro else ft.Colors.RED_800
    btn_vista_rapida = ft.Button("Vista rápida", icon=ft.Icons.KEYBOARD_ARROW_DOWN, on_click=toggle_vista_rapida, bgcolor=ft.Colors.TRANSPARENT, color=color_btn)
    bloque_botones_quiebre = ft.Row(
        [
            btn_vista_rapida,
            ft.Button("Ver detalle", icon=ft.Icons.VISIBILITY, on_click=lambda _e, items=criticos_res: on_ver_detalle(interfaz, items), bgcolor=ft.Colors.TRANSPARENT, color=color_btn),
            ft.Button("Generar pedido fábrica", icon=ft.Icons.FILE_DOWNLOAD, on_click=interfaz.generar_pedido_fabrica, bgcolor=ROJO, color=ft.Colors.WHITE),
        ],
        spacing=6,
        wrap=True,
    )

    fila_o_columna_principal: ft.Control = (
        ft.Column([bloque_info_quiebre, bloque_botones_quiebre], spacing=8, tight=True)
        if es_pantalla_estrecha
        else ft.Row([bloque_info_quiebre, bloque_botones_quiebre], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
    )
    banner.content = ft.Column([fila_o_columna_principal, contenedor_vista_rapida], spacing=6, tight=True)
