"""Tarjetas y vista de detalle para la auditoría administrativa de cierres de operarios."""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ...design import fila_cabecera_responsiva
from ...theme import ROJO
from .cierre_reportes_helper import generar_reporte_admin_para_cierre
from .hoja_ruta import gestionar_hoja_ruta_cierre, resolver_archivos_cierre


def construir_chip_metrica_cierre(
    interfaz: Any,
    titulo: str,
    control_val: ft.Text,
    icono: ft.IconData,
) -> ft.Container:
    """Construye una tarjeta KPI compacta para la barra de métricas de cierres."""
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
                        ft.Text(titulo, size=10, color=interfaz.secundario, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        control_val,
                    ],
                    spacing=1,
                    expand=True,
                ),
            ],
            spacing=8,
        ),
    )


def construir_estado_vacio_cierres(interfaz: Any, tiene_filtro: bool) -> ft.Container:
    """Construye el placeholder cuando no hay cierres registrados o coincidentes."""
    mensaje = (
        "No se encontraron cierres que coincidan con la búsqueda."
        if tiene_filtro
        else "Aún no se han ejecutado cierres de jornada por parte de los operarios."
    )
    return ft.Container(
        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_100,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=24,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Icon(ft.Icons.INBOX, size=36, color=interfaz.secundario),
                ft.Text(mensaje, size=13, color=interfaz.secundario, weight=ft.FontWeight.W_500),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )


def _construir_tarjeta_pedido_detalle_cierre(interfaz: Any, pedido: Any) -> ft.Container:
    """Renderiza una tarjeta de pedido individual dentro del modal de detalle de un cierre."""
    num_ped_txt = (
        f"Pedido #{pedido.numero_pedido}"
        if getattr(pedido, "numero_pedido", "")
        else f"Remito: {pedido.nota_pedido}"
    )
    st_despacho = getattr(pedido, "estado_despacho", "") or "Preparado"
    badge_color = (
        ft.Colors.BLUE_400
        if st_despacho == "Preparado"
        else (ft.Colors.AMBER_400 if st_despacho == "Despachado" else ft.Colors.GREEN_400)
    )

    return ft.Container(
        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=10,
        content=ft.Column(
            [
                fila_cabecera_responsiva(
                    ft.Row(
                        [
                            ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                            ft.Text(f"· Remito: {pedido.nota_pedido}", size=11, color=interfaz.secundario)
                            if getattr(pedido, "numero_pedido", "")
                            else ft.Container(),
                            ft.Container(
                                content=ft.Text(st_despacho, size=10, weight=ft.FontWeight.BOLD, color=badge_color),
                                bgcolor=ft.Colors.with_opacity(0.12, badge_color),
                                border_radius=4,
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                            ),
                        ],
                        spacing=8,
                        wrap=True,
                        run_spacing=4,
                        tight=True,
                    ),
                    ft.Text(f"Armado: {pedido.created_at[:16]}", size=10, color=interfaz.secundario),
                    spacing=8,
                    run_spacing=4,
                ),
                ft.Row(
                    [
                        ft.Text(f"👤 Cliente: {pedido.cliente}", size=11, color=interfaz.texto, weight=ft.FontWeight.W_500),
                        ft.Text(f"📦 Bultos: {pedido.bultos}", size=11, color=interfaz.secundario),
                        ft.Text(f"🚚 Logística: {pedido.logistica or 'Sin especificar'}", size=11, color=interfaz.secundario),
                        ft.Text(f"🔢 Unid: {pedido.articulos_descontados}", size=11, color=ROJO, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=12,
                    wrap=True,
                ),
                ft.Text(
                    f"Detalle ítems: {pedido.resumen_items}",
                    size=11,
                    color=interfaz.secundario,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
                if getattr(pedido, "resumen_items", "")
                else ft.Container(),
            ],
            spacing=4,
        ),
    )


def mostrar_detalle_pedidos_cierre(interfaz: Any, cierre_obj: Any) -> None:
    """Muestra un modal detallado con la lista de pedidos consolidados en un cierre de jornada específico."""
    peds = interfaz.order_store.obtener_pedidos_por_cierre(cierre_obj.id)
    _pdf_ruta, _xls_ruta, hoja_ruta = resolver_archivos_cierre(interfaz, cierre_obj)

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
        for pedido in peds:
            lista_pedidos_ctrl.controls.append(_construir_tarjeta_pedido_detalle_cierre(interfaz, pedido))

    total_bultos = sum(p.bultos for p in peds)
    total_unid = sum(p.articulos_descontados for p in peds)

    acciones: list[ft.Control] = [
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

    ancho_det = interfaz.ancho_adaptable(680) if hasattr(interfaz, "ancho_adaptable") else 680
    alto_det = interfaz.alto_adaptable(440) if hasattr(interfaz, "alto_adaptable") else 440
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
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
        content=ft.Container(width=ancho_det, height=alto_det, content=lista_pedidos_ctrl),
        actions=acciones,
    )
    interfaz.page.show_dialog(dlg_detalle)


def construir_tarjeta_cierre_admin(
    interfaz: Any,
    cierre: Any,
    *,
    on_ver_pedidos: Callable[[Any], None],
) -> ft.Container:
    """Construye la tarjeta responsiva de un cierre de jornada en el panel de administración."""
    pdf_ruta, xls_ruta, hoja_ruta = resolver_archivos_cierre(interfaz, cierre)

    boton_ver_pedidos = ft.Button(
        content=f"Ver Pedidos ({cierre.cantidad_pedidos})",
        icon=ft.Icons.LIST_ALT,
        bgcolor=ft.Colors.BLUE_900 if interfaz.modo_oscuro else ft.Colors.BLUE_50,
        color=ft.Colors.BLUE_200 if interfaz.modo_oscuro else ft.Colors.BLUE_800,
        on_click=lambda _e, cierre_obj=cierre: on_ver_pedidos(cierre_obj),
    )
    boton_hoja_ruta = ft.IconButton(
        icon=ft.Icons.LOCAL_SHIPPING,
        tooltip="Ver / Imprimir Hoja de Ruta de Despacho",
        icon_color=ft.Colors.TEAL_400 if interfaz.modo_oscuro else ft.Colors.TEAL_700,
        on_click=lambda _e, cierre_obj=cierre, hr_path=hoja_ruta: gestionar_hoja_ruta_cierre(interfaz, cierre_obj, hr_path),
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

    def _abrir_consolidado_admin(_e: ft.Event, cierre_obj: Any = cierre) -> None:
        try:
            ruta_admin = generar_reporte_admin_para_cierre(interfaz, cierre_obj, formato="pdf")
            interfaz.abrir_informe(ruta_especifica=ruta_admin)
        except Exception as exc_adm:
            interfaz.notificar(f"No se pudo generar consolidado administrador: {exc_adm}")

    boton_admin_consolidado = ft.IconButton(
        icon=ft.Icons.SUMMARIZE,
        tooltip="Reporte Consolidado Administrador (Suma total por producto)",
        icon_color=ft.Colors.INDIGO_300 if interfaz.modo_oscuro else ft.Colors.INDIGO_700,
        on_click=_abrir_consolidado_admin,
    )
    boton_correo = (
        ft.IconButton(
            icon=ft.Icons.EMAIL_OUTLINED,
            tooltip="Enviar comprobantes de este cierre por correo",
            icon_color=ft.Colors.BLUE_400,
            on_click=lambda _e, cid=cierre.id, pdf=pdf_ruta, xls=xls_ruta, res=cierre.resumen_pedidos, usr=cierre.usuario, hr=hoja_ruta: (
                interfaz.mostrar_dialogo_compartir_cierre(cid, pdf, xls, res, usr, hr)
            ),
        )
        if ((pdf_ruta and pdf_ruta.exists()) or (xls_ruta and xls_ruta.exists()) or (hoja_ruta and hoja_ruta.exists()))
        else ft.Container()
    )

    return ft.Container(
        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
        border=ft.Border.all(1, interfaz.borde),
        border_radius=8,
        padding=12,
        content=ft.Column(
            [
                fila_cabecera_responsiva(
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(f"Cierre #{cierre.id}", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.WHITE),
                                bgcolor=ROJO,
                                border_radius=4,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            ),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.PERSON, size=14, color=ft.Colors.AMBER_400 if interfaz.modo_oscuro else ft.Colors.AMBER_800),
                                        ft.Text(f"Operario: {cierre.usuario}", size=12, weight=ft.FontWeight.W_600, color=interfaz.texto),
                                    ],
                                    spacing=4,
                                    tight=True,
                                ),
                                bgcolor=interfaz.superficie,
                                border=ft.Border.all(1, interfaz.borde),
                                border_radius=4,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            ),
                            ft.Text(f"📅 {cierre.created_at[:16]}", size=11, color=interfaz.secundario),
                        ],
                        spacing=8,
                        wrap=True,
                        run_spacing=4,
                        tight=True,
                    ),
                    ft.Row(
                        [
                            boton_ver_pedidos,
                            boton_admin_consolidado,
                            boton_hoja_ruta,
                            boton_pdf,
                            boton_excel,
                            boton_correo,
                        ],
                        spacing=2,
                        wrap=True,
                        run_spacing=4,
                        tight=True,
                    ),
                    spacing=8,
                    run_spacing=6,
                ),
                ft.Divider(height=8, color=interfaz.borde),
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.INVENTORY_2, size=14, color=ft.Colors.BLUE_400),
                                ft.Text(f"{cierre.cantidad_pedidos} pedidos", size=12, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                ft.Text("·", color=interfaz.secundario),
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=14, color=ft.Colors.GREEN_400),
                                ft.Text(f"{cierre.articulos_totales} unidades", size=12, weight=ft.FontWeight.W_500, color=interfaz.texto),
                            ],
                            spacing=6,
                        ),
                        ft.Text(
                            f"Resumen: {cierre.resumen_pedidos}",
                            size=11,
                            color=interfaz.secundario,
                            no_wrap=True,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        )
                        if cierre.resumen_pedidos
                        else ft.Container(),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=6,
        ),
    )
