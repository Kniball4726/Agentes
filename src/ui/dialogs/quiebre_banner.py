"""Banner adaptativo y notificación automática de quiebres de stock para el dashboard."""

from __future__ import annotations

from typing import Any, Callable
import flet as ft

from ..theme import ROJO


def actualizar_alerta_quiebre(
    interfaz: Any,
    criticos: list | None = None,
    on_ver_detalle: Callable[[Any, list | None], None] | None = None,
) -> None:
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

    if on_ver_detalle is None:
        from .dlg_quiebre import mostrar_detalle_quiebre
        on_ver_detalle = mostrar_detalle_quiebre

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
    interfaz.banner_alerta_quiebre.bgcolor = ft.Colors.RED_900 if interfaz.modo_oscuro else ft.Colors.RED_50
    interfaz.banner_alerta_quiebre.border = ft.Border.all(
        1.5, ft.Colors.RED_400 if interfaz.modo_oscuro else ft.Colors.RED_700
    )
    interfaz.banner_alerta_quiebre.border_radius = 12
    interfaz.banner_alerta_quiebre.padding = ft.Padding(12, 10, 12, 10) if es_movil else ft.Padding(16, 12, 16, 12)

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

    contenedor_vista_rapida = ft.Container(visible=False)

    def toggle_vista_rapida(_e: ft.ControlEvent) -> None:
        contenedor_vista_rapida.visible = not contenedor_vista_rapida.visible
        btn_vista_rapida.icon = (
            ft.Icons.KEYBOARD_ARROW_UP if contenedor_vista_rapida.visible else ft.Icons.KEYBOARD_ARROW_DOWN
        )
        btn_vista_rapida.text = "Ocultar lista" if contenedor_vista_rapida.visible else "Vista rápida"
        interfaz.page.update()

    btn_vista_rapida = ft.Button(
        "Vista rápida",
        icon=ft.Icons.KEYBOARD_ARROW_DOWN,
        on_click=toggle_vista_rapida,
        bgcolor=ft.Colors.TRANSPARENT,
        color=ft.Colors.RED_300 if interfaz.modo_oscuro else ft.Colors.RED_800,
    )

    bloque_botones_quiebre = ft.Row(
        [
            btn_vista_rapida,
            ft.Button(
                "Ver detalle",
                icon=ft.Icons.VISIBILITY,
                on_click=lambda _e, items=criticos: on_ver_detalle(interfaz, items),
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

    items_vista_rapida = []
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
                        on_click=lambda _e, items=criticos: on_ver_detalle(interfaz, items),
                    )
                ],
                alignment=ft.MainAxisAlignment.END,
            )
        )

    contenedor_vista_rapida.content = ft.Column(
        [ft.Divider(height=1), ft.Column(items_vista_rapida, spacing=4, tight=True)],
        spacing=6,
        tight=True,
    )

    fila_o_columna_principal = (
        ft.Column([bloque_info_quiebre, bloque_botones_quiebre], spacing=8, tight=True)
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
