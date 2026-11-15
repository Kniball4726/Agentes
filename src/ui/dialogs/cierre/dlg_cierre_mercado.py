"""Diálogo interactivo para el Cierre de Mercado con pestañas dedicadas para Mercado Libre y Mercado Full."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import flet as ft

from ...theme import ROJO
from .cierre_mercado_cards import (
    renderizar_lista_historial_mercado,
    renderizar_lista_pedidos_mercado,
)
from .cierre_mercado_exec import ejecutar_tarea_cierre_mercado

logger = logging.getLogger("stockagent.ui.cierre_mercado")


def mostrar_dialogo_cierre_mercado(interfaz: Any, tab_inicial: int = 0) -> None:
    """Abre el panel con pestañas 100% aisladas para cerrar Mercado Libre (diario) o Mercado Full (multidía)."""
    if not interfaz.exigir_roles("picker", "operador", "administrador", "master"):
        return

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    armador_filtro = (
        interfaz.usuario_actual.username
        if getattr(interfaz, "usuario_actual", None) and interfaz.usuario_actual.role == "picker"
        else None
    )

    tab_activa = [tab_inicial]

    # Estado de Mercado Libre
    pedidos_ml: list[Any] = []
    seleccionados_ml: dict[int, bool] = {}
    lista_ml = ft.ListView(expand=True, spacing=6)
    resumen_ml = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto)

    # Estado de Mercado Full
    pedidos_full: list[Any] = []
    seleccionados_full: dict[int, bool] = {}
    lista_full = ft.ListView(expand=True, spacing=6)
    resumen_full = ft.Text("", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto)

    # Estado de Historial
    lista_historial = ft.ListView(expand=True, spacing=6)

    # Botón principal contextual
    btn_confirmar = ft.Button(
        "Cerrar Colecta Mercado Libre",
        icon=ft.Icons.STOREFRONT,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    def _recargar_ml() -> None:
        nonlocal pedidos_ml
        try:
            pedidos_ml = interfaz.order_store.listar_pedidos_mercado_pendientes_cierre(
                tipo="MERCADO_LIBRE",
                armador=armador_filtro,
            )
        except Exception as exc:
            logger.warning("Error al listar pedidos ML pendientes: %s", exc)
            pedidos_ml = []
        renderizar_lista_pedidos_mercado(
            lista_ctrl=lista_ml,
            resumen_ctrl=resumen_ml,
            seleccionados=seleccionados_ml,
            pedidos=pedidos_ml,
            interfaz=interfaz,
            es_oscuro=es_oscuro,
            es_full=False,
            on_cambio_seleccion=_sync_estado_boton,
        )

    def _recargar_full() -> None:
        nonlocal pedidos_full
        try:
            pedidos_full = interfaz.order_store.listar_pedidos_mercado_pendientes_cierre(
                tipo="MERCADO_FULL",
                armador=armador_filtro,
            )
        except Exception as exc:
            logger.warning("Error al listar pedidos Full pendientes: %s", exc)
            pedidos_full = []
        renderizar_lista_pedidos_mercado(
            lista_ctrl=lista_full,
            resumen_ctrl=resumen_full,
            seleccionados=seleccionados_full,
            pedidos=pedidos_full,
            interfaz=interfaz,
            es_oscuro=es_oscuro,
            es_full=True,
            on_cambio_seleccion=_sync_estado_boton,
        )

    def _sync_estado_boton() -> None:
        idx = tab_activa[0]
        if idx == 0:
            # Mercado Libre
            activos = [p for p in pedidos_ml if seleccionados_ml.get(p.id, False)]
            total_u = sum(p.articulos_descontados for p in activos)
            btn_confirmar.visible = True
            btn_confirmar.text = "Cerrar Colecta Mercado Libre"
            btn_confirmar.icon = ft.Icons.STOREFRONT
            btn_confirmar.bgcolor = ROJO
            if not activos:
                resumen_ml.value = "⚠️ Selecciona al menos un paquete de Mercado Libre para cerrar colecta."
                resumen_ml.color = ft.Colors.AMBER_400
                btn_confirmar.disabled = True
            else:
                resumen_ml.value = f"📦 {len(activos)} paquetes de ML seleccionados ({total_u} unidades a certificar)"
                resumen_ml.color = interfaz.texto
                btn_confirmar.disabled = False
        elif idx == 1:
            # Mercado Full
            activos = [p for p in pedidos_full if seleccionados_full.get(p.id, False)]
            total_u = sum(p.articulos_descontados for p in activos)
            btn_confirmar.visible = True
            btn_confirmar.text = "Cerrar Envío Mercado Full (Pallet)"
            btn_confirmar.icon = ft.Icons.LOCAL_SHIPPING
            btn_confirmar.bgcolor = ft.Colors.AMBER_800
            if not activos:
                resumen_full.value = "⚠️ Selecciona al menos un lote de Full para cerrar el envío."
                resumen_full.color = ft.Colors.AMBER_400
                btn_confirmar.disabled = True
            else:
                resumen_full.value = f"🚚 {len(activos)} tandas de Full seleccionadas ({total_u} unidades en el pallet)"
                resumen_full.color = interfaz.texto
                btn_confirmar.disabled = False
        else:
            # Historial
            btn_confirmar.visible = False
            btn_confirmar.disabled = True

        interfaz.page.update()

    def _recargar_historial() -> None:
        try:
            cierres = interfaz.order_store.listar_cierres_mercado(limit=30)
        except Exception:
            cierres = []
        renderizar_lista_historial_mercado(
            lista_historial=lista_historial,
            cierres=cierres,
            interfaz=interfaz,
            es_oscuro=es_oscuro,
        )

    async def on_confirmar_cierre(_e: ft.Event) -> None:
        idx = tab_activa[0]
        if idx == 0:
            tipo_m = "MERCADO_LIBRE"
            peds_a_cerrar = [p for p in pedidos_ml if seleccionados_ml.get(p.id, False)]
        elif idx == 1:
            tipo_m = "MERCADO_FULL"
            peds_a_cerrar = [p for p in pedidos_full if seleccionados_full.get(p.id, False)]
        else:
            return

        if not peds_a_cerrar:
            interfaz.notificar("No hay pedidos seleccionados en este canal.")
            return

        btn_confirmar.disabled = True
        interfaz.page.pop_dialog()

        res_cierre: dict[str, Any] = {}

        def tarea() -> None:
            res = ejecutar_tarea_cierre_mercado(
                interfaz=interfaz,
                pedidos_seleccionados=peds_a_cerrar,
                tipo_mercado=tipo_m,
            )
            res_cierre.update(res)

        nombre_tarea = "Cierre Colecta Mercado Libre" if idx == 0 else "Cierre Envío Mercado Full"
        exito = await interfaz.ejecutar_tarea(nombre_tarea, tarea)
        if not exito:
            return

        interfaz.actualizar_listas()
        if hasattr(interfaz, "actualizar_estado"):
            interfaz.actualizar_estado()

        pdf_path = res_cierre.get("pdf_path")
        cid = res_cierre.get("cierre_id", 0)
        tot = res_cierre.get("total_articulos", 0)

        interfaz.notificar(f"✅ {nombre_tarea} #{cid} generado exitosamente ({tot} unidades).")

        # Abre modal con opciones de impresión en Windows / descarga
        if pdf_path and pdf_path.exists():
            interfaz.mostrar_opciones_documento(pdf_path)

    btn_confirmar.on_click = on_confirmar_cierre

    vista_ml = ft.Column(
        [
            ft.Text(
                "📦 Paquetes de Mercado Libre pistoleados o cargados hoy (Colecta Diaria):",
                size=12,
                weight=ft.FontWeight.W_500,
                color=interfaz.texto,
            ),
            ft.Container(
                content=lista_ml,
                height=260 if not es_movil else 200,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=6,
            ),
            ft.Container(content=resumen_ml, padding=ft.Padding.symmetric(vertical=4)),
        ],
        spacing=6,
    )

    vista_full = ft.Column(
        [
            ft.Text(
                "🚚 Tandas y planillas de Mercado Envíos Full acumuladas (Pallet Multidía):",
                size=12,
                weight=ft.FontWeight.W_500,
                color=interfaz.texto,
            ),
            ft.Container(
                content=lista_full,
                height=260 if not es_movil else 200,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=6,
            ),
            ft.Container(content=resumen_full, padding=ft.Padding.symmetric(vertical=4)),
        ],
        spacing=6,
    )

    vista_historial = ft.Column(
        [
            ft.Text("Historial de comprobantes de cierre emitidos (ML y Full):", size=11, color=interfaz.secundario),
            ft.Container(
                content=lista_historial,
                height=280 if not es_movil else 220,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=6,
            ),
        ],
        spacing=6,
    )

    def on_tab_change(e: ft.Event) -> None:
        idx = 0
        try:
            idx = int(e.control.selected_index if hasattr(e.control, "selected_index") else getattr(e, "data", 0) or 0)
        except Exception:
            idx = 0
        tab_activa[0] = idx
        _sync_estado_boton()

    tabs = ft.Tabs(
        length=3,
        expand=True,
        selected_index=tab_inicial,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Mercado Libre (Diario)", icon=ft.Icons.STOREFRONT),
                        ft.Tab(label="Mercado Full (Multidía)", icon=ft.Icons.LOCAL_SHIPPING),
                        ft.Tab(label="Historial de Cierres", icon=ft.Icons.HISTORY),
                    ]
                ),
                ft.TabBarView(expand=True, controls=[vista_ml, vista_full, vista_historial]),
            ],
        ),
    )
    tabs.on_change = on_tab_change

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.FACT_CHECK, color=ROJO, size=24),
                ft.Text("Cierre de Mercado · Descuento Individual", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=650 if not es_movil else 340,
            content=tabs,
        ),
        actions=[
            btn_confirmar,
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )

    _recargar_ml()
    _recargar_full()
    _recargar_historial()
    _sync_estado_boton()
    interfaz.page.show_dialog(dialogo)
