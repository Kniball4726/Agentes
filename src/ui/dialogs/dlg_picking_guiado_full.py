"""Diálogo para la preparación guiada de Mercado Envíos Full con escaneo y validación en tiempo real."""

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


def _get_stock_manager():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


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


def mostrar_picking_guiado_full(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana interactiva de picking guiado por código de barras para Mercado Envíos Full."""
    if not interfaz.exigir_roles("picker", "administrador", "operador", "master"):
        return

    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))
    picker_nom = (
        interfaz.usuario_actual.nombre_identificador
        if getattr(interfaz, "usuario_actual", None)
        else "Picker"
    )

    planes_activos = interfaz.order_store.listar_planes_mercado_full(estado="en_proceso")
    planes_pendientes = interfaz.order_store.listar_planes_mercado_full(estado="pendiente")
    todos_candidatos = planes_activos + planes_pendientes

    plan_actual_id = [todos_candidatos[0]["id"] if todos_candidatos else None]

    # Controles superiores
    lbl_plan_titulo = ft.Text(
        "Preparación de Mercado Envíos Full",
        size=15,
        weight=ft.FontWeight.BOLD,
        color=interfaz.texto,
    )
    lbl_progreso_txt = ft.Text("0.0% (0 / 0 un.)", size=13, weight=ft.FontWeight.BOLD, color=ROJO)
    barra_progreso = ft.ProgressBar(value=0.0, color=ROJO, bgcolor=ft.Colors.GREY_300, height=10)

    # Banner de feedback acústico y visual
    banner_feedback = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.INFO_OUTLINE, size=18, color=ft.Colors.BLUE_400),
                ft.Text("Escanee el código de barras o SKU del producto para registrar el picking.", size=12, expand=True),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )

    # Entradas de escaneo
    txt_cantidad = ft.TextField(
        value="1",
        label="Cant.",
        dense=True,
        width=70,
        text_align=ft.TextAlign.CENTER,
    )

    txt_lector = ft.TextField(
        label="Escanear Código de Barras o SKU...",
        dense=True,
        expand=True,
        autofocus=True,
    )

    lista_items = ft.ListView(expand=True, spacing=4, height=250)

    btn_finalizar = ft.Button(
        "✔ Finalizar y Descontar Full",
        icon=ft.Icons.CHECK_CIRCLE,
        bgcolor=ft.Colors.GREEN_600,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    def actualizar_vista_plan() -> None:
        pid = plan_actual_id[0]
        if not pid:
            lbl_plan_titulo.value = "No hay envíos Full pendientes de preparación."
            lbl_progreso_txt.value = ""
            barra_progreso.value = 0.0
            lista_items.controls.clear()
            txt_lector.disabled = True
            btn_finalizar.disabled = True
            interfaz.page.update()
            return

        plan = interfaz.order_store.obtener_plan_mercado_full(pid)
        if not plan:
            return

        porc = float(plan.get("porcentaje", 0.0))
        tot = int(plan.get("articulos_totales", 0))
        pick = int(plan.get("articulos_pickeados", 0))

        lbl_plan_titulo.value = f"📦 #{plan['id']} - {plan['nombre_envio']}"
        lbl_progreso_txt.value = f"{porc:.1f}% ({pick} / {tot} un.)"
        barra_progreso.value = min(1.0, max(0.0, porc / 100.0))

        # Habilitar botón de finalización si llegó al 100% o todo está pickeado
        btn_finalizar.disabled = not (pick >= tot and tot > 0)

        items = interfaz.order_store.obtener_items_plan_full(pid)
        lista_items.controls.clear()
        for it in items:
            cod = it["codigo"]
            desc = it["descripcion"]
            sol = it["cantidad_solicitada"]
            pck = it["cantidad_pickeada"]
            comp = bool(it["completado"])

            color_item = ft.Colors.GREEN_400 if comp else (ft.Colors.AMBER_400 if pck > 0 else interfaz.texto)
            icono = ft.Icons.CHECK_CIRCLE if comp else (ft.Icons.PENDING_ACTIONS if pck > 0 else ft.Icons.RADIO_BUTTON_UNCHECKED)
            icono_color = ft.Colors.GREEN_400 if comp else (ft.Colors.AMBER_400 if pck > 0 else ft.Colors.GREY_400)

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
                                f"{pck} / {sol} un.",
                                weight=ft.FontWeight.BOLD,
                                size=11,
                                color=color_item,
                                width=70,
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

        res = interfaz.order_store.registrar_escaneo_item_plan(
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
                        f"✔ {res['codigo']} ({res['descripcion']}): {res['cantidad_actual']} / {res['cantidad_solicitada']} un.",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_800,
                        expand=True,
                    ),
                ],
                spacing=8,
            )

            # Notificar progreso en tiempo real al administrador
            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"📦 Full #{pid}: {picker_nom} preparó {res['codigo']} ({res['porcentaje']}%)"
            )
        else:
            emitir_tono_error()
            banner_feedback.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED_400)
            banner_feedback.content = ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, size=18, color=ft.Colors.RED_400),
                    ft.Text(
                        f"⛔ {res.get('mensaje', 'Error en escaneo')}",
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

    # Selector de envíos en caso de que existan múltiples
    selector_planes_picker = ft.Dropdown(
        label="Envío a Preparar",
        options=[
            ft.dropdown.Option(
                key=str(p["id"]),
                text=f"#{p['id']} - {p['nombre_envio']} ({p['porcentaje']}%)",
            )
            for p in todos_candidatos
        ],
        value=str(plan_actual_id[0]) if plan_actual_id[0] else None,
        dense=True,
        expand=True,
    )

    def al_cambiar_plan_picker(_e: ft.Event) -> None:
        if selector_planes_picker.value:
            plan_actual_id[0] = int(selector_planes_picker.value)
            actualizar_vista_plan()

    selector_planes_picker.on_change = al_cambiar_plan_picker

    async def al_finalizar_envio(_e: ft.Event) -> None:
        pid = plan_actual_id[0]
        if not pid:
            return

        plan = interfaz.order_store.obtener_plan_mercado_full(pid)
        if not plan:
            return

        items = interfaz.order_store.obtener_items_plan_full(pid)
        items_dict = {it["codigo"]: it["cantidad_pickeada"] for it in items if it["cantidad_pickeada"] > 0}

        interfaz.page.pop_dialog()

        def ejecutar() -> None:
            # 1. Marcar plan completado en DB
            interfaz.order_store.finalizar_plan_mercado_full(pid, picker=picker_nom)

            # 2. Descontar stock central en Excel/SQLite
            sm = _get_stock_manager()(interfaz.menu.ruta_excel_base)
            try:
                sm.descontar_mercado_full(
                    items_dict,
                    nombre_archivo=plan.get("archivo_excel", "MercadoFull.xlsx"),
                    sincronizar_excel=True,
                )
            except Exception as exc_sm:
                print(f"[WARN] Error al descontar del catálogo central: {exc_sm}")

            # 3. Registrar pedido de Mercado Full en store para que aparezca en el Cierre de Mercado
            total_unidades = sum(items_dict.values())
            nota_full = f"FULL-PLAN-{pid}"
            if interfaz.order_store.existe_nota_pedido(nota_full):
                nota_full = f"{nota_full}_{datetime.now().strftime('%H%M%S')}"

            items_pedido: list[tuple[str, str, int]] = []
            for it in items:
                items_pedido.append((it["codigo"], it["descripcion"], it["cantidad_pickeada"]))

            resumen_it = f"{len(items_dict)} productos ({total_unidades} un.)"
            try:
                interfaz.order_store.registrar_pedido(
                    nota_pedido=nota_full,
                    numero_pedido=f"ENVIO-{pid}",
                    cliente="Mercado Envíos Full",
                    bultos=1,
                    logistica="Transporte",
                    armador=picker_nom,
                    tipo_archivo="excel",
                    nombre_archivo=plan.get("archivo_excel", "MercadoFull.xlsx"),
                    agregado=False,
                    articulos_descontados=total_unidades,
                    resumen_items=resumen_it,
                    fecha_retiro=datetime.now().strftime("%Y-%m-%d"),
                    archivo_descuento="",
                    items=items_pedido,
                    archivo_hash="",
                )
            except Exception as exc_order:
                print(f"[WARN] No se pudo registrar pedido en store para Mercado Full: {exc_order}")

            # 4. Sincronizar sesiones para que el Admin vea 100% completado
            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"🎉 Envío Full #{pid} '{plan['nombre_envio']}' completado por {picker_nom} ({total_unidades} un.)!"
            )

        await interfaz.ejecutar_tarea(f"Completando Envío Full #{pid}", ejecutar)
        interfaz.actualizar_estado()
        interfaz.notificar(f"¡Envío Full #{pid} completado con éxito! Listo para el Cierre de Mercado.")

    btn_finalizar.on_click = al_finalizar_envio

    actualizar_vista_plan()

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.LOCAL_SHIPPING, color=ROJO, size=24),
                ft.Text("Preparación Guiada - Mercado Envíos Full", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=interfaz.ancho_adaptable(650) if hasattr(interfaz, "ancho_adaptable") else 650,
            content=ft.Column(
                [
                    ft.Row([selector_planes_picker], spacing=8),
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
                    ft.Text("Artículos del Envío:", size=12, weight=ft.FontWeight.BOLD),
                    lista_items,
                ],
                spacing=8,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Pausar (Guardar progreso)", on_click=lambda _: interfaz.page.pop_dialog()),
            btn_finalizar,
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    interfaz.page.show_dialog(dialogo)
    interfaz.page.update()
    safe_focus(interfaz, txt_lector)
