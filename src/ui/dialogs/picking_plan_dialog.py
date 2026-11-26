"""Constructor parametrizado y modular para diálogos de planificación y monitoreo de picking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import flet as ft

from .picking_plan_shared import (
    construir_fila_monitor_plan,
    construir_fila_preview_plan,
    resolver_stock_manager_ui,
)


@dataclass(frozen=True)
class PlanDialogConfig:
    """Configuración declarativa para los diálogos de planificación y monitoreo."""

    titulo_dialogo: str
    icono_dialogo: Any
    color_acento: Any
    color_icono_dialogo: Any
    color_preview_cantidad: Any
    color_porcentaje: Any
    color_progreso: Any
    carpeta_attr: str
    subcarpeta_default: str
    extensiones: tuple[str, ...]
    prefijo_nombre: str
    label_nombre_plan: str
    label_selector_archivo: str
    titulo_subida_pc: str
    descripcion_nuevo: str
    texto_tab_nuevo: str
    texto_boton_publicar: str
    msg_error_archivo_invalido: str
    msg_sin_columnas: str
    msg_resumen_preview: Callable[[int, int], str]
    label_selector_plan: str
    label_picker_prefix: str
    texto_cantidades_inicial: str
    texto_sin_planes: str
    titulo_detalle_monitor: str
    msg_aviso_colaborativo: Callable[[str, str, int], str]
    msg_notificacion_creado: Callable[[int, str], str]
    msg_error_crear: Callable[[Exception], str]
    plan_nombre_key: str
    obtener_plan_activo_fn: Callable[[Any], dict[str, Any] | None]
    listar_planes_fn: Callable[[Any], list[dict[str, Any]]]
    obtener_plan_fn: Callable[[Any, int], dict[str, Any] | None]
    obtener_items_plan_fn: Callable[[Any, int], list[dict[str, Any]]]
    crear_plan_fn: Callable[[Any, str, str, str, list[tuple[str, str, int]]], int]
    formatear_cantidades_fn: Callable[[dict[str, Any]], str]
    formatear_item_monitor_fn: Callable[[dict[str, Any]], tuple[str, bool, bool]]


def _resolver_carpeta_plan(interfaz: Any, cfg: PlanDialogConfig) -> Path:
    carpeta = getattr(interfaz.menu, cfg.carpeta_attr, None) or (
        getattr(interfaz.menu, "base_dir", Path(".")) / "Descuentos" / cfg.subcarpeta_default
    )
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _listar_archivos_carpeta(carpeta: Path, extensiones: tuple[str, ...]) -> list[Path]:
    archivos: list[Path] = []
    for ext in extensiones:
        archivos.extend(carpeta.glob(f"*.{ext}"))
    archivos.sort()
    return archivos


def _cargar_preview_plan(
    *,
    arch: Path,
    parser_fn: Callable[[Path], tuple[dict[str, int], Any]],
    stock_manager_factory: Callable[[], type],
    interfaz: Any,
    cfg: PlanDialogConfig,
    es_oscuro: bool,
    items_parseados: list[tuple[str, str, int]],
    totales_dict: dict[str, int],
    lista_items_nuevo: ft.ListView,
    lbl_resumen_nuevo: ft.Text,
) -> None:
    items_parseados.clear()
    totales_dict.clear()
    lista_items_nuevo.controls.clear()

    try:
        totales, _detalle = parser_fn(arch)
    except Exception as exc:
        lbl_resumen_nuevo.value = f"Error al procesar {arch.name}: {exc}"
        lbl_resumen_nuevo.color = ft.Colors.RED_400
        interfaz.page.update()
        return

    if not totales:
        lbl_resumen_nuevo.value = cfg.msg_sin_columnas.format(archivo=arch.name)
        lbl_resumen_nuevo.color = ft.Colors.AMBER_400
        interfaz.page.update()
        return

    totales_dict.update(totales)
    sm = stock_manager_factory()(interfaz.menu.ruta_excel_base)
    catalogo = getattr(sm, "catalogo", {})
    for cod, cant in totales.items():
        nom = catalogo[cod][1] if cod in catalogo else "Producto en catálogo"
        items_parseados.append((cod, nom, cant))

    total_u = sum(totales.values())
    lbl_resumen_nuevo.value = cfg.msg_resumen_preview(len(totales), total_u)
    lbl_resumen_nuevo.color = ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_700

    for cod, desc, cant in items_parseados:
        lista_items_nuevo.controls.append(
            construir_fila_preview_plan(cod, desc, cant, cfg.color_preview_cantidad, es_oscuro)
        )
    interfaz.page.update()


def _construir_opciones_planes(
    planes: list[dict[str, Any]],
    nombre_key: str,
) -> list[ft.dropdown.Option]:
    return [
        ft.dropdown.Option(
            key=str(p["id"]),
            text=f"#{p['id']} - {p[nombre_key]} ({p['porcentaje']}%) [{p['estado'].upper()}]",
        )
        for p in planes
    ]


def mostrar_dialogo_planificacion(
    interfaz: Any,
    cfg: PlanDialogConfig,
    parser_fn: Callable[[Path], tuple[dict[str, int], Any]],
    stock_manager_factory: Callable[[], type] = resolver_stock_manager_ui,
) -> None:
    """Construye y muestra el diálogo dual de carga de planilla y monitoreo en tiempo real."""
    if not interfaz.exigir_roles("administrador", "master", "operador"):
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    carpeta = _resolver_carpeta_plan(interfaz, cfg)
    archivos_pendientes = _listar_archivos_carpeta(carpeta, cfg.extensiones)
    tab_actual = ["monitor" if cfg.obtener_plan_activo_fn(interfaz.order_store) else "nuevo"]

    archivo_seleccionado: list[Path | None] = [archivos_pendientes[0] if archivos_pendientes else None]
    items_parseados: list[tuple[str, str, int]] = []
    totales_dict: dict[str, int] = {}

    txt_nombre = ft.TextField(
        label=cfg.label_nombre_plan,
        value=f"{cfg.prefijo_nombre} - {datetime.now().strftime('%d/%m/%Y')}",
        dense=True,
        expand=True,
    )
    lista_items_nuevo = ft.ListView(expand=True, spacing=4, height=220)
    lbl_resumen_nuevo = ft.Text(
        "Seleccione una planilla para previsualizar los artículos.",
        size=12,
        color=interfaz.secundario,
    )
    selector_archivo = ft.Dropdown(
        label=cfg.label_selector_archivo,
        options=[ft.dropdown.Option(arch.name) for arch in archivos_pendientes],
        value=archivos_pendientes[0].name if archivos_pendientes else None,
        dense=True,
        expand=True,
    )

    def _cargar_preview(arch: Path) -> None:
        _cargar_preview_plan(
            arch=arch,
            parser_fn=parser_fn,
            stock_manager_factory=stock_manager_factory,
            interfaz=interfaz,
            cfg=cfg,
            es_oscuro=es_oscuro,
            items_parseados=items_parseados,
            totales_dict=totales_dict,
            lista_items_nuevo=lista_items_nuevo,
            lbl_resumen_nuevo=lbl_resumen_nuevo,
        )

    def al_cambiar_dropdown(_e: ft.Event) -> None:
        nom = selector_archivo.value
        for arch in archivos_pendientes:
            if arch.name == nom:
                archivo_seleccionado[0] = arch
                _cargar_preview(arch)
                txt_nombre.value = f"{cfg.prefijo_nombre} - {arch.stem}"
                break

    selector_archivo.on_select = al_cambiar_dropdown
    if archivo_seleccionado[0]:
        _cargar_preview(archivo_seleccionado[0])

    def al_subir_archivo(guardados: list[Path]) -> None:
        nonlocal archivos_pendientes
        for guardado in guardados:
            if guardado not in archivos_pendientes:
                archivos_pendientes.append(guardado)
        selector_archivo.options = [ft.dropdown.Option(a.name) for a in archivos_pendientes]
        ultimo = guardados[-1]
        archivo_seleccionado[0] = ultimo
        selector_archivo.value = ultimo.name
        txt_nombre.value = f"{cfg.prefijo_nombre} - {ultimo.stem}"
        _cargar_preview(ultimo)

    async def examinar_pc(_e: ft.Event) -> None:
        await interfaz.subir_archivos_desde_pc(
            carpeta_destino=carpeta,
            extensiones=list(cfg.extensiones),
            titulo=cfg.titulo_subida_pc,
            al_terminar=al_subir_archivo,
        )

    btn_publicar = ft.Button(
        cfg.texto_boton_publicar,
        icon=ft.Icons.SEND,
        bgcolor=cfg.color_acento,
        color=ft.Colors.WHITE,
    )

    planes_disponibles = cfg.listar_planes_fn(interfaz.order_store)
    plan_activo_id: list[int | None] = [planes_disponibles[0]["id"] if planes_disponibles else None]
    selector_plan = ft.Dropdown(
        label=cfg.label_selector_plan,
        options=_construir_opciones_planes(planes_disponibles, cfg.plan_nombre_key),
        value=str(plan_activo_id[0]) if plan_activo_id[0] else None,
        dense=True,
        expand=True,
    )

    lbl_estado_monitor = ft.Text("Estado: -", size=12, weight=ft.FontWeight.BOLD)
    lbl_picker_monitor = ft.Text(f"{cfg.label_picker_prefix}: -", size=12)
    lbl_cantidades_monitor = ft.Text(cfg.texto_cantidades_inicial, size=14, weight=ft.FontWeight.BOLD)
    lbl_porcentaje_monitor = ft.Text("0.0%", size=20, weight=ft.FontWeight.BOLD, color=cfg.color_porcentaje)
    progreso_monitor = ft.ProgressBar(value=0.0, color=cfg.color_progreso, bgcolor=ft.Colors.GREY_300, height=10)
    lista_items_monitor = ft.ListView(expand=True, spacing=4, height=220)

    def recargar_monitor(pid: int | None = None) -> None:
        target_id = pid or plan_activo_id[0]
        if not target_id:
            lbl_estado_monitor.value = cfg.texto_sin_planes
            lbl_picker_monitor.value = ""
            lbl_cantidades_monitor.value = cfg.texto_cantidades_inicial
            lbl_porcentaje_monitor.value = "0%"
            progreso_monitor.value = 0.0
            lista_items_monitor.controls.clear()
            interfaz.page.update()
            return

        plan = cfg.obtener_plan_fn(interfaz.order_store, target_id)
        if not plan:
            return

        porc = float(plan.get("porcentaje", 0.0))
        est = str(plan.get("estado", "")).upper()
        pck = plan.get("picker_asignado") or "Sin asignar"
        color_est = (
            ft.Colors.AMBER_400
            if est == "EN_PROCESO"
            else (ft.Colors.GREEN_400 if est == "COMPLETADO" else ft.Colors.BLUE_400)
        )
        lbl_estado_monitor.value = f"Estado: {est}"
        lbl_estado_monitor.color = color_est
        lbl_picker_monitor.value = f"👤 {cfg.label_picker_prefix}: {pck}"
        lbl_cantidades_monitor.value = cfg.formatear_cantidades_fn(plan)
        lbl_porcentaje_monitor.value = f"{porc:.1f}%"
        progreso_monitor.value = min(1.0, max(0.0, porc / 100.0))

        lista_items_monitor.controls.clear()
        for it in cfg.obtener_items_plan_fn(interfaz.order_store, target_id):
            txt_badge, completado, en_progreso = cfg.formatear_item_monitor_fn(it)
            lista_items_monitor.controls.append(
                construir_fila_monitor_plan(
                    codigo=it["codigo"],
                    descripcion=it["descripcion"],
                    txt_badge=txt_badge,
                    completado=completado,
                    en_progreso=en_progreso,
                    es_oscuro=es_oscuro,
                )
            )
        interfaz.page.update()

    def al_cambiar_plan_dropdown(_e: ft.Event) -> None:
        if selector_plan.value:
            plan_activo_id[0] = int(selector_plan.value)
            recargar_monitor(plan_activo_id[0])

    selector_plan.on_select = al_cambiar_plan_dropdown
    if plan_activo_id[0]:
        recargar_monitor(plan_activo_id[0])

    panel_nuevo = ft.Column(
        [
            ft.Text(cfg.descripcion_nuevo, size=12, color=interfaz.secundario),
            ft.Row([selector_archivo, ft.IconButton(ft.Icons.UPLOAD_FILE, tooltip="Subir archivo desde PC", on_click=examinar_pc)]),
            txt_nombre,
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
            ft.Text(cfg.titulo_detalle_monitor, size=12, weight=ft.FontWeight.BOLD),
            lista_items_monitor,
        ],
        spacing=8,
    )

    contenedor_vistas = ft.AnimatedSwitcher(
        content=panel_monitor if tab_actual[0] == "monitor" else panel_nuevo,
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=200,
    )

    bg_inactivo = ft.Colors.WHITE_12 if es_oscuro else ft.Colors.GREY_200
    btn_tab_nuevo = ft.Button(
        cfg.texto_tab_nuevo,
        icon=ft.Icons.ADD_TASK,
        bgcolor=cfg.color_acento if tab_actual[0] == "nuevo" else bg_inactivo,
        color=ft.Colors.WHITE if tab_actual[0] == "nuevo" else interfaz.texto,
    )
    btn_tab_monitor = ft.Button(
        "Monitoreo en Tiempo Real",
        icon=ft.Icons.INSIGHTS,
        bgcolor=cfg.color_acento if tab_actual[0] == "monitor" else bg_inactivo,
        color=ft.Colors.WHITE if tab_actual[0] == "monitor" else interfaz.texto,
    )

    def cambiar_tab(nueva_tab: str) -> None:
        tab_actual[0] = nueva_tab
        btn_tab_nuevo.bgcolor = cfg.color_acento if nueva_tab == "nuevo" else bg_inactivo
        btn_tab_nuevo.color = ft.Colors.WHITE if nueva_tab == "nuevo" else interfaz.texto
        btn_tab_monitor.bgcolor = cfg.color_acento if nueva_tab == "monitor" else bg_inactivo
        btn_tab_monitor.color = ft.Colors.WHITE if nueva_tab == "monitor" else interfaz.texto

        if nueva_tab == "nuevo":
            contenedor_vistas.content = panel_nuevo
        else:
            nuevos_planes = cfg.listar_planes_fn(interfaz.order_store)
            selector_plan.options = _construir_opciones_planes(nuevos_planes, cfg.plan_nombre_key)
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
            interfaz.notificar(cfg.msg_error_archivo_invalido)
            return

        nombre_plan = txt_nombre.value.strip() or f"{cfg.prefijo_nombre} - {archivo_seleccionado[0].stem}"
        usuario_nom = (
            interfaz.usuario_actual.nombre_identificador
            if getattr(interfaz, "usuario_actual", None)
            else "Administrador"
        )

        try:
            plan_id = cfg.crear_plan_fn(
                interfaz.order_store,
                nombre_plan,
                archivo_seleccionado[0].name,
                usuario_nom,
                items_parseados,
            )
        except Exception as exc:
            interfaz.notificar(cfg.msg_error_crear(exc))
            return

        total_unidades = sum(cant for _, _, cant in items_parseados)
        interfaz.sincronizar_sesiones(
            aviso_colaborativo=cfg.msg_aviso_colaborativo(usuario_nom, nombre_plan, total_unidades)
        )
        interfaz.notificar(cfg.msg_notificacion_creado(plan_id, nombre_plan))
        plan_activo_id[0] = plan_id
        selector_plan.value = str(plan_id)
        cambiar_tab("monitor")

    btn_publicar.on_click = al_confirmar_publicacion

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(cfg.icono_dialogo, color=cfg.color_icono_dialogo, size=24),
                ft.Text(cfg.titulo_dialogo, size=16, weight=ft.FontWeight.BOLD),
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
        actions=[ft.TextButton("Cerrar", on_click=lambda _: interfaz.page.pop_dialog())],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    interfaz.page.show_dialog(dialogo)
    interfaz.page.update()
