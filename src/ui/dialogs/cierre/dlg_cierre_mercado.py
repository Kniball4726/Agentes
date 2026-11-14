"""Diálogo interactivo para el Cierre de Mercado (Mercado Libre y Mercado Full) para el rol Picker."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import flet as ft

from ...theme import ROJO
from .cierre_mercado_exec import ejecutar_tarea_cierre_mercado

logger = logging.getLogger("stockagent.ui.cierre_mercado")


def mostrar_dialogo_cierre_mercado(interfaz: Any) -> None:
    """Abre el panel para cerrar la tanda de Mercado Libre o Mercado Full del picker."""
    if not interfaz.exigir_roles("picker", "operador", "administrador", "master"):
        return

    es_movil = bool(getattr(interfaz, "es_pantalla_movil", False))
    es_oscuro = bool(getattr(interfaz, "modo_oscuro", True))

    filtro_tipo = ["TODOS"]
    pedidos_pendientes: list[Any] = []
    seleccionados: dict[int, bool] = {}

    lista_pedidos = ft.ListView(expand=True, spacing=6)
    lista_historial = ft.ListView(expand=True, spacing=6)
    resumen_texto = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=interfaz.texto)

    btn_confirmar = ft.Button(
        "Confirmar Cierre y Emitir Documento",
        icon=ft.Icons.FACT_CHECK,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
        disabled=True,
    )

    def _recargar_pedidos() -> None:
        nonlocal pedidos_pendientes
        armador_filtro = (
            interfaz.usuario_actual.username
            if getattr(interfaz, "usuario_actual", None) and interfaz.usuario_actual.role == "picker"
            else None
        )
        try:
            pedidos_pendientes = interfaz.order_store.listar_pedidos_mercado_pendientes_cierre(
                tipo=filtro_tipo[0],
                armador=armador_filtro,
            )
        except Exception as exc:
            logger.warning("Error al listar pedidos de mercado pendientes: %s", exc)
            pedidos_pendientes = []

        lista_pedidos.controls.clear()
        seleccionados.clear()

        if not pedidos_pendientes:
            lista_pedidos.controls.append(
                ft.Container(
                    padding=16,
                    border_radius=8,
                    bgcolor=interfaz.fondo_acento if es_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400, size=24),
                            ft.Text(
                                "No hay paquetes de Mercado Libre o Full pendientes de cierre en esta tanda.",
                                size=12,
                                color=interfaz.texto,
                                expand=True,
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )
            resumen_texto.value = "Sin despachos pendientes para cerrar."
            btn_confirmar.disabled = True
            interfaz.page.update()
            return

        for p in pedidos_pendientes:
            seleccionados[p.id] = True

            def _on_check(e: ft.Event, pid=p.id) -> None:
                seleccionados[pid] = bool(e.control.value)
                _actualizar_resumen()

            es_full = "FULL" in p.cliente.upper() or "FULL" in p.nombre_archivo.upper() or "FULL" in p.nota_pedido.upper()
            icono_tipo = ft.Icons.LOCAL_SHIPPING if es_full else ft.Icons.STOREFRONT
            color_badge = ft.Colors.AMBER_600 if es_full else ft.Colors.BLUE_400
            etiqueta_badge = "Mercado Full" if es_full else "Mercado Libre"

            lista_pedidos.controls.append(
                ft.Container(
                    bgcolor=interfaz.fondo_acento if es_oscuro else ft.Colors.GREY_50,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=8,
                    content=ft.Row(
                        [
                            ft.Checkbox(
                                value=True,
                                on_change=_on_check,
                            ),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Container(
                                                content=ft.Row(
                                                    [
                                                        ft.Icon(icono_tipo, size=12, color=ft.Colors.WHITE),
                                                        ft.Text(etiqueta_badge, size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                                    ],
                                                    spacing=4,
                                                ),
                                                bgcolor=color_badge,
                                                border_radius=4,
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            ),
                                            ft.Text(f"#{p.nota_pedido}", weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                            ft.Text(f"· {p.cliente}", size=11, color=interfaz.secundario, expand=True, overflow=ft.TextOverflow.ELLIPSIS),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Text(f"Bultos: {p.bultos}", size=11, color=interfaz.secundario),
                                            ft.Text(f"Descuento: {p.resumen_items}", size=11, color=ft.Colors.GREEN_400, weight=ft.FontWeight.W_500),
                                            ft.Text(f"Armador: {p.armador}", size=11, color=interfaz.secundario),
                                        ],
                                        spacing=10,
                                    ),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            ft.Text(p.created_at[11:16] if len(p.created_at) >= 16 else "", size=11, color=interfaz.secundario),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

        _actualizar_resumen()

    def _actualizar_resumen() -> None:
        peds_activos = [p for p in pedidos_pendientes if seleccionados.get(p.id, False)]
        total_peds = len(peds_activos)
        total_units = sum(p.articulos_descontados for p in peds_activos)
        if total_peds == 0:
            resumen_texto.value = "⚠️ Debes seleccionar al menos un pedido para cerrar la tanda."
            resumen_texto.color = ft.Colors.AMBER_400
            btn_confirmar.disabled = True
        else:
            resumen_texto.value = f"📦 {total_peds} pedidos seleccionados ({total_units} unidades en el comprobante)"
            resumen_texto.color = interfaz.texto
            btn_confirmar.disabled = False
        interfaz.page.update()

    def _recargar_historial() -> None:
        lista_historial.controls.clear()
        try:
            cierres = interfaz.order_store.listar_cierres_mercado(limit=25)
        except Exception:
            cierres = []

        if not cierres:
            lista_historial.controls.append(
                ft.Text("Aún no se han registrado cierres de tanda de Mercado.", size=12, color=interfaz.secundario)
            )
            return

        carpeta_desc = getattr(interfaz.menu, "carpeta_descuentos", Path("."))

        for c in cierres:
            pdf_path = carpeta_desc / c.archivo_pdf if c.archivo_pdf else None
            existe_pdf = pdf_path is not None and pdf_path.exists()

            btn_opciones = ft.IconButton(
                icon=ft.Icons.PRINT,
                tooltip="Imprimir o Descargar comprobante en Windows",
                icon_color=ROJO,
                on_click=(lambda _e, r=pdf_path: interfaz.mostrar_opciones_documento(r)) if existe_pdf else None,
            )

            lista_historial.controls.append(
                ft.Container(
                    bgcolor=interfaz.fondo_acento if es_oscuro else ft.Colors.GREY_50,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=8,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(f"Cierre Mercado #{c.id}", weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                                            ft.Text(f"[{c.tipo_mercado}]", size=11, color=ROJO, weight=ft.FontWeight.BOLD),
                                            ft.Text(f"{c.cantidad_pedidos} pedidos ({c.articulos_totales} un.)", size=11, color=ft.Colors.GREEN_400),
                                        ],
                                        spacing=8,
                                    ),
                                    ft.Text(
                                        f"Picker: {c.usuario} · Fecha: {c.created_at[:16]} · Archivo: {c.archivo_pdf or 'N/A'}",
                                        size=10,
                                        color=interfaz.secundario,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            btn_opciones,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

    async def on_confirmar_cierre(_e: ft.Event) -> None:
        peds_a_cerrar = [p for p in pedidos_pendientes if seleccionados.get(p.id, False)]
        if not peds_a_cerrar:
            interfaz.notificar("No hay pedidos seleccionados para cerrar.")
            return

        btn_confirmar.disabled = True
        interfaz.page.pop_dialog()

        res_cierre: dict[str, Any] = {}

        def tarea() -> None:
            res = ejecutar_tarea_cierre_mercado(
                interfaz=interfaz,
                pedidos_seleccionados=peds_a_cerrar,
                tipo_mercado=filtro_tipo[0],
            )
            res_cierre.update(res)

        exito = await interfaz.ejecutar_tarea("Cierre de Mercado", tarea)
        if not exito:
            return

        interfaz.actualizar_listas()
        if hasattr(interfaz, "actualizar_estado"):
            interfaz.actualizar_estado()

        pdf_path = res_cierre.get("pdf_path")
        cid = res_cierre.get("cierre_id", 0)
        tot = res_cierre.get("total_articulos", 0)

        interfaz.notificar(f"✅ Cierre de Mercado #{cid} generado exitosamente ({tot} unidades).")

        # Abre inmediatamente el diálogo de opciones de Windows para Imprimir o Descargar
        if pdf_path and pdf_path.exists():
            interfaz.mostrar_opciones_documento(pdf_path)

    btn_confirmar.on_click = on_confirmar_cierre

    selector_filtro = ft.Dropdown(
        label="Filtrar por Canal de Mercado",
        value="TODOS",
        dense=True,
        options=[
            ft.DropdownOption(key="TODOS", text="Todos los canales (Mercado Libre + Full)"),
            ft.DropdownOption(key="MERCADO_LIBRE", text="Mercado Libre (Pistoleo y Docx)"),
            ft.DropdownOption(key="MERCADO_FULL", text="Mercado Envíos Full (Excel)"),
        ],
    )
    selector_filtro.on_change = lambda e: (filtro_tipo.__setitem__(0, e.control.value), _recargar_pedidos())

    vista_pendientes = ft.Column(
        [
            ft.Row([selector_filtro], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(height=6, color=ft.Colors.TRANSPARENT),
            ft.Text(
                "Selecciona los paquetes pickeados que deseas consolidar en este comprobante de descuento:",
                size=11,
                color=interfaz.secundario,
            ),
            ft.Container(
                content=lista_pedidos,
                height=260 if not es_movil else 200,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=6,
            ),
            ft.Container(
                content=resumen_texto,
                padding=ft.Padding.symmetric(vertical=4),
            ),
        ],
        spacing=6,
    )

    vista_historial = ft.Column(
        [
            ft.Text("Historial de tandas y cierres de Mercado generados:", size=11, color=interfaz.secundario),
            ft.Container(
                content=lista_historial,
                height=300 if not es_movil else 220,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=6,
            ),
        ],
        spacing=6,
    )

    tabs = ft.Tabs(
        length=2,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Cierre de Tanda", icon=ft.Icons.FACT_CHECK),
                        ft.Tab(label="Historial de Cierres", icon=ft.Icons.HISTORY),
                    ]
                ),
                ft.TabBarView(expand=True, controls=[vista_pendientes, vista_historial]),
            ],
        ),
    )

    dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.STOREFRONT, color=ROJO, size=24),
                ft.Text("Cierre de Mercado · Descuento Individual", size=16, weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=620 if not es_movil else 340,
            content=tabs,
        ),
        actions=[
            btn_confirmar,
            interfaz.boton_dialogo("Cancelar", lambda _e: interfaz.page.pop_dialog()),
        ],
    )

    _recargar_pedidos()
    _recargar_historial()
    interfaz.page.show_dialog(dialogo)
