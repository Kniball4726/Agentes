"""Diálogos para supervisión y auditoría de cierres de operarios por administración."""
from pathlib import Path
import sys
from typing import Any
import flet as ft

from ....paths import application_root
from ...theme import ROJO
from .hoja_ruta import resolver_archivos_cierre, gestionar_hoja_ruta_cierre

def mostrar_detalle_pedidos_cierre(interfaz: Any, cierre_obj: Any) -> None:
    """Muestra un modal detallado con la lista de pedidos consolidados en un cierre de jornada específico."""
    peds = interfaz.order_store.obtener_pedidos_por_cierre(cierre_obj.id)
    pdf_ruta, xls_ruta, hoja_ruta = resolver_archivos_cierre(interfaz, cierre_obj)

    lista_pedidos_ctrl = ft.ListView(expand=True, spacing=6, height=380)
    if not peds:
        lista_pedidos_ctrl.controls.append(
            ft.Container(
                padding=20,
                alignment=ft.Alignment.CENTER,
                content=ft.Text(
                    "No se encontraron registros de pedidos individuales para este cierre.",
                    size=12,
                    color=interfaz.secundario,
                ),
            )
        )
    else:
        for p in peds:
            num_ped_txt = f"Pedido #{p.numero_pedido}" if getattr(p, "numero_pedido", "") else f"Remito: {p.nota_pedido}"
            st_despacho = getattr(p, "estado_despacho", "") or "Preparado"
            badge_color = ft.Colors.BLUE_400 if st_despacho == "Preparado" else (
                ft.Colors.AMBER_400 if st_despacho == "Despachado" else ft.Colors.GREEN_400
            )

            lista_pedidos_ctrl.controls.append(
                ft.Container(
                    bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=10,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                                            ft.Text(f"· Remito: {p.nota_pedido}", size=11, color=interfaz.secundario) if getattr(p, "numero_pedido", "") else ft.Container(),
                                            ft.Container(
                                                content=ft.Text(st_despacho, size=10, weight=ft.FontWeight.BOLD, color=badge_color),
                                                bgcolor=ft.Colors.with_opacity(0.12, badge_color),
                                                border_radius=4,
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                    ft.Text(f"Armado: {p.created_at[:16]}", size=10, color=interfaz.secundario),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Row(
                                [
                                    ft.Text(f"👤 Cliente: {p.cliente}", size=11, color=interfaz.texto, weight=ft.FontWeight.W_500),
                                    ft.Text(f"📦 Bultos: {p.bultos}", size=11, color=interfaz.secundario),
                                    ft.Text(f"🚚 Logística: {p.logistica or 'Sin especificar'}", size=11, color=interfaz.secundario),
                                    ft.Text(f"🔢 Unid: {p.articulos_descontados}", size=11, color=ROJO, weight=ft.FontWeight.BOLD),
                                ],
                                spacing=12,
                                wrap=True,
                            ),
                            ft.Text(
                                f"Detalle ítems: {p.resumen_items}",
                                size=11,
                                color=interfaz.secundario,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ) if getattr(p, "resumen_items", "") else ft.Container(),
                        ],
                        spacing=4,
                    ),
                )
            )

    total_bultos = sum(p.bultos for p in peds)
    total_unid = sum(p.articulos_descontados for p in peds)

    acciones = [
        interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())
    ]
    if peds or (hoja_ruta and hoja_ruta.exists()):
        acciones.insert(
            0,
            interfaz.boton(
                "Hoja de Ruta",
                ft.Icons.LOCAL_SHIPPING,
                lambda _e: gestionar_hoja_ruta_cierre(interfaz, cierre_obj, hoja_ruta),
            ),
        )

    dlg_detalle = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.RECEIPT_LONG, color=ROJO),
                ft.Column(
                    [
                        ft.Text(f"Pedidos del Cierre #{cierre_obj.id}", weight=ft.FontWeight.BOLD, size=16),
                        ft.Text(
                            f"Operario: {cierre_obj.usuario} · Fecha: {cierre_obj.created_at[:16]} · {len(peds)} pedidos ({total_bultos} bultos · {total_unid} unidades)",
                            size=11,
                            color=interfaz.secundario,
                        ),
                    ],
                    spacing=2,
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=680,
            height=440,
            content=lista_pedidos_ctrl,
        ),
        actions=acciones,
    )
    interfaz.page.show_dialog(dlg_detalle)


def mostrar_dialogo_cierres_operarios(interfaz: Any) -> None:
    """Abre el panel para que el administrador visualice en orden descendente los cierres creados por los operarios."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("administrador", "master"):
        interfaz.notificar("La consulta de cierres de operarios es exclusiva del rol administrador.")
        return

    # Obtener cierres de la base de datos (orden descendente por ID y fecha)
    todos_los_cierres = interfaz.order_store.listar_cierres(limit=250)
    todos_los_cierres.sort(key=lambda c: c.id, reverse=True)

    lista_cierres = ft.ListView(expand=True, spacing=8)
    total_cierres_lbl = ft.Text("0", weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto)
    total_pedidos_lbl = ft.Text("0", weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto)
    total_unidades_lbl = ft.Text("0", weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto)

    def renderizar_lista(filtro: str = "") -> None:
        q = (filtro or "").strip().lower()
        lista_cierres.controls.clear()

        filtrados = [
            c for c in todos_los_cierres
            if not q or (
                q in str(c.id).lower()
                or q in f"#{c.id}".lower()
                or q in (c.usuario or "").lower()
                or q in (c.created_at or "").lower()
                or q in (c.resumen_pedidos or "").lower()
            )
        ]

        total_cierres_lbl.value = str(len(filtrados))
        total_pedidos_lbl.value = str(sum(c.cantidad_pedidos for c in filtrados))
        total_unidades_lbl.value = str(sum(c.articulos_totales for c in filtrados))

        if not filtrados:
            lista_cierres.controls.append(
                ft.Container(
                    bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_100,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.INBOX, size=36, color=interfaz.secundario),
                            ft.Text(
                                "No se encontraron cierres que coincidan con la búsqueda." if q else "Aún no se han ejecutado cierres de jornada por parte de los operarios.",
                                size=13,
                                color=interfaz.secundario,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                )
            )
        else:
            for c in filtrados:
                pdf_ruta, xls_ruta, hoja_ruta = resolver_archivos_cierre(interfaz, c)

                boton_ver_pedidos = ft.Button(
                    content=f"Ver Pedidos ({c.cantidad_pedidos})",
                    icon=ft.Icons.LIST_ALT,
                    bgcolor=ft.Colors.BLUE_900 if interfaz.modo_oscuro else ft.Colors.BLUE_50,
                    color=ft.Colors.BLUE_200 if interfaz.modo_oscuro else ft.Colors.BLUE_800,
                    on_click=lambda _e, cierre_obj=c: mostrar_detalle_pedidos_cierre(interfaz, cierre_obj),
                )

                boton_hoja_ruta = ft.IconButton(
                    icon=ft.Icons.LOCAL_SHIPPING,
                    tooltip="Ver / Imprimir Hoja de Ruta de Despacho",
                    icon_color=ft.Colors.TEAL_400 if interfaz.modo_oscuro else ft.Colors.TEAL_700,
                    on_click=lambda _e, cierre_obj=c, hr_path=hoja_ruta: gestionar_hoja_ruta_cierre(interfaz, cierre_obj, hr_path),
                )

                boton_pdf = (
                    ft.IconButton(
                        icon=ft.Icons.PICTURE_AS_PDF,
                        tooltip="Abrir / Imprimir PDF del cierre",
                        icon_color=ROJO,
                        on_click=lambda _e, r=pdf_ruta: interfaz.abrir_informe(ruta_especifica=r),
                    )
                    if (pdf_ruta and pdf_ruta.exists())
                    else ft.Container()
                )

                boton_excel = (
                    ft.IconButton(
                        icon=ft.Icons.TABLE_CHART,
                        tooltip="Abrir planilla Excel del cierre",
                        icon_color=ft.Colors.GREEN_400 if interfaz.modo_oscuro else ft.Colors.GREEN_700,
                        on_click=lambda _e, r=xls_ruta: interfaz.abrir_informe(ruta_especifica=r),
                    )
                    if (xls_ruta and xls_ruta.exists())
                    else ft.Container()
                )

                boton_correo = (
                    ft.IconButton(
                        icon=ft.Icons.EMAIL_OUTLINED,
                        tooltip="Enviar comprobantes de este cierre por correo",
                        icon_color=ft.Colors.BLUE_400,
                        on_click=lambda _e, cid=c.id, pdf=pdf_ruta, xls=xls_ruta, res=c.resumen_pedidos, usr=c.usuario, hr=hoja_ruta: (
                            interfaz.mostrar_dialogo_compartir_cierre(cid, pdf, xls, res, usr, hr)
                        ),
                    )
                    if ((pdf_ruta and pdf_ruta.exists()) or (xls_ruta and xls_ruta.exists()) or (hoja_ruta and hoja_ruta.exists()))
                    else ft.Container()
                )

                lista_cierres.controls.append(
                    ft.Container(
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
                        border=ft.Border.all(1, interfaz.borde),
                        border_radius=8,
                        padding=12,
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Row(
                                            [
                                                ft.Container(
                                                    content=ft.Text(f"Cierre #{c.id}", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.WHITE),
                                                    bgcolor=ROJO,
                                                    border_radius=4,
                                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                                ),
                                                ft.Container(
                                                    content=ft.Row(
                                                        [
                                                            ft.Icon(ft.Icons.PERSON, size=14, color=ft.Colors.AMBER_400 if interfaz.modo_oscuro else ft.Colors.AMBER_800),
                                                            ft.Text(f"Operario: {c.usuario}", size=12, weight=ft.FontWeight.W_600, color=interfaz.texto),
                                                        ],
                                                        spacing=4,
                                                    ),
                                                    bgcolor=interfaz.superficie,
                                                    border=ft.Border.all(1, interfaz.borde),
                                                    border_radius=4,
                                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                                ),
                                                ft.Text(f"📅 {c.created_at[:16]}", size=11, color=interfaz.secundario),
                                            ],
                                            spacing=8,
                                            wrap=True,
                                        ),
                                        ft.Row(
                                            [
                                                boton_ver_pedidos,
                                                boton_hoja_ruta,
                                                boton_pdf,
                                                boton_excel,
                                                boton_correo,
                                            ],
                                            spacing=2,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Divider(height=8, color=interfaz.borde),
                                ft.Row(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.INVENTORY_2, size=14, color=ft.Colors.BLUE_400),
                                                ft.Text(f"{c.cantidad_pedidos} pedidos", size=12, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                                ft.Text("·", color=interfaz.secundario),
                                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=14, color=ft.Colors.GREEN_400),
                                                ft.Text(f"{c.articulos_totales} unidades", size=12, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                            ],
                                            spacing=6,
                                        ),
                                        ft.Text(
                                            f"Resumen: {c.resumen_pedidos}",
                                            size=11,
                                            color=interfaz.secundario,
                                            no_wrap=True,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            expand=True,
                                        ) if c.resumen_pedidos else ft.Container(),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                            ],
                            spacing=6,
                        ),
                    )
                )

        if interfaz.page:
            interfaz.page.update()

    filtro_input = ft.TextField(
        hint_text="Filtrar por operario, # cierre o fecha...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
        border_radius=8,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        on_change=lambda e: renderizar_lista(e.control.value),
    )

    def recargar_cierres(_e: ft.Event) -> None:
        nonlocal todos_los_cierres
        todos_los_cierres = interfaz.order_store.listar_cierres(limit=250)
        todos_los_cierres.sort(key=lambda c: c.id, reverse=True)
        renderizar_lista(filtro_input.value)

    boton_recargar = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip="Actualizar lista de cierres",
        icon_color=interfaz.texto,
        on_click=recargar_cierres,
    )

    renderizar_lista("")

    def _chip_metrica(titulo: str, control_val: ft.Text, icono: ft.IconData) -> ft.Container:
        return ft.Container(
            bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_100,
            border=ft.Border.all(1, interfaz.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            content=ft.Row(
                [
                    ft.Icon(icono, size=16, color=ROJO),
                    ft.Column(
                        [
                            ft.Text(titulo, size=10, color=interfaz.secundario),
                            control_val,
                        ],
                        spacing=1,
                    ),
                ],
                spacing=8,
            ),
        )

    barra_metricas = ft.Row(
        [
            _chip_metrica("Total Cierres", total_cierres_lbl, ft.Icons.FACT_CHECK),
            _chip_metrica("Pedidos Consolidados", total_pedidos_lbl, ft.Icons.INVENTORY_2),
            _chip_metrica("Unidades Descontadas", total_unidades_lbl, ft.Icons.CHECK_CIRCLE),
            ft.Container(
                bgcolor=interfaz.superficie,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.ARROW_DOWNWARD, size=16, color=ft.Colors.GREEN_400),
                        ft.Text("Orden: Descendente", size=11, weight=ft.FontWeight.W_500, color=interfaz.secundario),
                    ],
                    spacing=4,
                ),
            ),
        ],
        spacing=8,
        wrap=True,
    )

    cuerpo = ft.Column(
        [
            barra_metricas,
            ft.Row([filtro_input, boton_recargar], spacing=8),
            ft.Divider(height=6, color=interfaz.borde),
            ft.Container(content=lista_cierres, expand=True),
        ],
        spacing=10,
        expand=True,
    )

    ancho_modal = 420 if getattr(interfaz, "es_pantalla_movil", False) else 800
    alto_modal = 520 if getattr(interfaz, "es_pantalla_movil", False) else 540

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.FACT_CHECK, color=ROJO, size=24),
                ft.Column(
                    [
                        ft.Text("Cierres de Operarios (Descendente)", weight=ft.FontWeight.BOLD, size=16),
                        ft.Text("Control y auditoría de jornadas finalizadas por los operarios", size=11, color=interfaz.secundario),
                    ],
                    spacing=2,
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(
            width=ancho_modal,
            height=alto_modal,
            content=cuerpo,
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())
        ],
    )
    interfaz.page.show_dialog(dialogo)

