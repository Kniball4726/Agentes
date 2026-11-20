"""Diálogo para la preparación guiada de Mercado Envíos Full con escaneo y validación en tiempo real."""

from __future__ import annotations

from typing import Any
import flet as ft

from ..theme import ROJO
from .picking_plan_shared import (
    actualizar_banner_resultado_escaneo,
    construir_banner_escaneo_inicial,
    construir_fila_picking_guiado,
    resolver_stock_manager_ui as _get_stock_manager,
    safe_focus,
)


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
    banner_feedback = construir_banner_escaneo_inicial(
        "Escanee el código de barras o SKU del producto para registrar el picking.",
        es_oscuro,
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

    btn_cierre_parcial = ft.Button(
        "Cierre Parcial (Lote)",
        icon=ft.Icons.SAVINGS_OUTLINED,
        bgcolor=ft.Colors.AMBER_700,
        color=ft.Colors.WHITE,
        disabled=True,
        on_click=lambda _: (interfaz.page.pop_dialog(), interfaz.mostrar_cierre_parcial_mercado_full()),
    )

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
            btn_cierre_parcial.disabled = True
            btn_finalizar.disabled = True
            interfaz.page.update()
            return

        plan = interfaz.order_store.obtener_plan_mercado_full(pid)
        if not plan:
            return

        porc = float(plan.get("porcentaje", 0.0))
        tot = int(plan.get("articulos_totales", 0))
        pick = int(plan.get("articulos_pickeados", 0))
        desc = int(plan.get("articulos_descontados", 0))

        lbl_plan_titulo.value = f"📦 #{plan['id']} - {plan['nombre_envio']}"
        lbl_progreso_txt.value = f"{porc:.1f}% ({pick} / {tot} un.)"
        barra_progreso.value = min(1.0, max(0.0, porc / 100.0))

        # Habilitar cierre parcial si hay delta nuevo y finalizar si el plan tiene artículos
        delta_pendiente = max(0, pick - desc)
        btn_cierre_parcial.disabled = not (delta_pendiente > 0)
        btn_finalizar.disabled = not (tot > 0)

        items = interfaz.order_store.obtener_items_plan_full(pid)
        lista_items.controls.clear()
        for it in items:
            pck = it["cantidad_pickeada"]
            sol = it["cantidad_solicitada"]
            lista_items.controls.append(
                construir_fila_picking_guiado(
                    codigo=it["codigo"],
                    descripcion=it["descripcion"],
                    cant_txt=f"{pck} / {sol} un.",
                    completado=bool(it["completado"]),
                    en_progreso=pck > 0,
                    color_texto_base=interfaz.texto,
                    es_oscuro=es_oscuro,
                    ancho_cant=70,
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
            actualizar_banner_resultado_escaneo(
                banner_feedback,
                True,
                f"✔ {res['codigo']} ({res['descripcion']}): {res['cantidad_actual']} / {res['cantidad_solicitada']} un.",
                es_oscuro,
            )
            interfaz.sincronizar_sesiones(
                aviso_colaborativo=f"📦 Full #{pid}: {picker_nom} preparó {res['codigo']} ({res['porcentaje']}%)"
            )
        else:
            actualizar_banner_resultado_escaneo(
                banner_feedback,
                False,
                f"⛔ {res.get('mensaje', 'Error en escaneo')}",
                es_oscuro,
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

    selector_planes_picker.on_select = al_cambiar_plan_picker

    async def al_finalizar_envio(_e: ft.Event) -> None:
        pid = plan_actual_id[0]
        if not pid:
            return
        from .cierre.dlg_cierre_full_plan import ejecutar_cierre_plan_full_async

        await ejecutar_cierre_plan_full_async(
            interfaz,
            pid,
            es_final=True,
            picker_nom=picker_nom,
            stock_manager_cls=_get_stock_manager(),
            cerrar_dialogo=True,
        )

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
            ft.Row([btn_cierre_parcial, btn_finalizar], spacing=6),
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    interfaz.page.show_dialog(dialogo)
    interfaz.page.update()
    safe_focus(interfaz, txt_lector)
