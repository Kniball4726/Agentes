"""Módulo de visualización y consulta interactiva de stock en tiempo real."""

from __future__ import annotations

from typing import Any

import flet as ft

from ..components.debounce import Debouncer
from ..theme import ROJO
from .stock_view_logic import (
    calcular_resumen_stock,
    cargar_catalogo_stock,
    construir_chip_kpi,
    construir_tarjeta_producto_stock,
    filtrar_productos_stock,
)


def _construir_estado_vacio_stock(interfaz: Any) -> ft.Container:
    return ft.Container(
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


def mostrar_dialogo_ver_stock(interfaz: Any) -> None:
    """Abre el visor interactivo de existencias en tiempo real."""
    if not interfaz.usuario_actual:
        interfaz.notificar("Debes iniciar sesión para consultar el stock.")
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    filtro_texto = ft.TextField(
        hint_text="Buscar código, descripción, código de barras o ubicación...",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        dense=True,
        border_radius=8,
        autofocus=True,
    )
    filtro_estado = ["todos"]
    limite = [60]
    contenedor_kpis = ft.Row(spacing=8, run_spacing=6, wrap=True)
    columna_productos = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)
    cache_productos: list[dict[str, Any]] = []

    def cargar_datos() -> None:
        cache_productos.clear()
        try:
            cache_productos.extend(cargar_catalogo_stock(interfaz))
        except Exception as exc:
            interfaz.notificar(f"Error al cargar stock: {exc}")

    def _cambiar_filtro_kpi(clave: str) -> None:
        filtro_estado[0] = clave
        limite[0] = 60
        renderizar_kpis()
        actualizar_lista()

    def renderizar_kpis() -> None:
        resumen = calcular_resumen_stock(cache_productos)
        activo = filtro_estado[0]
        contenedor_kpis.controls = [
            construir_chip_kpi(interfaz, "Total Ítems", resumen["total"], ft.Colors.BLUE_400, "todos", activo, _cambiar_filtro_kpi),
            construir_chip_kpi(interfaz, "Unidades", f"{resumen['unidades']:,}", ft.Colors.CYAN_400, "todos", activo, _cambiar_filtro_kpi),
            construir_chip_kpi(interfaz, "En Quiebre", resumen["quiebres"], ROJO, "quiebre", activo, _cambiar_filtro_kpi),
            construir_chip_kpi(interfaz, "Stock Bajo", resumen["bajos"], ft.Colors.AMBER_600, "bajo", activo, _cambiar_filtro_kpi),
            construir_chip_kpi(interfaz, "Normal", resumen["normales"], ft.Colors.GREEN_600, "normal", activo, _cambiar_filtro_kpi),
        ]

    def _cargar_mas() -> None:
        limite[0] += 60
        actualizar_lista()

    def actualizar_lista() -> None:
        filtrados = filtrar_productos_stock(
            cache_productos,
            termino=filtro_texto.value or "",
            estado=filtro_estado[0],
        )
        tarjetas: list[ft.Control] = [
            construir_tarjeta_producto_stock(interfaz, p, es_oscuro)
            for p in filtrados[: limite[0]]
        ]

        if not tarjetas:
            tarjetas.append(_construir_estado_vacio_stock(interfaz))
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

    debouncer = Debouncer(0.15)

    def _restablecer_filtro_si_busca() -> None:
        limite[0] = 60
        val = (filtro_texto.value or "").strip()
        if val and filtro_estado[0] != "todos":
            filtro_estado[0] = "todos"
            renderizar_kpis()

    def al_escribir_busqueda(_e: Any) -> None:
        _restablecer_filtro_si_busca()
        debouncer.debounce(actualizar_lista)

    def al_enviar_busqueda(_e: Any) -> None:
        debouncer.cancel()
        _restablecer_filtro_si_busca()
        actualizar_lista()

    def limpiar_busqueda(_e: Any) -> None:
        debouncer.cancel()
        filtro_texto.value = ""
        limite[0] = 60
        actualizar_lista()

    filtro_texto.on_change = al_escribir_busqueda
    filtro_texto.on_submit = al_enviar_busqueda

    btn_recargar = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip="Recargar existencias desde la base de datos",
        on_click=lambda _e: (cargar_datos(), renderizar_kpis(), actualizar_lista()),
    )
    btn_limpiar = ft.IconButton(
        icon=ft.Icons.CLEAR,
        tooltip="Limpiar búsqueda",
        on_click=limpiar_busqueda,
    )

    cargar_datos()
    renderizar_kpis()
    actualizar_lista()

    acciones = [ft.TextButton("Cerrar", on_click=lambda _e: interfaz.page.pop_dialog())]
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
            width=interfaz.ancho_adaptable(780),
            height=interfaz.alto_adaptable(580),
            content=ft.Column(
                [contenedor_kpis, ft.Row([filtro_texto, btn_limpiar], spacing=6), columna_productos],
                spacing=10,
                expand=True,
            ),
        ),
        actions=acciones,
        actions_alignment=ft.MainAxisAlignment.END,
    )
    interfaz.page.show_dialog(dialogo)
