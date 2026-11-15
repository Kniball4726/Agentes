"""Diálogo para el control y recepción guiada de mercadería de fábrica por escaneo."""

from __future__ import annotations

from datetime import datetime
import inspect
from pathlib import Path
import sys
from typing import Any
import flet as ft

from ..audio_feedback import emitir_tono_error, emitir_tono_exito
from ..theme import ROJO
from ...inventory import StockManager as _DefaultStockManager
from .ingreso_fabrica_archivo import resolver_stock_manager_fabrica


def safe_focus(interfaz: Any, ctrl: Any) -> None:
    try:
        res = ctrl.focus()
        if inspect.iscoroutine(res):
            if (
                hasattr(interfaz, "page")
                and hasattr(interfaz.page, "run_task")
                and callable(interfaz.page.run_task)
                and not getattr(interfaz.page, "_is_mock", False)
                and not hasattr(interfaz.page, "mock_calls")
            ):
                async def _f():
                    await res
                interfaz.page.run_task(_f)
            else:
                res.close()
    except Exception:
        pass


def mostrar_control_ingreso_fabrica(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana interactiva para que el picker controle físicamente el remito de fábrica por escaneo."""
    if not interfaz.exigir_roles("picker", "administrador", "operador", "master"):
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    picker_nom = (
        interfaz.usuario_actual.nombre_identificador
        if getattr(interfaz, "usuario_actual", None)
        else "Picker"
    )

    planes_activos = interfaz.order_store.listar_planes_ingreso_fabrica(estado="en_proceso")
    planes_pendientes = interfaz.order_store.listar_planes_ingreso_fabrica(estado="pendiente")
    todos_candidatos = planes_activos + planes_pendientes

    plan_actual_id = [todos_candidatos[0]["id"] if todos_candidatos else None]

    lbl_plan_titulo = ft.Text(
        "Control de Recepción de Fábrica",
        size=15,
        weight=ft.FontWeight.BOLD,
        color=interfaz.texto,
    )
    lbl_progreso_txt = ft.Text("0.0% (0 / 0 un.)", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
    barra_progreso = ft.ProgressBar(value=0.0, color=ft.Colors.GREEN_600, bgcolor=ft.Colors.GREY_300, height=10)

    banner_feedback = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.INFO_OUTLINE, size=18, color=ft.Colors.BLUE_400),
                ft.Text("Escanee cada bulto o producto recibido para verificarlo contra el remito.", size=12, expand=True),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )

    txt_cantidad = ft.TextField(
        value="1",
        label="Cant.",
        dense=True,
        width=70,
        text_align=ft.TextAlign.CENTER,
    )

    txt_lector = ft.TextField(
        label="Escanear Código de Barras o SKU recibido...",
        dense=True,
        expand=True,
        autofocus=True,
    )

    lista_items = ft.ListView(expand=True, spacing=4, height=250)

    btn_cierre_parcial = ft.Button(
        "📅 Cierre Parcial del Día",
        icon=ft.Icons.SAVE,
        bgcolor=ft.Colors.AMBER_800,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    btn_confirmar_stock = ft.Button(
        "✔ Finalizar Cierre Definitivo",
        icon=ft.Icons.CHECK_CIRCLE,
        bgcolor=ft.Colors.GREEN_700,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    def actualizar_vista_plan() -> None:
        pid = plan_actual_id[0]
        if not pid:
            lbl_plan_titulo.value = "No hay remitos de fábrica pendientes de control."
            lbl_progreso_txt.value = ""
            barra_progreso.value = 0.0
            lista_items.controls.clear()
            txt_lector.disabled = True
            btn_cierre_parcial.disabled = True
            btn_confirmar_stock.disabled = True
            interfaz.page.update()
            return

        plan = interfaz.order_store.obtener_plan_ingreso_fabrica(pid)
        if not plan:
            return

        porc = float(plan.get("porcentaje", 0.0))
        tot = int(plan.get("articulos_esperados", 0))
        ctrl = int(plan.get("articulos_controlados", 0))
        ingr = int(plan.get("articulos_ingresados", 0))
        pend_ingreso = max(0, ctrl - ingr)

        lbl_plan_titulo.value = f"📥 #{plan['id']} - {plan['nombre_remito']}"
        txt_progreso = f"{porc:.1f}% ({ctrl} / {tot} un. verificadas)"
        if ingr > 0:
            txt_progreso += f" • {ingr} un. ya en stock"
        lbl_progreso_txt.value = txt_progreso
        barra_progreso.value = min(1.0, max(0.0, porc / 100.0))

        # Cierre parcial: habilitado si hay unidades verificadas pendientes de ingresar
        btn_cierre_parcial.disabled = pend_ingreso <= 0
        btn_cierre_parcial.text = f"📅 Cierre Parcial ({pend_ingreso} un.)" if pend_ingreso > 0 else "📅 Cierre Parcial del Día"

        # Cierre definitivo: habilitado si se controló al menos 1 unidad
        btn_confirmar_stock.disabled = ctrl <= 0

        items = interfaz.order_store.obtener_items_plan_ingreso_fabrica(pid)
        lista_items.controls.clear()
        for it in items:
            cod = it["codigo"]
            desc = it["descripcion"]
            esp = it["cantidad_esperada"]
            ctrl_it = it["cantidad_controlada"]
            ingr_it = it.get("cantidad_ingresada", 0)
            comp = bool(it["completado"])

            color_item = ft.Colors.GREEN_400 if comp else (ft.Colors.AMBER_400 if ctrl_it > 0 else interfaz.texto)
            icono = ft.Icons.CHECK_CIRCLE if comp else (ft.Icons.PENDING_ACTIONS if ctrl_it > 0 else ft.Icons.RADIO_BUTTON_UNCHECKED)
            icono_color = ft.Colors.GREEN_400 if comp else (ft.Colors.AMBER_400 if ctrl_it > 0 else ft.Colors.GREY_400)

            cant_txt = f"{ctrl_it} / {esp} un."
            if ingr_it > 0:
                cant_txt += f" ({ingr_it} en stock)"

            lista_items.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Icon(icono, color=icono_color, size=18),
                            ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                            ft.Text(desc, size=11, expand=True, no_wrap=True),
                            ft.Text(
                                cant_txt,
                                weight=ft.FontWeight.BOLD,
                                size=11,
                                color=color_item,
                                text_align=ft.TextAlign.RIGHT,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        interfaz.page.update()

    def procesar_escaneo(_e: ft.Event) -> None:
        codigo = txt_lector.value.strip()
        if not codigo:
            return

        cant_val = 1
        try:
            cant_val = max(1, int(txt_cantidad.value or 1))
        except ValueError:
            cant_val = 1

        pid = plan_actual_id[0]
        if not pid:
            return

        res = interfaz.order_store.registrar_escaneo_item_ingreso_fabrica(
            plan_id=pid,
            codigo_escaneado=codigo,
            cantidad=cant_val,
            picker=picker_nom,
        )

        txt_lector.value = ""
        txt_cantidad.value = "1"
        safe_focus(interfaz, txt_lector)

        if res["exito"]:
            emitir_tono_exito()
            banner_feedback.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_400)
            banner_feedback.content = ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=18, color=ft.Colors.GREEN_400),
                    ft.Text(
                        f"✔ {res['codigo']} ({res['descripcion']}): {res['cantidad_actual']} / {res['cantidad_esperada']} un. controladas.",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_800,
                        expand=True,
                    ),
                ],
                spacing=8,
            )

            # Sincronizar en tiempo real con el monitor del administrador
            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"📦 Fábrica #{pid}: {picker_nom} verificó {res['codigo']} ({res['porcentaje']}%)"
            )
        else:
            emitir_tono_error()
            banner_feedback.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED_400)
            banner_feedback.content = ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=18, color=ft.Colors.RED_400),
                    ft.Text(
                        f"⛔ {res.get('mensaje', 'Error en control')}",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.RED_400 if es_oscuro else ft.Colors.RED_800,
                        expand=True,
                    ),
                ],
                spacing=8,
            )

        actualizar_vista_plan()

    txt_lector.on_submit = procesar_escaneo

    selector_planes_fabrica = ft.Dropdown(
        label="Remito de Fábrica a Controlar",
        options=[
            ft.dropdown.Option(
                key=str(p["id"]),
                text=f"#{p['id']} - {p['nombre_remito']} ({p['porcentaje']}%)",
            )
            for p in todos_candidatos
        ],
        value=str(plan_actual_id[0]) if plan_actual_id[0] else None,
        dense=True,
        expand=True,
    )

    def al_cambiar_plan_dropdown(_e: ft.Event) -> None:
        if selector_planes_fabrica.value:
            plan_actual_id[0] = int(selector_planes_fabrica.value)
            actualizar_vista_plan()

    selector_planes_fabrica.on_change = al_cambiar_plan_dropdown

    async def al_cierre_parcial(_e: ft.Event) -> None:
        pid = plan_actual_id[0]
        if not pid:
            return

        def ejecutar() -> None:
            res_parcial = interfaz.order_store.registrar_cierre_parcial_ingreso_fabrica(pid, picker=picker_nom)
            if not res_parcial.get("exito"):
                return

            items_a_ingresar = res_parcial.get("items_a_ingresar", {})
            if items_a_ingresar:
                sm = resolver_stock_manager_fabrica()(interfaz.menu.ruta_excel_base)
                try:
                    sm.registrar_ingreso_fabrica(items_a_ingresar, sobrescribir=False)
                except Exception as exc_sm:
                    print(f"[WARN] Error al registrar cierre parcial en stock: {exc_sm}")

            total_u = res_parcial.get("articulos_ingresados_parcial", 0)
            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"📦 Cierre parcial remito #{pid} por {picker_nom}: +{total_u} un. verificadas ingresadas al stock central."
            )

        await interfaz.ejecutar_tarea(f"Registrando Cierre Parcial Fábrica #{pid}", ejecutar)
        interfaz.actualizar_estado()
        actualizar_vista_plan()
        interfaz.notificar(f"¡Cierre parcial del remito #{pid} registrado! Las unidades verificadas ya ingresaron al stock central.")

    btn_cierre_parcial.on_click = al_cierre_parcial

    async def al_confirmar_ingreso_stock(_e: ft.Event) -> None:
        pid = plan_actual_id[0]
        if not pid:
            return

        plan = interfaz.order_store.obtener_plan_ingreso_fabrica(pid)
        if not plan:
            return

        interfaz.page.pop_dialog()

        def ejecutar() -> None:
            # 1. Finalizar plan en DB y obtener únicamente los artículos controlados pendientes de ingresar
            res_fin = interfaz.order_store.finalizar_plan_ingreso_fabrica(pid, picker=picker_nom)
            items_controlados = res_fin.get("items_controlados", {})

            if items_controlados:
                sm = resolver_stock_manager_fabrica()(interfaz.menu.ruta_excel_base)
                try:
                    sm.registrar_ingreso_fabrica(items_controlados, sobrescribir=False)
                except Exception as exc_sm:
                    print(f"[WARN] Error al registrar ingreso en catálogo central: {exc_sm}")

            total_u = sum(items_controlados.values()) if items_controlados else 0
            total_total = res_fin.get("articulos_controlados", 0)

            # 2. Notificar a todas las terminales LAN
            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"🎉 Ingreso de fábrica #{pid} completado por {picker_nom}: total verificado {total_total} un. ({total_u} un. en cierre final)."
            )

        await interfaz.ejecutar_tarea(f"Finalizando Ingreso de Fábrica #{pid}", ejecutar)
        interfaz.actualizar_estado()
        interfaz.notificar(f"¡Ingreso de fábrica #{pid} completado y cerrado definitivamente!")

    btn_confirmar_stock.on_click = al_confirmar_ingreso_stock

    actualizar_vista_plan()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.INVENTORY_2, color=ft.Colors.GREEN_500, size=24),
                ft.Text("Control de Ingreso - Fábrica", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=interfaz.ancho_adaptable(680) if hasattr(interfaz, "ancho_adaptable") else 680,
            content=ft.Column(
                [
                    ft.Row([selector_planes_fabrica], spacing=8),
                    ft.Row([lbl_plan_titulo, lbl_progreso_txt], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    barra_progreso,
                    banner_feedback,
                    ft.Row(
                        [
                            txt_lector,
                            txt_cantidad,
                            ft.IconButton(
                                ft.Icons.QR_CODE_SCANNER,
                                tooltip="Registrar escaneo",
                                on_click=procesar_escaneo,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Text("Artículos del Remito:", size=12, weight=ft.FontWeight.BOLD),
                    lista_items,
                ],
                spacing=8,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Pausar (Guardar avance)", on_click=lambda _: interfaz.page.pop_dialog()),
            ft.Row(
                [
                    btn_cierre_parcial,
                    btn_confirmar_stock,
                ],
                spacing=8,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    interfaz.page.show_dialog(dialogo)
    interfaz.page.update()
    safe_focus(interfaz, txt_lector)
