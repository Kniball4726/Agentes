"""Diálogo para la planificación, carga de remito de fábrica y monitoreo en tiempo real del control del picker."""

from __future__ import annotations

from typing import Any

import flet as ft

from ...parsers.factory_parser import parsear_archivo_fabrica
from .picking_plan_dialog import PlanDialogConfig, mostrar_dialogo_planificacion
from .picking_plan_shared import resolver_stock_manager_ui as _get_stock_manager


def _formatear_cantidades_fabrica(plan: dict[str, Any]) -> str:
    tot = int(plan.get("articulos_esperados", 0))
    ctrl = int(plan.get("articulos_controlados", 0))
    ingr = int(plan.get("articulos_ingresados", 0))
    txt = f"{ctrl} / {tot} unidades verificadas"
    if ingr > 0:
        txt += f" ({ingr} un. en stock)"
    return txt


def _formatear_item_fabrica(it: dict[str, Any]) -> tuple[str, bool, bool]:
    it_esp = it["cantidad_esperada"]
    it_ctrl = it["cantidad_controlada"]
    it_ingr = it.get("cantidad_ingresada", 0)
    it_comp = bool(it["completado"])
    if it_comp:
        txt_badge = f"✔ CONTROLADO ({it_ingr} en stock)" if it_ingr > 0 else "✔ CONTROLADO"
    elif it_ctrl > 0:
        txt_badge = f"⏳ {it_ctrl}/{it_esp} un. ({it_ingr} en stock)" if it_ingr > 0 else f"⏳ {it_ctrl}/{it_esp} un."
    else:
        txt_badge = f"0/{it_esp} un."
    return txt_badge, it_comp, it_ctrl > 0


_CONFIG_PLAN_FABRICA = PlanDialogConfig(
    titulo_dialogo="Planificación y Monitoreo de Ingreso de Fábrica",
    icono_dialogo=ft.Icons.INVENTORY_2,
    color_acento=ft.Colors.GREEN_700,
    color_icono_dialogo=ft.Colors.GREEN_500,
    color_preview_cantidad=ft.Colors.GREEN_400,
    color_porcentaje=ft.Colors.GREEN_400,
    color_progreso=ft.Colors.GREEN_600,
    carpeta_attr="carpeta_fabrica",
    subcarpeta_default="Fabrica",
    extensiones=("xlsx", "xls", "pdf"),
    prefijo_nombre="Remito Fábrica",
    label_nombre_plan="Nombre / Número de Remito de Fábrica",
    label_selector_archivo="Comprobante / Remito de Fábrica",
    titulo_subida_pc="Seleccionar comprobante / remito de fábrica",
    descripcion_nuevo="Carga el remito o planilla de fábrica para habilitar el control físico por escaneo del picker.",
    texto_tab_nuevo="Cargar Nuevo Remito",
    texto_boton_publicar="🚀 Crear Ingreso y Notificar al Picker",
    msg_error_archivo_invalido="Debe seleccionar una planilla o remito válido con artículos.",
    msg_sin_columnas="El archivo {archivo} no contiene productos o cantidades reconocidas.",
    msg_resumen_preview=lambda n, u: f"✔ {n} productos esperados ({u} unidades totales).",
    label_selector_plan="Seleccionar Remito de Fábrica",
    label_picker_prefix="Controlando",
    texto_cantidades_inicial="0 / 0 un. controladas",
    texto_sin_planes="Sin remitos registrados.",
    titulo_detalle_monitor="Detalle por Producto en el Remito:",
    msg_aviso_colaborativo=lambda usr, nom, tot: (
        f"🔔 Nuevo remito de fábrica cargado por {usr}: '{nom}' ({tot} un. esperadas) - ¡Listo para control!"
    ),
    msg_notificacion_creado=lambda pid, nom: f"Remito #{pid} '{nom}' creado y notificado al equipo de control.",
    msg_error_crear=lambda exc: f"Error al crear el remito de fábrica: {exc}",
    plan_nombre_key="nombre_remito",
    obtener_plan_activo_fn=lambda store: store.obtener_plan_activo_ingreso_fabrica(),
    listar_planes_fn=lambda store: store.listar_planes_ingreso_fabrica(),
    obtener_plan_fn=lambda store, pid: store.obtener_plan_ingreso_fabrica(pid),
    obtener_items_plan_fn=lambda store, pid: store.obtener_items_plan_ingreso_fabrica(pid),
    crear_plan_fn=lambda store, nom, arch, usr, items: store.crear_plan_ingreso_fabrica(
        nombre_remito=nom,
        archivo_remito=arch,
        creado_por=usr,
        items=items,
    ),
    formatear_cantidades_fn=_formatear_cantidades_fabrica,
    formatear_item_monitor_fn=_formatear_item_fabrica,
)


def mostrar_planificar_ingreso_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para que el Administrador cargue el remito de fábrica y monitoree el control en tiempo real."""
    mostrar_dialogo_planificacion(
        interfaz,
        _CONFIG_PLAN_FABRICA,
        parsear_archivo_fabrica,
        stock_manager_factory=_get_stock_manager,
    )
