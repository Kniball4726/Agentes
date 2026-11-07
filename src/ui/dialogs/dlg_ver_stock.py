"""Módulo de visualización y consulta interactiva de stock en tiempo real."""

from typing import Any
import flet as ft
from ..theme import ROJO


def mostrar_dialogo_ver_stock(interfaz: Any) -> None:
    """Abre el visor interactivo de existencias en tiempo real."""
    if not interfaz.usuario_actual:
        interfaz.notificar("Debes iniciar sesión para consultar el stock.")
        return

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))

    filtro_texto = ft.TextField(
        hint_text="Buscar código, descripción, código de barras o ubicación...",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        dense=True,
        border_radius=8,
        autofocus=True,
    )

    filtro_estado = ["todos"]  # "todos", "normal", "bajo", "quiebre"
    limite = [60]

    contenedor_kpis = ft.Row(spacing=8, scroll=ft.ScrollMode.ADAPTIVE)
    columna_productos = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

    cache_productos: list[dict[str, Any]] = []

    def cargar_datos() -> None:
        nonlocal cache_productos
        cache_productos.clear()
        try:
            if hasattr(interfaz, "product_store") and interfaz.product_store:
                filas = interfaz.product_store.list_products()
                for f in filas:
                    d = dict(f) if not isinstance(f, dict) else f
                    cache_productos.append(d)
            elif hasattr(interfaz, "menu") and hasattr(interfaz.menu, "ruta_excel_base"):
                from ...stock_manager import StockManager
                sm = StockManager(interfaz.menu.ruta_excel_base)
                cache_productos = sm.obtener_catalogo_completo()
        except Exception as exc:
            interfaz.notificar(f"Error al cargar stock: {exc}")

    def renderizar_kpis() -> None:
        total_prods = len(cache_productos)
        total_unidades = sum(int(p.get("stock") or 0) for p in cache_productos)
        quiebres = sum(1 for p in cache_productos if int(p.get("stock") or 0) <= 0)
        bajos = sum(
            1
            for p in cache_productos
            if 0 < int(p.get("stock") or 0) <= int(p.get("stock_minimo") or 5)
        )
        normales = total_prods - quiebres - bajos

        def _kpi_chip(label: str, valor: str | int, color: str, clave_filtro: str) -> ft.Control:
            seleccionado = filtro_estado[0] == clave_filtro
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            width=8,
                            height=8,
                            border_radius=4,
                            bgcolor=color,
                        ),
                        ft.Text(f"{label}:", size=11, color=interfaz.secundario),
                        ft.Text(str(valor), size=12, weight=ft.FontWeight.BOLD, color=color if seleccionado else interfaz.texto),
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
                on_click=lambda _e: _cambiar_filtro_kpi(clave_filtro),
                tooltip=f"Filtrar por {label}",
            )

        contenedor_kpis.controls = [
            _kpi_chip("Total Ítems", total_prods, ft.Colors.BLUE_400, "todos"),
            _kpi_chip("Unidades", f"{total_unidades:,}", ft.Colors.CYAN_400, "todos"),
            _kpi_chip("En Quiebre", quiebres, ROJO, "quiebre"),
            _kpi_chip("Stock Bajo", bajos, ft.Colors.AMBER_600, "bajo"),
            _kpi_chip("Normal", normales, ft.Colors.GREEN_600, "normal"),
        ]

    def _cambiar_filtro_kpi(clave: str) -> None:
        filtro_estado[0] = clave
        limite[0] = 60
        renderizar_kpis()
        actualizar_lista()

    def actualizar_lista() -> None:
        termino = (filtro_texto.value or "").strip().lower()
        estado = filtro_estado[0]

        filtrados: list[dict[str, Any]] = []
        for p in cache_productos:
            stock = int(p.get("stock") or 0)
            stock_min = int(p.get("stock_minimo") or 5)

            # Filtro por estado
            if estado == "quiebre" and stock > 0:
                continue
            if estado == "bajo" and not (0 < stock <= stock_min):
                continue
            if estado == "normal" and stock <= stock_min:
                continue

            # Filtro por término
            if termino:
                codigo = str(p.get("code") or "").lower()
                nombre = str(p.get("name") or "").lower()
                barras = str(p.get("cod_barras") or "").lower()
                ubicacion = str(p.get("ubicacion") or "").lower()
                if (
                    termino not in codigo
                    and termino not in nombre
                    and termino not in barras
                    and termino not in ubicacion
                ):
                    continue

            filtrados.append(p)

        items_a_mostrar = filtrados[: limite[0]]
        tarjetas: list[ft.Control] = []

        for p in items_a_mostrar:
            stock = int(p.get("stock") or 0)
            stock_min = int(p.get("stock_minimo") or 5)
            codigo = str(p.get("code") or "")
            nombre = str(p.get("name") or "")
            barras = str(p.get("cod_barras") or "")
            ubicacion = str(p.get("ubicacion") or "")

            if stock <= 0:
                color_stock = ROJO
                estado_texto = "QUIEBRE"
                bg_badge = ft.Colors.with_opacity(0.15, ROJO)
            elif stock <= stock_min:
                color_stock = ft.Colors.AMBER_600
                estado_texto = "STOCK BAJO"
                bg_badge = ft.Colors.with_opacity(0.15, ft.Colors.AMBER_600)
            else:
                color_stock = ft.Colors.GREEN_600
                estado_texto = "NORMAL"
                bg_badge = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)

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

            tarjeta = ft.Container(
                bgcolor=ft.Colors.with_opacity(0.04 if es_oscuro else 0.02, interfaz.texto),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, interfaz.borde)),
                border_radius=10,
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(
                                    nombre,
                                    size=13,
                                    weight=ft.FontWeight.W_600,
                                    color=interfaz.texto,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row(chips_secundarios, spacing=6, wrap=True),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        ft.Column(
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
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            tarjetas.append(tarjeta)

        if not tarjetas:
            tarjetas.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.SEARCH_OFF, size=36, color=interfaz.secundario),
                            ft.Text("No se encontraron productos coincidentes", size=13, color=interfaz.secundario),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                )
            )
        elif len(filtrados) > limite[0]:
            tarjetas.append(
                ft.Container(
                    content=ft.Button(
                        f"Mostrar más ({len(filtrados) - limite[0]} restantes)",
                        icon=ft.Icons.EXPAND_MORE,
                        on_click=lambda _e: _cargar_mas(),
                    ),
                    alignment=ft.Alignment.CENTER,
                    padding=10,
                )
            )

        columna_productos.controls = tarjetas
        if hasattr(interfaz, "page") and interfaz.page:
            try:
                interfaz.page.update()
            except Exception:
                pass

    def _cargar_mas() -> None:
        limite[0] += 60
        actualizar_lista()

    def al_escribir_busqueda(_e: Any) -> None:
        limite[0] = 60
        actualizar_lista()

    filtro_texto.on_change = al_escribir_busqueda

    btn_recargar = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip="Recargar existencias desde la base de datos",
        on_click=lambda _e: (cargar_datos(), renderizar_kpis(), actualizar_lista()),
    )

    btn_limpiar = ft.IconButton(
        icon=ft.Icons.CLEAR,
        tooltip="Limpiar búsqueda",
        on_click=lambda _e: setattr(filtro_texto, "value", "") or actualizar_lista(),
    )

    # Cargar datos iniciales
    cargar_datos()
    renderizar_kpis()
    actualizar_lista()

    ancho_modal = interfaz.ancho_adaptable(780)
    alto_modal = interfaz.alto_adaptable(580)

    acciones = [
        ft.TextButton("Cerrar", on_click=lambda _e: interfaz.page.pop_dialog()),
    ]
    if getattr(getattr(interfaz, "usuario_actual", None), "role", "") == "administrador":
        acciones.insert(
            0,
            ft.TextButton(
                "Gestionar Productos",
                icon=ft.Icons.SETTINGS,
                on_click=lambda _e: (interfaz.page.pop_dialog(), interfaz.mostrar_gestion_productos()),
            ),
        )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.VISIBILITY, color=ft.Colors.BLUE_400, size=24),
                ft.Column(
                    [
                        ft.Text("Ver Stock en Tiempo Real", size=17, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                        ft.Text("Consulta rápida de existencias, ubicaciones y quiebres", size=11, color=interfaz.secundario),
                    ],
                    spacing=1,
                    expand=True,
                ),
                btn_recargar,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=ft.Container(
            width=ancho_modal,
            height=alto_modal,
            content=ft.Column(
                [
                    contenedor_kpis,
                    ft.Row([filtro_texto, btn_limpiar], spacing=6),
                    columna_productos,
                ],
                spacing=10,
                expand=True,
            ),
        ),
        actions=acciones,
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
