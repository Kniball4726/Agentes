"""Diálogo para la planificación, carga de remito de fábrica y monitoreo en tiempo real del control del picker."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any
import flet as ft

from ..theme import ROJO
from ...inventory import StockManager as _DefaultStockManager
from ...parsers.factory_parser import parsear_archivo_fabrica


def _get_stock_manager():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def mostrar_planificar_ingreso_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para que el Administrador cargue el remito de fábrica y monitoree el control en tiempo real."""
    if not interfaz.exigir_roles("administrador", "master", "operador"):
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    carpeta_fabrica = getattr(interfaz.menu, "carpeta_fabrica", None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / "Fabrica"
    )
    carpeta_fabrica.mkdir(parents=True, exist_ok=True)

    archivos_pendientes: list[Path] = []
    for ext in ("*.xlsx", "*.xls", "*.pdf"):
        archivos_pendientes.extend(carpeta_fabrica.glob(ext))
    archivos_pendientes.sort()

    tab_actual = ["monitor" if interfaz.order_store.obtener_plan_activo_ingreso_fabrica() else "nuevo"]

    # -------------------------------------------------------------
    # TAB 1: NUEVO INGRESO (CARGA ARCHIVO)
    # -------------------------------------------------------------
    archivo_seleccionado: list[Path | None] = [archivos_pendientes[0] if archivos_pendientes else None]
    items_parseados: list[tuple[str, str, int]] = []
    totales_dict: dict[str, int] = {}

    txt_nombre_remito = ft.TextField(
        label="Nombre / Número de Remito de Fábrica",
        value=f"Remito Fábrica - {datetime.now().strftime('%d/%m/%Y')}",
        dense=True,
        expand=True,
    )

    lista_items_nuevo = ft.ListView(expand=True, spacing=4, height=220)
    lbl_resumen_nuevo = ft.Text(
        "Seleccione un archivo de fábrica (.xlsx, .xls o .pdf) para previsualizar.",
        size=12,
        color=interfaz.secundario,
    )

    selector_archivo = ft.Dropdown(
        label="Comprobante / Remito de Fábrica",
        options=[ft.dropdown.Option(arch.name) for arch in archivos_pendientes],
        value=archivos_pendientes[0].name if archivos_pendientes else None,
        dense=True,
        expand=True,
    )

    def cargar_datos_archivo(arch: Path) -> None:
        items_parseados.clear()
        totales_dict.clear()
        lista_items_nuevo.controls.clear()

        try:
            totales, detalle = parsear_archivo_fabrica(arch)
        except Exception as e:
            lbl_resumen_nuevo.value = f"Error al procesar {arch.name}: {e}"
            lbl_resumen_nuevo.color = ft.Colors.RED_400
            interfaz.page.update()
            return

        if not totales:
            lbl_resumen_nuevo.value = f"El archivo {arch.name} no contiene productos o cantidades reconocidas."
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
        lbl_resumen_nuevo.value = f"✔ {len(totales)} productos esperados ({total_u} unidades totales)."
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
                            ft.Text(f"{cant} un.", weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400, size=11, width=60),
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
                cargar_datos_archivo(a)
                txt_nombre_remito.value = f"Remito Fábrica - {a.stem}"
                break

    selector_archivo.on_change = al_cambiar_dropdown

    if archivo_seleccionado[0]:
        cargar_datos_archivo(archivo_seleccionado[0])

    def al_subir_archivo(guardados: list[Path]) -> None:
        nonlocal archivos_pendientes
        for g in guardados:
            if g not in archivos_pendientes:
                archivos_pendientes.append(g)
        selector_archivo.options = [ft.dropdown.Option(a.name) for a in archivos_pendientes]
        ultimo = guardados[-1]
        archivo_seleccionado[0] = ultimo
        selector_archivo.value = ultimo.name
        txt_nombre_remito.value = f"Remito Fábrica - {ultimo.stem}"
        cargar_datos_archivo(ultimo)

    async def examinar_pc(_e: ft.Event) -> None:
        await interfaz.subir_archivos_desde_pc(
            carpeta_destino=carpeta_fabrica,
            extensiones=["xlsx", "xls", "pdf"],
            titulo="Seleccionar comprobante / remito de fábrica",
            al_terminar=al_subir_archivo,
        )

    btn_publicar = ft.Button(
        "🚀 Crear Ingreso y Notificar al Picker",
        icon=ft.Icons.SEND,
        bgcolor=ft.Colors.GREEN_700,
        color=ft.Colors.WHITE,
    )

    # -------------------------------------------------------------
    # TAB 2: MONITOR EN TIEMPO REAL
    # -------------------------------------------------------------
    planes_disponibles = interfaz.order_store.listar_planes_ingreso_fabrica()
    plan_activo_id: list[int | None] = [planes_disponibles[0]["id"] if planes_disponibles else None]

    selector_plan = ft.Dropdown(
        label="Seleccionar Remito de Fábrica",
        options=[
            ft.dropdown.Option(
                key=str(p["id"]),
                text=f"#{p['id']} - {p['nombre_remito']} ({p['porcentaje']}%) [{p['estado'].upper()}]",
            )
            for p in planes_disponibles
        ],
        value=str(plan_activo_id[0]) if plan_activo_id[0] else None,
        dense=True,
        expand=True,
    )

    lbl_estado_monitor = ft.Text("Estado: -", size=12, weight=ft.FontWeight.BOLD)
    lbl_picker_monitor = ft.Text("Picker / Operador: -", size=12)
    lbl_cantidades_monitor = ft.Text("0 / 0 un. controladas", size=14, weight=ft.FontWeight.BOLD)
    lbl_porcentaje_monitor = ft.Text("0.0%", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    progreso_monitor = ft.ProgressBar(value=0.0, color=ft.Colors.GREEN_600, bgcolor=ft.Colors.GREY_300, height=10)

    lista_items_monitor = ft.ListView(expand=True, spacing=4, height=220)

    def recargar_monitor(pid: int | None = None) -> None:
        target_id = pid or plan_activo_id[0]
        if not target_id:
            lbl_estado_monitor.value = "Sin remitos registrados."
            lbl_picker_monitor.value = ""
            lbl_cantidades_monitor.value = "0 / 0 un. controladas"
            lbl_porcentaje_monitor.value = "0%"
            progreso_monitor.value = 0.0
            lista_items_monitor.controls.clear()
            interfaz.page.update()
            return

        plan = interfaz.order_store.obtener_plan_ingreso_fabrica(target_id)
        if not plan:
            return

        porc = float(plan.get("porcentaje", 0.0))
        tot = int(plan.get("articulos_esperados", 0))
        ctrl = int(plan.get("articulos_controlados", 0))
        ingr = int(plan.get("articulos_ingresados", 0))
        est = str(plan.get("estado", "")).upper()
        pck = plan.get("picker_asignado") or "Sin asignar"

        color_est = ft.Colors.AMBER_400 if est == "EN_PROCESO" else (ft.Colors.GREEN_400 if est == "COMPLETADO" else ft.Colors.BLUE_400)
        lbl_estado_monitor.value = f"Estado: {est}"
        lbl_estado_monitor.color = color_est
        lbl_picker_monitor.value = f"👤 Controlando: {pck}"
        txt_cantidades = f"{ctrl} / {tot} unidades verificadas"
        if ingr > 0:
            txt_cantidades += f" ({ingr} un. en stock)"
        lbl_cantidades_monitor.value = txt_cantidades
        lbl_porcentaje_monitor.value = f"{porc:.1f}%"
        progreso_monitor.value = min(1.0, max(0.0, porc / 100.0))

        lista_items_monitor.controls.clear()
        items = interfaz.order_store.obtener_items_plan_ingreso_fabrica(target_id)
        for it in items:
            it_cod = it["codigo"]
            it_desc = it["descripcion"]
            it_esp = it["cantidad_esperada"]
            it_ctrl = it["cantidad_controlada"]
            it_ingr = it.get("cantidad_ingresada", 0)
            it_comp = bool(it["completado"])

            color_badge = ft.Colors.GREEN_400 if it_comp else (ft.Colors.AMBER_400 if it_ctrl > 0 else ft.Colors.GREY_400)
            if it_comp:
                txt_badge = f"✔ CONTROLADO ({it_ingr} en stock)" if it_ingr > 0 else "✔ CONTROLADO"
            elif it_ctrl > 0:
                txt_badge = f"⏳ {it_ctrl}/{it_esp} un. ({it_ingr} en stock)" if it_ingr > 0 else f"⏳ {it_ctrl}/{it_esp} un."
            else:
                txt_badge = f"0/{it_esp} un."

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

    panel_nuevo = ft.Column(
        [
            ft.Text(
                "Carga el remito o planilla de fábrica para habilitar el control físico por escaneo del picker.",
                size=12,
                color=interfaz.secundario,
            ),
            ft.Row([selector_archivo, ft.IconButton(ft.Icons.UPLOAD_FILE, tooltip="Subir archivo desde PC", on_click=examinar_pc)]),
            txt_nombre_remito,
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
            ft.Text("Detalle por Producto en el Remito:", size=12, weight=ft.FontWeight.BOLD),
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
        "Cargar Nuevo Remito",
        icon=ft.Icons.ADD_TASK,
        bgcolor=ft.Colors.GREEN_700 if tab_actual[0] == "nuevo" else (ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200),
        color=ft.Colors.WHITE if tab_actual[0] == "nuevo" else interfaz.texto,
    )

    btn_tab_monitor = ft.Button(
        "Monitoreo en Tiempo Real",
        icon=ft.Icons.INSIGHTS,
        bgcolor=ft.Colors.GREEN_700 if tab_actual[0] == "monitor" else (ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200),
        color=ft.Colors.WHITE if tab_actual[0] == "monitor" else interfaz.texto,
    )

    def cambiar_tab(nueva_tab: str) -> None:
        tab_actual[0] = nueva_tab
        btn_tab_nuevo.bgcolor = ft.Colors.GREEN_700 if nueva_tab == "nuevo" else (ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200)
        btn_tab_nuevo.color = ft.Colors.WHITE if nueva_tab == "nuevo" else interfaz.texto
        btn_tab_monitor.bgcolor = ft.Colors.GREEN_700 if nueva_tab == "monitor" else (ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200)
        btn_tab_monitor.color = ft.Colors.WHITE if nueva_tab == "monitor" else interfaz.texto

        if nueva_tab == "nuevo":
            contenedor_vistas.content = panel_nuevo
        else:
            nuevos_planes = interfaz.order_store.listar_planes_ingreso_fabrica()
            selector_plan.options = [
                ft.dropdown.Option(
                    key=str(p["id"]),
                    text=f"#{p['id']} - {p['nombre_remito']} ({p['porcentaje']}%) [{p['estado'].upper()}]",
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
            interfaz.notificar("Debe seleccionar una planilla o remito válido con artículos.")
            return

        nombre_remito = txt_nombre_remito.value.strip() or f"Remito Fábrica - {archivo_seleccionado[0].stem}"
        usuario_nom = (
            interfaz.usuario_actual.nombre_identificador
            if getattr(interfaz, "usuario_actual", None)
            else "Administrador"
        )

        try:
            plan_id = interfaz.order_store.crear_plan_ingreso_fabrica(
                nombre_remito=nombre_remito,
                archivo_remito=archivo_seleccionado[0].name,
                creado_por=usuario_nom,
                items=items_parseados,
            )
        except Exception as exc:
            interfaz.notificar(f"Error al crear el remito de fábrica: {exc}")
            return

        total_unidades = sum(cant for _, _, cant in items_parseados)

        # Notificar a todas las terminales LAN
        interfaz.sincronizar_sesiones(
            aviso_colaborativo=f"🔔 Nuevo remito de fábrica cargado por {usuario_nom}: '{nombre_remito}' ({total_unidades} un. esperadas) - ¡Listo para control!"
        )

        interfaz.notificar(f"Remito #{plan_id} '{nombre_remito}' creado y notificado al equipo de control.")
        plan_activo_id[0] = plan_id
        selector_plan.value = str(plan_id)
        cambiar_tab("monitor")

    btn_publicar.on_click = al_confirmar_publicacion

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.INVENTORY_2, color=ft.Colors.GREEN_500, size=24),
                ft.Text("Planificación y Monitoreo de Ingreso de Fábrica", size=16, weight=ft.FontWeight.BOLD),
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
