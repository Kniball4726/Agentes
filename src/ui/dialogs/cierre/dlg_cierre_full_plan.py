"""Diálogos y ejecutores compartidos para Cierre Parcial y Cierre Final de Mercado Full."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import flet as ft

from ...theme import ROJO, SECUNDARIO_CLARO, SECUNDARIO_OSCURO
from .hoja_ruta import _get_stock_manager_cls


def _resolver_nota_unica(order_store: Any, nota_base: str) -> str:
    """Genera una nota de pedido única para el lote descontado de Mercado Full."""
    if not order_store.existe_nota_pedido(nota_base):
        return nota_base
    sufijo = datetime.now().strftime("%H%M%S")
    candidato = f"{nota_base}_{sufijo}"
    indice = 1
    while order_store.existe_nota_pedido(candidato):
        candidato = f"{nota_base}_{sufijo}_{indice}"
        indice += 1
    return candidato


def procesar_cierre_plan_full_sync(
    interfaz: Any,
    plan_id: int,
    *,
    es_final: bool,
    picker_nom: str,
    stock_manager_cls: Any = None,
) -> dict[str, Any]:
    """Ejecuta el cierre parcial/final en DB, descuenta solo el delta en stock y registra el pedido."""
    if es_final:
        res = interfaz.order_store.registrar_cierre_final_mercado_full(plan_id, picker=picker_nom)
    else:
        res = interfaz.order_store.registrar_cierre_parcial_mercado_full(plan_id, picker=picker_nom)

    if not res.get("exito"):
        return res

    delta_items = res.get("delta_items") or {}
    items_detalle = res.get("items_detalle") or []
    total_unidades = int(res.get("total_descontado") or 0)
    archivo_excel = str(res.get("archivo_excel") or "MercadoFull.xlsx")

    if total_unidades > 0 and delta_items:
        sm_factory = stock_manager_cls or _get_stock_manager_cls()
        sm = sm_factory(interfaz.menu.ruta_excel_base)
        try:
            sm.descontar_mercado_full(
                delta_items,
                nombre_archivo=archivo_excel,
                sincronizar_excel=True,
            )
        except Exception as exc_sm:
            print(f"[WARN] Error al descontar del catálogo central Full: {exc_sm}")

        nota_base = f"FULL-PLAN-{plan_id}" if es_final else f"FULL-PLAN-{plan_id}-PARCIAL"
        nota_full = _resolver_nota_unica(interfaz.order_store, nota_base)
        resumen_it = f"{len(delta_items)} productos ({total_unidades} un.)"
        try:
            interfaz.order_store.registrar_pedido(
                nota_pedido=nota_full,
                numero_pedido=f"ENVIO-{plan_id}",
                cliente="Mercado Envíos Full",
                bultos=1,
                logistica="Transporte",
                armador=picker_nom,
                tipo_archivo="excel",
                nombre_archivo=archivo_excel,
                agregado=False,
                articulos_descontados=total_unidades,
                resumen_items=resumen_it,
                fecha_retiro=datetime.now().strftime("%Y-%m-%d"),
                archivo_descuento="",
                items=items_detalle,
                archivo_hash="",
            )
        except Exception as exc_order:
            print(f"[WARN] No se pudo registrar pedido en store para Mercado Full: {exc_order}")

    nombre_envio = str(res.get("nombre_envio") or "")
    porc = float(res.get("porcentaje") or 0.0)
    if es_final:
        aviso = (
            f"🎉 Envío Full #{plan_id} '{nombre_envio}' cerrado definitivamente por {picker_nom} "
            f"({porc:.1f}% pickeado, {total_unidades} un. en lote final)."
        )
    else:
        aviso = (
            f"📅 Envío Full #{plan_id} '{nombre_envio}': cierre parcial de {picker_nom} "
            f"(+{total_unidades} un. descontadas, {porc:.1f}% total)."
        )
    interfaz.sincronizar_sesiones(aviso_colaborativo=aviso)
    return res


async def ejecutar_cierre_plan_full_async(
    interfaz: Any,
    plan_id: int,
    *,
    es_final: bool,
    picker_nom: str,
    stock_manager_cls: Any = None,
    cerrar_dialogo: bool = True,
) -> dict[str, Any]:
    """Ejecuta en segundo plano el cierre parcial o final de Mercado Full y notifica al usuario."""
    if cerrar_dialogo:
        interfaz.page.pop_dialog()

    resultado_ref: dict[str, Any] = {}

    def ejecutar() -> None:
        res = procesar_cierre_plan_full_sync(
            interfaz,
            plan_id,
            es_final=es_final,
            picker_nom=picker_nom,
            stock_manager_cls=stock_manager_cls,
        )
        resultado_ref.update(res)

    titulo = f"Cierre Final Envío Full #{plan_id}" if es_final else f"Cierre Parcial Envío Full #{plan_id}"
    await interfaz.ejecutar_tarea(titulo, ejecutar)
    interfaz.actualizar_estado()

    if not resultado_ref.get("exito"):
        interfaz.notificar(str(resultado_ref.get("mensaje") or "No se pudo completar el cierre Full."))
        return resultado_ref

    total_un = int(resultado_ref.get("total_descontado") or 0)
    porc = float(resultado_ref.get("porcentaje") or 0.0)
    if es_final:
        interfaz.notificar(
            f"¡Cierre Final Envío Full #{plan_id} completado ({porc:.1f}%, +{total_un} un.)! "
            "Listo para el Cierre de Mercado."
        )
    else:
        interfaz.notificar(
            f"Cierre Parcial Envío Full #{plan_id}: {total_un} un. descontadas del stock. "
            "El envío continúa abierto para seguir escaneando."
        )
    return resultado_ref


def _mostrar_dialogo_cierre_plan_full(interfaz: Any, *, es_final: bool) -> None:
    """Construye y abre el modal para confirmar un cierre parcial o final de Mercado Full."""
    if not interfaz.exigir_roles("picker", "operador", "administrador", "master"):
        return

    es_oscuro = bool(interfaz.modo_oscuro)
    color_sec = SECUNDARIO_OSCURO if es_oscuro else SECUNDARIO_CLARO
    usuario = getattr(interfaz, "usuario_actual", None)
    picker_nom = (
        getattr(usuario, "nombre_identificador", None)
        or getattr(usuario, "username", None)
        or "Picker"
    )

    planes = [
        p for p in interfaz.order_store.listar_planes_mercado_full()
        if p.get("estado") in ("en_proceso", "pendiente")
    ]
    preseleccionado = next((p["id"] for p in planes if p.get("estado") == "en_proceso"), None)
    if preseleccionado is None and planes:
        preseleccionado = planes[0]["id"]
    plan_actual_id = [preseleccionado]

    lbl_resumen = ft.Text("", size=12, weight=ft.FontWeight.W_600)
    lbl_aviso = ft.Text("", size=11, color=color_sec)
    lista_items = ft.ListView(spacing=4, height=220)

    texto_btn = "✔ Confirmar Cierre Final" if es_final else "📅 Confirmar Cierre Parcial"
    btn_confirmar = ft.Button(
        texto_btn,
        icon=ft.Icons.FACT_CHECK if es_final else ft.Icons.SAVE,
        bgcolor=ROJO if es_final else ft.Colors.BLUE_700,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    selector_plan = ft.Dropdown(
        label="Envío Mercado Full Activo",
        dense=True,
        expand=True,
        value=str(plan_actual_id[0]) if plan_actual_id[0] else None,
        options=[
            ft.DropdownOption(
                key=str(p["id"]),
                text=f"#{p['id']} - {p['nombre_envio']} ({float(p.get('porcentaje', 0.0)):.1f}%)",
            )
            for p in planes
        ],
    )

    def actualizar_vista() -> None:
        pid = plan_actual_id[0]
        lista_items.controls.clear()
        if not pid:
            lbl_resumen.value = "No hay envíos de Mercado Full activos en preparación."
            lbl_aviso.value = "Solicite al administrador planificar un envío o verifique si ya fue cerrado."
            btn_confirmar.disabled = True
            btn_confirmar.text = texto_btn
            interfaz.page.update()
            return

        plan = interfaz.order_store.obtener_plan_mercado_full(pid)
        if not plan:
            btn_confirmar.disabled = True
            interfaz.page.update()
            return

        tot = int(plan.get("articulos_totales", 0))
        pick = int(plan.get("articulos_pickeados", 0))
        desc = int(plan.get("articulos_descontados", 0))
        porc = float(plan.get("porcentaje", 0.0))
        pendiente = max(0, pick - desc)
        cierres_prev = interfaz.order_store.listar_cierres_parciales_full(pid)

        lbl_resumen.value = (
            f"Envío #{pid}: {pick} / {tot} un. pickeadas ({porc:.1f}%)  •  "
            f"Ya descontadas: {desc} un.  •  Pendientes de descontar: {pendiente} un."
        )

        if es_final:
            if porc < 100.0:
                lbl_aviso.value = (
                    f"⚠ Cierre con avance del {porc:.1f}% (incompleto). Se descontarán {pendiente} un. "
                    "nuevas y el envío quedará marcado como CERRADO para su despacho final."
                )
                lbl_aviso.color = ft.Colors.AMBER_400 if es_oscuro else ft.Colors.ORANGE_800
            else:
                lbl_aviso.value = (
                    f"Se descontarán {pendiente} un. pendientes y el envío pasará a estado completado "
                    "(listo para Cierre de Mercado)."
                )
                lbl_aviso.color = ft.Colors.GREEN_400 if es_oscuro else ft.Colors.GREEN_800
            btn_confirmar.disabled = (pick <= 0 and desc <= 0)
            btn_confirmar.text = (
                f"✔ Confirmar Cierre Final ({pendiente} un. nuevas)"
                if pendiente > 0
                else "✔ Confirmar Cierre Final"
            )
        else:
            lbl_aviso.value = (
                f"Se descontarán solo las {pendiente} un. nuevas respecto a cierres anteriores "
                f"(cierres parciales previos: {len(cierres_prev)}). El envío seguirá en proceso."
            )
            lbl_aviso.color = ft.Colors.BLUE_300 if es_oscuro else ft.Colors.BLUE_800
            btn_confirmar.disabled = pendiente <= 0
            btn_confirmar.text = (
                f"📅 Confirmar Cierre Parcial ({pendiente} un.)"
                if pendiente > 0
                else "📅 Sin unidades nuevas para descontar"
            )

        items = interfaz.order_store.obtener_items_plan_full(pid)
        for it in items:
            cod = it["codigo"]
            descr = it["descripcion"]
            sol = int(it["cantidad_solicitada"])
            pck = int(it["cantidad_pickeada"])
            des_it = int(it.get("cantidad_descontada", 0))
            delta_it = max(0, pck - des_it)
            detalle_txt = f"{pck}/{sol} pick."
            if des_it > 0:
                detalle_txt += f" • {des_it} desc."
            if delta_it > 0:
                detalle_txt += f" • +{delta_it} hoy"
            lista_items.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                            ft.Text(descr, size=11, expand=True, no_wrap=True),
                            ft.Text(
                                detalle_txt,
                                size=11,
                                weight=ft.FontWeight.W_600,
                                color=(
                                    ft.Colors.BLUE_300 if delta_it > 0 and es_oscuro
                                    else (ft.Colors.BLUE_700 if delta_it > 0 else color_sec)
                                ),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        interfaz.page.update()

    def al_seleccionar_plan(e: Any) -> None:
        val = e.control.value
        plan_actual_id[0] = int(val) if val else None
        actualizar_vista()

    selector_plan.on_select = al_seleccionar_plan

    async def al_confirmar(_e: ft.Event) -> None:
        pid = plan_actual_id[0]
        if not pid:
            return
        await ejecutar_cierre_plan_full_async(
            interfaz,
            pid,
            es_final=es_final,
            picker_nom=picker_nom,
            cerrar_dialogo=True,
        )

    btn_confirmar.on_click = al_confirmar
    actualizar_vista()

    titulo_texto = "Cierre Final Mercado Full" if es_final else "Cierre Parcial Mercado Full"
    icono_titulo = ft.Icons.FACT_CHECK if es_final else ft.Icons.SAVE
    color_icono = ROJO if es_final else ft.Colors.BLUE_700

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(icono_titulo, color=color_icono, size=24),
                ft.Text(titulo_texto, size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=interfaz.ancho_adaptable(620) if hasattr(interfaz, "ancho_adaptable") else 620,
            content=ft.Column(
                [
                    ft.Row([selector_plan]),
                    ft.Container(
                        padding=ft.Padding.all(10),
                        border_radius=8,
                        bgcolor=ft.Colors.WHITE_10 if es_oscuro else ft.Colors.GREY_100,
                        content=ft.Column([lbl_resumen, lbl_aviso], spacing=4, tight=True),
                    ),
                    ft.Text("Detalle por Artículo:", size=12, weight=ft.FontWeight.BOLD),
                    lista_items,
                ],
                spacing=10,
                tight=True,
            ),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: interfaz.page.pop_dialog()),
            btn_confirmar,
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    interfaz.page.show_dialog(dialogo)
    interfaz.page.update()


def mostrar_cierre_parcial_mercado_full(interfaz: Any) -> None:
    """Abre el diálogo de Cierre Parcial de Mercado Full para descontar solo lo pickeado pendiente."""
    _mostrar_dialogo_cierre_plan_full(interfaz, es_final=False)


def mostrar_cierre_final_mercado_full(interfaz: Any) -> None:
    """Abre el diálogo de Cierre Final de Mercado Full para completar y cerrar el envío."""
    _mostrar_dialogo_cierre_plan_full(interfaz, es_final=True)
