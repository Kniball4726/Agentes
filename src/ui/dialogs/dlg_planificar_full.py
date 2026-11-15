"""Diálogo para la planificación, carga de Excel y monitoreo en tiempo real de Mercado Envíos Full."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import flet as ft

from ..theme import ROJO
from ...inventory import StockManager as _DefaultStockManager
from ...parsers.mercado_full_parser import parsear_archivo_mercado_full
import sys


def _get_stock_manager():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def mostrar_planificar_full(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para que el Administrador cargue el Excel de Full y monitoree el picking en tiempo real."""
    if not interfaz.exigir_roles("administrador", "master", "operador"):
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    carpeta_full = getattr(interfaz.menu, "carpeta_mercado_full", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "MercadoFull"
    )
    carpeta_full.mkdir(parents=True, exist_ok=True)

    archivos_pendientes: list[Path] = []
    for ext in ("*.xlsx", "*.xls"):
        archivos_pendientes.extend(carpeta_full.glob(ext))
    archivos_pendientes.sort()

    tab_actual = ["monitor" if interfaz.order_store.obtener_plan_activo_mercado_full() else "nuevo"]

    # -------------------------------------------------------------
    # TAB 1: NUEVO ENVÍO (CARGA EXCEL)
    # -------------------------------------------------------------
    archivo_seleccionado: list[Path | None] = [archivos_pendientes[0] if archivos_pendientes else None]
    items_parseados: list[tuple[str, str, int]] = []
    totales_dict: dict[str, int] = {}

    txt_nombre_envio = ft.TextField(
        label="Nombre o Referencia del Envío",
        value=f"Envío Full - {datetime.now().strftime('%d/%m/%Y')}",
        dense=True,
        expand=True,
    )

    lista_items_nuevo = ft.ListView(expand=True, spacing=4, height=220)
    lbl_resumen_nuevo = ft.Text(
        "Seleccione una planilla Excel para previsualizar los artículos.",
        size=12,
        color=interfaz.secundario,
    )

    selector_archivo = ft.Dropdown(
        label="Planilla Excel (.xlsx / .xls)",
        options=[ft.dropdown.Option(arch.name) for arch in archivos_pendientes],
        value=archivos_pendientes[0].name if archivos_pendientes else None,
        dense=True,
        expand=True,
    )

    def cargar_datos_excel(arch: Path) -> None:
        items_parseados.clear()
        totales_dict.clear()
        lista_items_nuevo.controls.clear()

        try:
            totales, detalle = parsear_archivo_mercado_full(arch)
        except Exception as e:
            lbl_resumen_nuevo.value = f"Error al procesar {arch.name}: {e}"
            lbl_resumen_nuevo.color = ft.Colors.RED_400
            interfaz.page.update()
            return

        if not totales:
            lbl_resumen_nuevo.value = f"El archivo {arch.name} no contiene columnas válidas de SKU/Cantidad."
            lbl_resumen_nuevo.color = ft.Colors.AMBER_400
            interfaz.page.update()
            return

        totales_dict.update(totales)
        sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
        for cod, cant in totales.items():
            nom = "Producto en catálogo"
            if hasattr(sm, "catalogo") and cod in sm.catalogo:
                nom = sm.catalogo[cod][1]
            items_parseados.append((cod, nom, cant))

        total_u = sum(totales.values())
        lbl_resumen_nuevo.value = f"✔ {len(totales)} productos cargados ({total_u} unidades totales)."
        lbl_resumen_nuevo.color = ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_700

        for cod, desc, cant in items_parseados:
            lista_items_nuevo.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=90),
                            ft.Text(desc, size=11, expand=True, no_wrap=True),
                            ft.Text(f"{cant} un.", weight=ft.FontWeight.BOLD, color=ROJO, size=11, width=60),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        interfaz.page.update()

    def al_cambiar_dropdown(_e: ft.Event) -> None:
        nom = selector_archivo.value
        for a in archivos_pendientes:
            if a.name == nom:
                archivo_seleccionado[0] = a
                cargar_datos_excel(a)
                txt_nombre_envio.value = f"Envío Full - {a.stem}"
                break

    selector_archivo.on_change = al_cambiar_dropdown

    if archivo_seleccionado[0]:
        cargar_datos_excel(archivo_seleccionado[0])

    def al_subir_archivo(guardados: list[Path]) -> None:
        nonlocal archivos_pendientes
        for g in guardados:
            if g not in archivos_pendientes:
                archivos_pendientes.append(g)
        selector_archivo.options = [ft.dropdown.Option(a.name) for a in archivos_pendientes]
        ultimo = guardados[-1]
        archivo_seleccionado[0] = ultimo
        selector_archivo.value = ultimo.name
        txt_nombre_envio.value = f"Envío Full - {ultimo.stem}"
        cargar_datos_excel(ultimo)

    async def examinar_pc(_e: ft.Event) -> None:
        await interfaz.subir_archivos_desde_pc(
            carpeta_destino=carpeta_full,
            extensiones=["xlsx", "xls"],
            titulo="Seleccionar planilla de Mercado Full",
            al_terminar=al_subir_archivo,
        )

    btn_publicar = ft.Button(
        "🚀 Crear Envío y Notificar al Picker",
        icon=ft.Icons.SEND,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
    )

    # -------------------------------------------------------------
    # TAB 2: MONITOR EN TIEMPO REAL
    # -------------------------------------------------------------
    planes_disponibles = interfaz.order_store.listar_planes_mercado_full()
    plan_activo_id: list[int | None] = [planes_disponibles[0]["id"] if planes_disponibles else None]

    selector_plan = ft.Dropdown(
        label="Seleccionar Envío / Plan",
        options=[
            ft.dropdown.Option(
                key=str(p["id"]),
                text=f"#{p['id']} - {p['nombre_envio']} ({p['porcentaje']}%) [{p['estado'].upper()}]",
            )
            for p in planes_disponibles
        ],
        value=str(plan_activo_id[0]) if plan_activo_id[0] else None,
        dense=True,
        expand=True,
    )

    lbl_estado_monitor = ft.Text("Estado: -", size=12, weight=ft.FontWeight.BOLD)
    lbl_picker_monitor = ft.Text("Picker: -", size=12)
    lbl_cantidades_monitor = ft.Text("0 / 0 un.", size=14, weight=ft.FontWeight.BOLD)
    lbl_porcentaje_monitor = ft.Text("0.0%", size=20, weight=ft.FontWeight.BOLD, color=ROJO)
    progreso_monitor = ft.ProgressBar(value=0.0, color=ROJO, bgcolor=ft.Colors.GREY_300, height=10)

    lista_items_monitor = ft.ListView(expand=True, spacing=4, height=220)

    def recargar_monitor(pid: int | None = None) -> None:
        target_id = pid or plan_activo_id[0]
        if not target_id:
            lbl_estado_monitor.value = "Sin envíos registrados."
            lbl_picker_monitor.value = ""
            lbl_cantidades_monitor.value = "0 / 0 un."
            lbl_porcentaje_monitor.value = "0%"
            progreso_monitor.value = 0.0
            lista_items_monitor.controls.clear()
            interfaz.page.update()
            return

        plan = interfaz.order_store.obtener_plan_mercado_full(target_id)
        if not plan:
            return

        porc = float(plan.get("porcentaje", 0.0))
        tot = int(plan.get("articulos_totales", 0))
        pick = int(plan.get("articulos_pickeados", 0))
        est = str(plan.get("estado", "")).upper()
        pck = plan.get("picker_asignado") or "Sin asignar"

        color_est = ft.Colors.AMBER_400 if est == "EN_PROCESO" else (ft.Colors.GREEN_400 if est == "COMPLETADO" else ft.Colors.BLUE_400)
        lbl_estado_monitor.value = f"Estado: {est}"
        lbl_estado_monitor.color = color_est
        lbl_picker_monitor.value = f"👤 Picker asignado: {pck}"
        lbl_cantidades_monitor.value = f"{pick} / {tot} unidades preparadas"
        lbl_porcentaje_monitor.value = f"{porc:.1f}%"
        progreso_monitor.value = min(1.0, max(0.0, porc / 100.0))

        lista_items_monitor.controls.clear()
        items = interfaz.order_store.obtener_items_plan_full(target_id)
        for it in items:
            it_cod = it["codigo"]
            it_desc = it["descripcion"]
            it_sol = it["cantidad_solicitada"]
            it_pick = it["cantidad_pickeada"]
            it_comp = bool(it["completado"])

            color_badge = ft.Colors.GREEN_400 if it_comp else (ft.Colors.AMBER_400 if it_pick > 0 else ft.Colors.GREY_400)
            txt_badge = "✔ COMPLETO" if it_comp else f"⏳ {it_pick}/{it_sol} un."

            lista_items_monitor.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if it_comp else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                color=color_badge,
                                size=16,
                            ),
                            ft.Text(f"[{it_cod}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                            ft.Text(it_desc, size=11, expand=True, no_wrap=True),
                            ft.Container(
                                content=ft.Text(txt_badge, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                bgcolor=color_badge,
                                border_radius=4,
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        interfaz.page.update()

    def al_cambiar_plan_dropdown(_e: ft.Event) -> None:
        if selector_plan.value:
            plan_activo_id[0] = int(selector_plan.value)
            recargar_monitor(plan_activo_id[0])

    selector_plan.on_change = al_cambiar_plan_dropdown

    if plan_activo_id[0]:
        recargar_monitor(plan_activo_id[0])

    # -------------------------------------------------------------
    # CAMBIO DE TABS Y CONTENEDOR PRINCIPAL
    # -------------------------------------------------------------
    panel_nuevo = ft.Column(
        [
            ft.Text(
                "Carga el archivo Excel de Mercado Full con los SKU y cantidades a preparar por el picker.",
                size=12,
                color=interfaz.secundario,
            ),
            ft.Row([selector_archivo, ft.IconButton(ft.Icons.UPLOAD_FILE, tooltip="Subir archivo desde PC", on_click=examinar_pc)]),
            txt_nombre_envio,
            lbl_resumen_nuevo,
            lista_items_nuevo,
            ft.Row([btn_publicar], alignment=ft.MainAxisAlignment.END),
        ],
        spacing=8,
    )

    panel_monitor = ft.Column(
        [
            ft.Row(
                [
                    selector_plan,
                    ft.IconButton(ft.Icons.REFRESH, tooltip="Actualizar progreso en tiempo real", on_click=lambda _: recargar_monitor()),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Container(
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column([lbl_estado_monitor, lbl_picker_monitor], spacing=2),
                                ft.Column([lbl_cantidades_monitor, lbl_porcentaje_monitor], horizontal_alignment=ft.CrossAxisAlignment.END, spacing=2),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        progreso_monitor,
                    ],
                    spacing=6,
                ),
            ),
            ft.Text("Detalle por Producto en el Envío:", size=12, weight=ft.FontWeight.BOLD),
            lista_items_monitor,
        ],
        spacing=8,
    )

    contenedor_vistas = ft.AnimatedSwitcher(
        content=panel_monitor if tab_actual[0] == "monitor" else panel_nuevo,
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=200,
    )

    btn_tab_nuevo = ft.Button(
        "Cargar Nuevo Envío",
        icon=ft.Icons.ADD_TASK,
        bgcolor=ROJO if tab_actual[0] == "nuevo" else (ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200),
        color=ft.Colors.WHITE if tab_actual[0] == "nuevo" else interfaz.texto,
    )

    btn_tab_monitor = ft.Button(
        "Monitoreo en Tiempo Real",
        icon=ft.Icons.INSIGHTS,
        bgcolor=ROJO if tab_actual[0] == "monitor" else (ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200),
        color=ft.Colors.WHITE if tab_actual[0] == "monitor" else interfaz.texto,
    )

    def cambiar_tab(nueva_tab: str) -> None:
        tab_actual[0] = nueva_tab
        btn_tab_nuevo.bgcolor = ROJO if nueva_tab == "nuevo" else (ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200)
        btn_tab_nuevo.color = ft.Colors.WHITE if nueva_tab == "nuevo" else interfaz.texto
        btn_tab_monitor.bgcolor = ROJO if nueva_tab == "monitor" else (ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200)
        btn_tab_monitor.color = ft.Colors.WHITE if nueva_tab == "monitor" else interfaz.texto

        if nueva_tab == "nuevo":
            contenedor_vistas.content = panel_nuevo
        else:
            # Actualizar dropdown de planes
            nuevos_planes = interfaz.order_store.listar_planes_mercado_full()
            selector_plan.options = [
                ft.dropdown.Option(
                    key=str(p["id"]),
                    text=f"#{p['id']} - {p['nombre_envio']} ({p['porcentaje']}%) [{p['estado'].upper()}]",
                )
                for p in nuevos_planes
            ]
            if nuevos_planes and not selector_plan.value:
                selector_plan.value = str(nuevos_planes[0]["id"])
                plan_activo_id[0] = nuevos_planes[0]["id"]
            recargar_monitor()
            contenedor_vistas.content = panel_monitor
        interfaz.page.update()

    btn_tab_nuevo.on_click = lambda _: cambiar_tab("nuevo")
    btn_tab_monitor.on_click = lambda _: cambiar_tab("monitor")

    async def al_confirmar_publicacion(_e: ft.Event) -> None:
        if not items_parseados or not archivo_seleccionado[0]:
            interfaz.notificar("Debe seleccionar una planilla Excel válida con artículos.")
            return

        nombre_envio = txt_nombre_envio.value.strip() or f"Envío Full - {archivo_seleccionado[0].stem}"
        usuario_nom = (
            interfaz.usuario_actual.nombre_identificador
            if getattr(interfaz, "usuario_actual", None)
            else "Administrador"
        )

        try:
            plan_id = interfaz.order_store.crear_plan_mercado_full(
                nombre_envio=nombre_envio,
                archivo_excel=archivo_seleccionado[0].name,
                creado_por=usuario_nom,
                items=items_parseados,
            )
        except Exception as exc:
            interfaz.notificar(f"Error al crear el plan: {exc}")
            return

        total_unidades = sum(cant for _, _, cant in items_parseados)

        # Notificar a todas las sesiones LAN (Pickers y operadores)
        interfaz.sincronizar_sesiones(
            aviso_colaborativo=f"🔔 Nuevo envío Mercado Full cargado por {usuario_nom}: '{nombre_envio}' ({total_unidades} un.) - Listo para preparar"
        )

        interfaz.notificar(f"Plan #{plan_id} '{nombre_envio}' creado y notificado al equipo de pickers.")
        plan_activo_id[0] = plan_id
        selector_plan.value = str(plan_id)
        cambiar_tab("monitor")

    btn_publicar.on_click = al_confirmar_publicacion

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.LOCAL_SHIPPING, color=ROJO, size=24),
                ft.Text("Planificación y Monitoreo de Mercado Full", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=interfaz.ancho_adaptable(680) if hasattr(interfaz, "ancho_adaptable") else 680,
            content=ft.Column(
                [
                    ft.Row([btn_tab_nuevo, btn_tab_monitor], spacing=8),
                    ft.Divider(height=1),
                    contenedor_vistas,
                ],
                spacing=10,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Cerrar", on_click=lambda _: interfaz.page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
    interfaz.page.update()
