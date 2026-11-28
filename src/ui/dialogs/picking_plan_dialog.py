"""Constructor parametrizado y modular para diálogos de planificación y monitoreo de picking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

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


class _PlanificacionPickingController:
    """Controlador del diálogo dual de carga de planilla y monitoreo en tiempo real."""

    def __init__(
        self,
        interfaz: Any,
        cfg: PlanDialogConfig,
        parser_fn: Callable[[Path], tuple[dict[str, int], Any]],
        stock_manager_factory: Callable[[], type],
    ) -> None:
        self.interfaz = interfaz
        self.cfg = cfg
        self.parser_fn = parser_fn
        self.stock_manager_factory = stock_manager_factory
        self.es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
        self.bg_inactivo = ft.Colors.WHITE_12 if self.es_oscuro else ft.Colors.GREY_200

        self.carpeta = _resolver_carpeta_plan(interfaz, cfg)
        self.archivos_pendientes = _listar_archivos_carpeta(self.carpeta, cfg.extensiones)
        self.tab_actual = "monitor" if cfg.obtener_plan_activo_fn(interfaz.order_store) else "nuevo"
        self.archivo_seleccionado: Path | None = (
            self.archivos_pendientes[0] if self.archivos_pendientes else None
        )
        self.items_parseados: list[tuple[str, str, int]] = []
        self.totales_dict: dict[str, int] = {}

        planes_disponibles = cfg.listar_planes_fn(interfaz.order_store)
        self.plan_activo_id: int | None = (
            planes_disponibles[0]["id"] if planes_disponibles else None
        )

        self._inicializar_controles_nuevo()
        self._inicializar_controles_monitor(planes_disponibles)
        self._inicializar_tabs()

        if self.archivo_seleccionado:
            self._cargar_preview(self.archivo_seleccionado)
        if self.plan_activo_id:
            self.recargar_monitor(self.plan_activo_id)

    def _inicializar_controles_nuevo(self) -> None:
        cfg = self.cfg
        self.txt_nombre = ft.TextField(
            label=cfg.label_nombre_plan,
            value=f"{cfg.prefijo_nombre} - {datetime.now().strftime('%d/%m/%Y')}",
            dense=True,
            expand=True,
        )
        self.lista_items_nuevo = ft.ListView(expand=True, spacing=4, height=220)
        self.lbl_resumen_nuevo = ft.Text(
            "Seleccione una planilla para previsualizar los artículos.",
            size=12,
            color=self.interfaz.secundario,
        )
        self.selector_archivo = ft.Dropdown(
            label=cfg.label_selector_archivo,
            options=[ft.dropdown.Option(arch.name) for arch in self.archivos_pendientes],
            value=self.archivos_pendientes[0].name if self.archivos_pendientes else None,
            dense=True,
            expand=True,
            on_select=self._al_cambiar_archivo,
        )
        self.btn_publicar = ft.Button(
            cfg.texto_boton_publicar,
            icon=ft.Icons.SEND,
            bgcolor=cfg.color_acento,
            color=ft.Colors.WHITE,
            on_click=self._al_confirmar_publicacion,
        )
        self.panel_nuevo = ft.Column(
            [
                ft.Text(cfg.descripcion_nuevo, size=12, color=self.interfaz.secundario),
                ft.Row(
                    [
                        self.selector_archivo,
                        ft.IconButton(
                            ft.Icons.UPLOAD_FILE,
                            tooltip="Subir archivo desde PC",
                            on_click=self._examinar_pc,
                        ),
                    ]
                ),
                self.txt_nombre,
                self.lbl_resumen_nuevo,
                self.lista_items_nuevo,
                ft.Row([self.btn_publicar], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=8,
        )

    def _inicializar_controles_monitor(self, planes_disponibles: list[dict[str, Any]]) -> None:
        cfg = self.cfg
        self.selector_plan = ft.Dropdown(
            label=cfg.label_selector_plan,
            options=_construir_opciones_planes(planes_disponibles, cfg.plan_nombre_key),
            value=str(self.plan_activo_id) if self.plan_activo_id else None,
            dense=True,
            expand=True,
            on_select=self._al_cambiar_plan,
        )
        self.lbl_estado_monitor = ft.Text("Estado: -", size=12, weight=ft.FontWeight.BOLD)
        self.lbl_picker_monitor = ft.Text(f"{cfg.label_picker_prefix}: -", size=12)
        self.lbl_cantidades_monitor = ft.Text(
            cfg.texto_cantidades_inicial,
            size=14,
            weight=ft.FontWeight.BOLD,
        )
        self.lbl_porcentaje_monitor = ft.Text(
            "0.0%",
            size=20,
            weight=ft.FontWeight.BOLD,
            color=cfg.color_porcentaje,
        )
        self.progreso_monitor = ft.ProgressBar(
            value=0.0,
            color=cfg.color_progreso,
            bgcolor=ft.Colors.GREY_300,
            height=10,
        )
        self.lista_items_monitor = ft.ListView(expand=True, spacing=4, height=220)
        self.panel_monitor = ft.Column(
            [
                ft.Row(
                    [
                        self.selector_plan,
                        ft.IconButton(
                            ft.Icons.REFRESH,
                            tooltip="Actualizar progreso en tiempo real",
                            on_click=lambda _: self.recargar_monitor(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    padding=10,
                    border_radius=8,
                    bgcolor=ft.Colors.WHITE_10 if self.es_oscuro else ft.Colors.GREY_100,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Column(
                                        [self.lbl_estado_monitor, self.lbl_picker_monitor],
                                        spacing=2,
                                    ),
                                    ft.Column(
                                        [self.lbl_cantidades_monitor, self.lbl_porcentaje_monitor],
                                        horizontal_alignment=ft.CrossAxisAlignment.END,
                                        spacing=2,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            self.progreso_monitor,
                        ],
                        spacing=6,
                    ),
                ),
                ft.Text(cfg.titulo_detalle_monitor, size=12, weight=ft.FontWeight.BOLD),
                self.lista_items_monitor,
            ],
            spacing=8,
        )

    def _inicializar_tabs(self) -> None:
        cfg = self.cfg
        self.contenedor_vistas = ft.AnimatedSwitcher(
            content=self.panel_monitor if self.tab_actual == "monitor" else self.panel_nuevo,
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=200,
        )
        self.btn_tab_nuevo = ft.Button(
            cfg.texto_tab_nuevo,
            icon=ft.Icons.ADD_TASK,
            bgcolor=cfg.color_acento if self.tab_actual == "nuevo" else self.bg_inactivo,
            color=ft.Colors.WHITE if self.tab_actual == "nuevo" else self.interfaz.texto,
            on_click=lambda _: self.cambiar_tab("nuevo"),
        )
        self.btn_tab_monitor = ft.Button(
            "Monitoreo en Tiempo Real",
            icon=ft.Icons.INSIGHTS,
            bgcolor=cfg.color_acento if self.tab_actual == "monitor" else self.bg_inactivo,
            color=ft.Colors.WHITE if self.tab_actual == "monitor" else self.interfaz.texto,
            on_click=lambda _: self.cambiar_tab("monitor"),
        )

    def _cargar_preview(self, arch: Path) -> None:
        _cargar_preview_plan(
            arch=arch,
            parser_fn=self.parser_fn,
            stock_manager_factory=self.stock_manager_factory,
            interfaz=self.interfaz,
            cfg=self.cfg,
            es_oscuro=self.es_oscuro,
            items_parseados=self.items_parseados,
            totales_dict=self.totales_dict,
            lista_items_nuevo=self.lista_items_nuevo,
            lbl_resumen_nuevo=self.lbl_resumen_nuevo,
        )

    def _al_cambiar_archivo(self, _e: ft.Event) -> None:
        nom = self.selector_archivo.value
        for arch in self.archivos_pendientes:
            if arch.name == nom:
                self.archivo_seleccionado = arch
                self._cargar_preview(arch)
                self.txt_nombre.value = f"{self.cfg.prefijo_nombre} - {arch.stem}"
                break

    def _al_subir_archivo(self, guardados: list[Path]) -> None:
        for guardado in guardados:
            if guardado not in self.archivos_pendientes:
                self.archivos_pendientes.append(guardado)
        self.selector_archivo.options = [
            ft.dropdown.Option(a.name) for a in self.archivos_pendientes
        ]
        ultimo = guardados[-1]
        self.archivo_seleccionado = ultimo
        self.selector_archivo.value = ultimo.name
        self.txt_nombre.value = f"{self.cfg.prefijo_nombre} - {ultimo.stem}"
        self._cargar_preview(ultimo)

    async def _examinar_pc(self, _e: ft.Event) -> None:
        await self.interfaz.subir_archivos_desde_pc(
            carpeta_destino=self.carpeta,
            extensiones=list(self.cfg.extensiones),
            titulo=self.cfg.titulo_subida_pc,
            al_terminar=self._al_subir_archivo,
        )

    def recargar_monitor(self, pid: int | None = None) -> None:
        target_id = pid or self.plan_activo_id
        if not target_id:
            self.lbl_estado_monitor.value = self.cfg.texto_sin_planes
            self.lbl_picker_monitor.value = ""
            self.lbl_cantidades_monitor.value = self.cfg.texto_cantidades_inicial
            self.lbl_porcentaje_monitor.value = "0%"
            self.progreso_monitor.value = 0.0
            self.lista_items_monitor.controls.clear()
            self.interfaz.page.update()
            return

        plan = self.cfg.obtener_plan_fn(self.interfaz.order_store, target_id)
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
        self.lbl_estado_monitor.value = f"Estado: {est}"
        self.lbl_estado_monitor.color = color_est
        self.lbl_picker_monitor.value = f"👤 {self.cfg.label_picker_prefix}: {pck}"
        self.lbl_cantidades_monitor.value = self.cfg.formatear_cantidades_fn(plan)
        self.lbl_porcentaje_monitor.value = f"{porc:.1f}%"
        self.progreso_monitor.value = min(1.0, max(0.0, porc / 100.0))

        self.lista_items_monitor.controls.clear()
        for it in self.cfg.obtener_items_plan_fn(self.interfaz.order_store, target_id):
            txt_badge, completado, en_progreso = self.cfg.formatear_item_monitor_fn(it)
            self.lista_items_monitor.controls.append(
                construir_fila_monitor_plan(
                    codigo=it["codigo"],
                    descripcion=it["descripcion"],
                    txt_badge=txt_badge,
                    completado=completado,
                    en_progreso=en_progreso,
                    es_oscuro=self.es_oscuro,
                )
            )
        self.interfaz.page.update()

    def _al_cambiar_plan(self, _e: ft.Event) -> None:
        if self.selector_plan.value:
            self.plan_activo_id = int(self.selector_plan.value)
            self.recargar_monitor(self.plan_activo_id)

    def cambiar_tab(self, nueva_tab: str) -> None:
        self.tab_actual = nueva_tab
        self.btn_tab_nuevo.bgcolor = (
            self.cfg.color_acento if nueva_tab == "nuevo" else self.bg_inactivo
        )
        self.btn_tab_nuevo.color = ft.Colors.WHITE if nueva_tab == "nuevo" else self.interfaz.texto
        self.btn_tab_monitor.bgcolor = (
            self.cfg.color_acento if nueva_tab == "monitor" else self.bg_inactivo
        )
        self.btn_tab_monitor.color = (
            ft.Colors.WHITE if nueva_tab == "monitor" else self.interfaz.texto
        )

        if nueva_tab == "nuevo":
            self.contenedor_vistas.content = self.panel_nuevo
        else:
            nuevos_planes = self.cfg.listar_planes_fn(self.interfaz.order_store)
            self.selector_plan.options = _construir_opciones_planes(
                nuevos_planes, self.cfg.plan_nombre_key
            )
            if nuevos_planes and not self.selector_plan.value:
                self.selector_plan.value = str(nuevos_planes[0]["id"])
                self.plan_activo_id = nuevos_planes[0]["id"]
            self.recargar_monitor()
            self.contenedor_vistas.content = self.panel_monitor
        self.interfaz.page.update()

    async def _al_confirmar_publicacion(self, _e: ft.Event) -> None:
        if not self.items_parseados or not self.archivo_seleccionado:
            self.interfaz.notificar(self.cfg.msg_error_archivo_invalido)
            return

        nombre_plan = (
            (self.txt_nombre.value or "").strip()
            or f"{self.cfg.prefijo_nombre} - {self.archivo_seleccionado.stem}"
        )
        usuario_nom = (
            self.interfaz.usuario_actual.nombre_identificador
            if getattr(self.interfaz, "usuario_actual", None)
            else "Administrador"
        )

        try:
            plan_id = self.cfg.crear_plan_fn(
                self.interfaz.order_store,
                nombre_plan,
                self.archivo_seleccionado.name,
                usuario_nom,
                self.items_parseados,
            )
        except Exception as exc:
            self.interfaz.notificar(self.cfg.msg_error_crear(exc))
            return

        total_unidades = sum(cant for _, _, cant in self.items_parseados)
        self.interfaz.sincronizar_sesiones(
            aviso_colaborativo=self.cfg.msg_aviso_colaborativo(
                usuario_nom, nombre_plan, total_unidades
            )
        )
        self.interfaz.notificar(self.cfg.msg_notificacion_creado(plan_id, nombre_plan))
        self.plan_activo_id = plan_id
        self.selector_plan.value = str(plan_id)
        self.cambiar_tab("monitor")

    def construir_dialogo(self) -> ft.AlertDialog:
        ancho = (
            self.interfaz.ancho_adaptable(680)
            if hasattr(self.interfaz, "ancho_adaptable")
            else 680
        )
        return ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(
                        self.cfg.icono_dialogo,
                        color=self.cfg.color_icono_dialogo,
                        size=24,
                    ),
                    ft.Text(self.cfg.titulo_dialogo, size=16, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=ancho,
                content=ft.Column(
                    [
                        ft.Row([self.btn_tab_nuevo, self.btn_tab_monitor], spacing=8),
                        ft.Divider(height=1),
                        self.contenedor_vistas,
                    ],
                    spacing=10,
                    tight=True,
                ),
            ),
            actions=[ft.TextButton("Cerrar", on_click=lambda _: self.interfaz.page.pop_dialog())],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def mostrar(self) -> None:
        self.interfaz.page.show_dialog(self.construir_dialogo())
        self.interfaz.page.update()


def mostrar_dialogo_planificacion(
    interfaz: Any,
    cfg: PlanDialogConfig,
    parser_fn: Callable[[Path], tuple[dict[str, int], Any]],
    stock_manager_factory: Callable[[], type] = resolver_stock_manager_ui,
) -> None:
    """Construye y muestra el diálogo dual de carga de planilla y monitoreo en tiempo real."""
    if not interfaz.exigir_roles("administrador", "master", "operador"):
        return

    _PlanificacionPickingController(interfaz, cfg, parser_fn, stock_manager_factory).mostrar()
