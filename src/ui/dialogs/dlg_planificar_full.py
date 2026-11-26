"""Diálogo para la planificación, carga de Excel y monitoreo en tiempo real de Mercado Envíos Full."""

from __future__ import annotations

from typing import Any

import flet as ft

from ...parsers.mercado_full_parser import parsear_archivo_mercado_full
from ..theme import ROJO
from .picking_plan_dialog import PlanDialogConfig, mostrar_dialogo_planificacion
from .picking_plan_shared import resolver_stock_manager_ui as _get_stock_manager


def _formatear_cantidades_full(plan: dict[str, Any]) -> str:
    tot = int(plan.get("articulos_totales", 0))
    pick = int(plan.get("articulos_pickeados", 0))
    return f"{pick} / {tot} unidades preparadas"


def _formatear_item_full(it: dict[str, Any]) -> tuple[str, bool, bool]:
    it_sol = it["cantidad_solicitada"]
    it_pick = it["cantidad_pickeada"]
    it_comp = bool(it["completado"])
    txt_badge = "✔ COMPLETO" if it_comp else f"⏳ {it_pick}/{it_sol} un."
    return txt_badge, it_comp, it_pick > 0


_CONFIG_PLAN_FULL = PlanDialogConfig(
    titulo_dialogo="Planificación y Monitoreo de Mercado Full",
    icono_dialogo=ft.Icons.LOCAL_SHIPPING,
    color_acento=ROJO,
    color_icono_dialogo=ROJO,
    color_preview_cantidad=ROJO,
    color_porcentaje=ROJO,
    color_progreso=ROJO,
    carpeta_attr="carpeta_mercado_full",
    subcarpeta_default="MercadoFull",
    extensiones=("xlsx", "xls"),
    prefijo_nombre="Envío Full",
    label_nombre_plan="Nombre o Referencia del Envío",
    label_selector_archivo="Planilla Excel (.xlsx / .xls)",
    titulo_subida_pc="Seleccionar planilla de Mercado Full",
    descripcion_nuevo="Carga el archivo Excel de Mercado Full con los SKU y cantidades a preparar por el picker.",
    texto_tab_nuevo="Cargar Nuevo Envío",
    texto_boton_publicar="🚀 Crear Envío y Notificar al Picker",
    msg_error_archivo_invalido="Debe seleccionar una planilla Excel válida con artículos.",
    msg_sin_columnas="El archivo {archivo} no contiene columnas válidas de SKU/Cantidad.",
    msg_resumen_preview=lambda n, u: f"✔ {n} productos cargados ({u} unidades totales).",
    label_selector_plan="Seleccionar Envío / Plan",
    label_picker_prefix="Picker asignado",
    texto_cantidades_inicial="0 / 0 un.",
    texto_sin_planes="Sin envíos registrados.",
    titulo_detalle_monitor="Detalle por Producto en el Envío:",
    msg_aviso_colaborativo=lambda usr, nom, tot: (
        f"🔔 Nuevo envío Mercado Full cargado por {usr}: '{nom}' ({tot} un.) - Listo para preparar"
    ),
    msg_notificacion_creado=lambda pid, nom: f"Plan #{pid} '{nom}' creado y notificado al equipo de pickers.",
    msg_error_crear=lambda exc: f"Error al crear el plan: {exc}",
    plan_nombre_key="nombre_envio",
    obtener_plan_activo_fn=lambda store: store.obtener_plan_activo_mercado_full(),
    listar_planes_fn=lambda store: store.listar_planes_mercado_full(),
    obtener_plan_fn=lambda store, pid: store.obtener_plan_mercado_full(pid),
    obtener_items_plan_fn=lambda store, pid: store.obtener_items_plan_full(pid),
    crear_plan_fn=lambda store, nom, arch, usr, items: store.crear_plan_mercado_full(
        nombre_envio=nom,
        archivo_excel=arch,
        creado_por=usr,
        items=items,
    ),
    formatear_cantidades_fn=_formatear_cantidades_full,
    formatear_item_monitor_fn=_formatear_item_full,
)


def mostrar_planificar_full(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para que el Administrador cargue el Excel de Full y monitoree el picking en tiempo real."""
    mostrar_dialogo_planificacion(
        interfaz,
        _CONFIG_PLAN_FULL,
        parsear_archivo_mercado_full,
        stock_manager_factory=lambda: _get_stock_manager(interfaz),
    )
