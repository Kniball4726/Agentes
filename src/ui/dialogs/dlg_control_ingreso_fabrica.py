"""Diálogo para el control y recepción guiada de mercadería de fábrica por escaneo."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

from .ingreso_fabrica_archivo import resolver_stock_manager_fabrica
from .picking_plan_shared import (
    actualizar_banner_resultado_escaneo,
    construir_banner_escaneo_inicial,
    construir_fila_picking_guiado,
    safe_focus,
)

logger = logging.getLogger(__name__)


def _registrar_items_en_stock(interfaz: Any, items: dict[str, int], contexto: str) -> None:
    if not items:
        return
    sm = resolver_stock_manager_fabrica(interfaz)(interfaz.menu.ruta_excel_base)
    try:
        sm.registrar_ingreso_fabrica(items, sobrescribir=False)
    except Exception as exc_sm:
        logger.warning("Error al registrar %s en stock: %s", contexto, exc_sm)


class _ControlIngresoFabricaController:
    """Controlador de estado y eventos para el control guiado de remitos de fábrica."""

    def __init__(self, interfaz: Any) -> None:
        self.interfaz = interfaz
        self.es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
        self.picker_nom = (
            interfaz.usuario_actual.nombre_identificador
            if getattr(interfaz, "usuario_actual", None)
            else "Picker"
        )
        planes_activos = interfaz.order_store.listar_planes_ingreso_fabrica(estado="en_proceso")
        planes_pendientes = interfaz.order_store.listar_planes_ingreso_fabrica(estado="pendiente")
        candidatos = planes_activos + planes_pendientes
        self.plan_actual_id: int | None = candidatos[0]["id"] if candidatos else None

        self.lbl_plan_titulo = ft.Text(
            "Control de Recepción de Fábrica",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=interfaz.texto,
        )
        self.lbl_progreso_txt = ft.Text(
            "0.0% (0 / 0 un.)",
            size=13,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.GREEN_400,
        )
        self.barra_progreso = ft.ProgressBar(
            value=0.0,
            color=ft.Colors.GREEN_600,
            bgcolor=ft.Colors.GREY_300,
            height=10,
        )
        self.banner_feedback = construir_banner_escaneo_inicial(
            "Escanee cada bulto o producto recibido para verificarlo contra el remito.",
            self.es_oscuro,
        )
        self.txt_cantidad = ft.TextField(
            value="1",
            label="Cant.",
            dense=True,
            width=70,
            text_align=ft.TextAlign.CENTER,
        )
        self.txt_lector = ft.TextField(
            label="Escanear Código de Barras o SKU recibido...",
            dense=True,
            expand=True,
            autofocus=True,
            on_submit=self.procesar_escaneo,
        )
        self.lista_items = ft.ListView(expand=True, spacing=4, height=250)
        self.btn_cierre_parcial = ft.Button(
            "📅 Cierre Parcial del Día",
            icon=ft.Icons.SAVE,
            bgcolor=ft.Colors.AMBER_800,
            color=ft.Colors.WHITE,
            disabled=True,
            on_click=self.al_cierre_parcial,
        )
        self.btn_confirmar_stock = ft.Button(
            "✔ Finalizar Cierre Definitivo",
            icon=ft.Icons.CHECK_CIRCLE,
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE,
            disabled=True,
            on_click=self.al_confirmar_ingreso_stock,
        )
        self.selector_planes_fabrica = ft.Dropdown(
            label="Remito de Fábrica a Controlar",
            options=[
                ft.dropdown.Option(
                    key=str(p["id"]),
                    text=f"#{p['id']} - {p['nombre_remito']} ({p['porcentaje']}%)",
                )
                for p in candidatos
            ],
            value=str(self.plan_actual_id) if self.plan_actual_id else None,
            dense=True,
            expand=True,
            on_select=self._al_cambiar_plan_dropdown,
        )
        self.actualizar_vista_plan()

    def _renderizar_sin_plan(self) -> None:
        self.lbl_plan_titulo.value = "No hay remitos de fábrica pendientes de control."
        self.lbl_progreso_txt.value = ""
        self.barra_progreso.value = 0.0
        self.lista_items.controls.clear()
        self.txt_lector.disabled = True
        self.btn_cierre_parcial.disabled = True
        self.btn_confirmar_stock.disabled = True
        self.interfaz.page.update()

    def actualizar_vista_plan(self) -> None:
        pid = self.plan_actual_id
        if not pid:
            self._renderizar_sin_plan()
            return

        plan = self.interfaz.order_store.obtener_plan_ingreso_fabrica(pid)
        if not plan:
            return

        porc = float(plan.get("porcentaje", 0.0))
        tot = int(plan.get("articulos_esperados", 0))
        ctrl = int(plan.get("articulos_controlados", 0))
        ingr = int(plan.get("articulos_ingresados", 0))
        pend_ingreso = max(0, ctrl - ingr)

        self.lbl_plan_titulo.value = f"📥 #{plan['id']} - {plan['nombre_remito']}"
        txt_progreso = f"{porc:.1f}% ({ctrl} / {tot} un. verificadas)"
        if ingr > 0:
            txt_progreso += f" • {ingr} un. ya en stock"
        self.lbl_progreso_txt.value = txt_progreso
        self.barra_progreso.value = min(1.0, max(0.0, porc / 100.0))

        self.btn_cierre_parcial.disabled = pend_ingreso <= 0
        self.btn_cierre_parcial.content = (
            f"📅 Cierre Parcial ({pend_ingreso} un.)"
            if pend_ingreso > 0
            else "📅 Cierre Parcial del Día"
        )
        self.btn_confirmar_stock.disabled = ctrl <= 0

        self.lista_items.controls.clear()
        for it in self.interfaz.order_store.obtener_items_plan_ingreso_fabrica(pid):
            ctrl_it = it["cantidad_controlada"]
            ingr_it = it.get("cantidad_ingresada", 0)
            cant_txt = f"{ctrl_it} / {it['cantidad_esperada']} un."
            if ingr_it > 0:
                cant_txt += f" ({ingr_it} en stock)"
            self.lista_items.controls.append(
                construir_fila_picking_guiado(
                    codigo=it["codigo"],
                    descripcion=it["descripcion"],
                    cant_txt=cant_txt,
                    completado=bool(it["completado"]),
                    en_progreso=ctrl_it > 0,
                    color_texto_base=self.interfaz.texto,
                    es_oscuro=self.es_oscuro,
                )
            )
        self.interfaz.page.update()

    def procesar_escaneo(self, _e: ft.Event) -> None:
        codigo = (self.txt_lector.value or "").strip()
        pid = self.plan_actual_id
        if not codigo or not pid:
            return

        try:
            cant_val = max(1, int(self.txt_cantidad.value or 1))
        except ValueError:
            cant_val = 1

        res = self.interfaz.order_store.registrar_escaneo_item_ingreso_fabrica(
            plan_id=pid,
            codigo_escaneado=codigo,
            cantidad=cant_val,
            picker=self.picker_nom,
        )

        self.txt_lector.value = ""
        self.txt_cantidad.value = "1"
        safe_focus(self.interfaz, self.txt_lector)

        if res["exito"]:
            actualizar_banner_resultado_escaneo(
                self.banner_feedback,
                True,
                f"✔ {res['codigo']} ({res['descripcion']}): {res['cantidad_actual']} / {res['cantidad_esperada']} un. controladas.",
                self.es_oscuro,
            )
            self.interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"📦 Fábrica #{pid}: {self.picker_nom} verificó {res['codigo']} ({res['porcentaje']}%)"
            )
        else:
            actualizar_banner_resultado_escaneo(
                self.banner_feedback,
                False,
                f"⛔ {res.get('mensaje', 'Error en control')}",
                self.es_oscuro,
            )

        self.actualizar_vista_plan()

    def _al_cambiar_plan_dropdown(self, _e: ft.Event) -> None:
        if self.selector_planes_fabrica.value:
            self.plan_actual_id = int(self.selector_planes_fabrica.value)
            self.actualizar_vista_plan()

    async def al_cierre_parcial(self, _e: ft.Event) -> None:
        pid = self.plan_actual_id
        if not pid:
            return

        def ejecutar() -> None:
            res_parcial = self.interfaz.order_store.registrar_cierre_parcial_ingreso_fabrica(
                pid, picker=self.picker_nom
            )
            if not res_parcial.get("exito"):
                return
            _registrar_items_en_stock(
                self.interfaz,
                res_parcial.get("items_a_ingresar", {}),
                "cierre parcial",
            )
            total_u = res_parcial.get("articulos_ingresados_parcial", 0)
            self.interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"📦 Cierre parcial remito #{pid} por {self.picker_nom}: +{total_u} un. verificadas ingresadas al stock central."
            )

        await self.interfaz.ejecutar_tarea(f"Registrando Cierre Parcial Fábrica #{pid}", ejecutar)
        self.interfaz.actualizar_estado()
        self.actualizar_vista_plan()
        self.interfaz.notificar(
            f"¡Cierre parcial del remito #{pid} registrado! Las unidades verificadas ya ingresaron al stock central."
        )

    async def al_confirmar_ingreso_stock(self, _e: ft.Event) -> None:
        pid = self.plan_actual_id
        if not pid:
            return
        if not self.interfaz.order_store.obtener_plan_ingreso_fabrica(pid):
            return

        self.interfaz.page.pop_dialog()

        def ejecutar() -> None:
            res_fin = self.interfaz.order_store.finalizar_plan_ingreso_fabrica(
                pid, picker=self.picker_nom
            )
            items_controlados = res_fin.get("items_controlados", {})
            _registrar_items_en_stock(self.interfaz, items_controlados, "ingreso en catálogo central")
            total_u = sum(items_controlados.values()) if items_controlados else 0
            total_total = res_fin.get("articulos_controlados", 0)
            self.interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"🎉 Ingreso de fábrica #{pid} completado por {self.picker_nom}: total verificado {total_total} un. ({total_u} un. en cierre final)."
            )

        await self.interfaz.ejecutar_tarea(f"Finalizando Ingreso de Fábrica #{pid}", ejecutar)
        self.interfaz.actualizar_estado()
        self.interfaz.notificar(f"¡Ingreso de fábrica #{pid} completado y cerrado definitivamente!")

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
                    ft.Icon(ft.Icons.INVENTORY_2, color=ft.Colors.GREEN_500, size=24),
                    ft.Text("Control de Ingreso - Fábrica", size=16, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=ancho,
                content=ft.Column(
                    [
                        ft.Row([self.selector_planes_fabrica], spacing=8),
                        ft.Row(
                            [self.lbl_plan_titulo, self.lbl_progreso_txt],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        self.barra_progreso,
                        self.banner_feedback,
                        ft.Row(
                            [
                                self.txt_lector,
                                self.txt_cantidad,
                                ft.IconButton(
                                    ft.Icons.QR_CODE_SCANNER,
                                    tooltip="Registrar escaneo",
                                    on_click=self.procesar_escaneo,
                                ),
                            ],
                            spacing=6,
                        ),
                        ft.Text("Artículos del Remito:", size=12, weight=ft.FontWeight.BOLD),
                        self.lista_items,
                    ],
                    spacing=8,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton(
                    "Pausar (Guardar avance)",
                    on_click=lambda _: self.interfaz.page.pop_dialog(),
                ),
                ft.Row([self.btn_cierre_parcial, self.btn_confirmar_stock], spacing=8),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def mostrar(self) -> None:
        self.interfaz.page.show_dialog(self.construir_dialogo())
        self.interfaz.page.update()
        safe_focus(self.interfaz, self.txt_lector)


def mostrar_control_ingreso_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana interactiva para que el picker controle físicamente el remito de fábrica por escaneo."""
    if not interfaz.exigir_roles("picker", "administrador", "operador", "master"):
        return

    _ControlIngresoFabricaController(interfaz).mostrar()
