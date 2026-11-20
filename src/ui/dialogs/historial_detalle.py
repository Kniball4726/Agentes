"""Vistas de detalle individual de pedido e impresión de descuentos recientes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import flet as ft

from ...orders import Pedido
from ..theme import ROJO
from .historial_archivos import (
    abrir_comprobante_pedido,
    abrir_descuento_pedido,
    buscar_archivo_comprobante,
    buscar_archivo_descuento,
)
from .dlg_email import compartir_whatsapp_pedido


def _icono_y_color_archivo(interfaz: Any, nombre_archivo: str) -> tuple[ft.IconData, str]:
    ext = Path(nombre_archivo).suffix.lower()
    if ext == ".pdf":
        return ft.Icons.PICTURE_AS_PDF, ROJO
    if ext in (".xlsx", ".xls"):
        return ft.Icons.TABLE_CHART, ft.Colors.GREEN_600 if not interfaz.modo_oscuro else ft.Colors.GREEN_400
    if ext in (".docx", ".doc"):
        return ft.Icons.DESCRIPTION, ft.Colors.BLUE_600 if not interfaz.modo_oscuro else ft.Colors.BLUE_400
    return ft.Icons.ATTACH_FILE, interfaz.secundario


def mostrar_detalle_pedido_modal(interfaz: Any, ped: Pedido) -> None:
    """Muestra un modal detallado del pedido con opciones de consulta y reimpresión de comprobante y rótulos."""
    if interfaz.usuario_actual and interfaz.usuario_actual.role == "master":
        interfaz.notificar("El usuario Master no tiene acceso a la visualización de pedidos operativos.")
        return
    if interfaz.usuario_actual and interfaz.usuario_actual.role == "picker":
        interfaz.notificar("El usuario Picker no tiene acceso a la visualización de pedidos operativos.")
        return
    if not interfaz.exigir_roles("operador", "administrador", "consulta"):
        return

    ruta_comprobante = buscar_archivo_comprobante(ped)
    ruta_descuento = buscar_archivo_descuento(ped)
    nombre_comprobante = ped.nombre_archivo or "Sin archivo adjunto"
    existe_comprobante = ruta_comprobante is not None and ruta_comprobante.exists()
    existe_descuento = ruta_descuento is not None and ruta_descuento.exists()
    icono_tipo, color_tipo = _icono_y_color_archivo(interfaz, nombre_comprobante)

    acciones_dialogo: list[ft.Control] = []
    if existe_comprobante:
        acciones_dialogo.append(
            interfaz.boton("Reimprimir Comprobante", ft.Icons.PRINT, lambda _e: abrir_comprobante_pedido(interfaz, ped))
        )
    acciones_dialogo.extend(
        [
            interfaz.boton("WhatsApp", ft.Icons.CHAT, lambda _e: compartir_whatsapp_pedido(interfaz, ped)),
            interfaz.boton("Rótulos QR", ft.Icons.QR_CODE_2, lambda _e: interfaz.imprimir_rotulos_pedido(ped)),
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog()),
        ]
    )

    fila_archivo = ft.Row(
        [
            ft.Icon(icono_tipo, color=color_tipo, size=20),
            ft.Column(
                [
                    ft.Text(f"Archivo Cargado: {nombre_comprobante}", weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                    ft.Text(
                        "Listo para consultar o reimprimir" if existe_comprobante else "Archivo no disponible localmente",
                        size=11,
                        color=ft.Colors.GREEN_400 if existe_comprobante else ft.Colors.AMBER_400,
                    ),
                ],
                spacing=2,
                expand=True,
            ),
            *(
                [
                    ft.Button(
                        "Abrir / Reimprimir",
                        icon=ft.Icons.OPEN_IN_NEW,
                        bgcolor=color_tipo,
                        color=ft.Colors.WHITE,
                        on_click=lambda _e: abrir_comprobante_pedido(interfaz, ped),
                    )
                ]
                if existe_comprobante
                else []
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    fila_informe: ft.Control = ft.Container()
    if getattr(ped, "archivo_descuento", ""):
        fila_informe = ft.Container(
            padding=ft.Padding.symmetric(vertical=4),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ASSESSMENT_OUTLINED, color=ft.Colors.GREEN_400, size=18),
                    ft.Text(f"Informe de Descuento: {ped.archivo_descuento}", size=12, color=interfaz.texto, expand=True),
                    *(
                        [ft.TextButton("Ver informe", icon=ft.Icons.VISIBILITY, on_click=lambda _e: abrir_descuento_pedido(interfaz, ped))]
                        if existe_descuento
                        else []
                    ),
                ],
                spacing=8,
            ),
        )

    dialogo_detalle = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Icon(ft.Icons.RECEIPT_LONG, color=ROJO),
                ft.Text(f"Pedido #{ped.numero_pedido or ped.id} · {ped.cliente}", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=620,
            content=ft.Column(
                [
                    ft.Container(
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_100,
                        border_radius=8,
                        padding=12,
                        content=fila_archivo,
                    ),
                    fila_informe,
                    ft.Divider(height=10, color=interfaz.borde),
                    ft.Row(
                        [
                            ft.Text(f"Remito: {ped.nota_pedido}", size=12, color=interfaz.secundario),
                            ft.Text(f"Armador: {ped.armador}", size=12, color=interfaz.secundario),
                            ft.Text(f"Logística: {ped.logistica}", size=12, color=interfaz.secundario),
                            ft.Text(f"Bultos: {ped.bultos}", size=12, color=interfaz.secundario),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            ft.Text(f"Cargado el: {ped.created_at[:16]}", size=12, color=interfaz.secundario),
                            ft.Text(f"Estado despacho: {ped.estado_despacho.upper()}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400),
                            *(
                                [ft.Text(f"Retiro: {ped.fecha_retiro}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400)]
                                if getattr(ped, "fecha_retiro", "")
                                else []
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(height=10, color=interfaz.borde),
                    ft.Text("Artículos Descontados:", weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                    ft.Container(
                        bgcolor=interfaz.fondo if interfaz.modo_oscuro else ft.Colors.WHITE,
                        border=ft.Border.all(1, interfaz.borde),
                        border_radius=8,
                        padding=10,
                        height=160,
                        content=ft.ListView(
                            controls=[ft.Text(ped.resumen_items or "Sin detalle de artículos registrado.", size=12, color=interfaz.texto)],
                            spacing=4,
                        ),
                    ),
                ],
                tight=True,
                spacing=8,
            ),
        ),
        actions=acciones_dialogo,
    )
    interfaz.page.show_dialog(dialogo_detalle)


def mostrar_imprimir_descuentos(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para consultar y reimprimir comprobantes PDF de descuentos procesados."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("La impresión de descuentos es una función exclusiva del rol operador.")
        return

    pedidos = interfaz.order_store.listar_pedidos(limit=200)
    todos_informes = interfaz.menu._obtener_generados()
    informes_descuento_pdf = [
        r
        for r in sorted(todos_informes, key=lambda x: x.stat().st_mtime_ns, reverse=True)
        if r.name.startswith("Descuento") and r.suffix.lower() == ".pdf"
    ]
    ultimo_pdf: Path | None = informes_descuento_pdf[0] if informes_descuento_pdf else None

    items_contenido = ft.ListView(expand=True, spacing=10)
    if ultimo_pdf:
        items_contenido.controls.append(
            ft.Container(
                bgcolor=ROJO,
                border_radius=8,
                padding=12,
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("ÚLTIMO DESCUENTO GENERADO", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE_70),
                                ft.Text(ultimo_pdf.name, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Button(
                            "Imprimir / Abrir PDF",
                            icon=ft.Icons.PRINT,
                            bgcolor=ft.Colors.WHITE,
                            color=ROJO,
                            on_click=lambda _e, r=ultimo_pdf: interfaz.abrir_informe(ruta_especifica=r),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    items_contenido.controls.append(
        ft.Text("Lista de Pedidos Descontados", size=14, weight=ft.FontWeight.BOLD, color=interfaz.texto)
    )

    if not pedidos:
        items_contenido.controls.append(
            ft.Text("Aún no hay pedidos descontados para mostrar o imprimir.", color=interfaz.secundario, size=13)
        )
    else:
        for p in pedidos:
            num_ped_txt = (
                f"Pedido #{p.numero_pedido} · Remito: {p.nota_pedido}"
                if getattr(p, "numero_pedido", "")
                else f"Remito / Factura: {p.nota_pedido}"
            )
            pdf_archivo: Path | None = None
            if getattr(p, "archivo_descuento", ""):
                candidato = interfaz.menu.carpeta_descuentos / p.archivo_descuento
                if candidato.exists():
                    pdf_archivo = candidato
            if not pdf_archivo and ultimo_pdf:
                pdf_archivo = ultimo_pdf

            boton_rotulo = ft.IconButton(
                icon=ft.Icons.QR_CODE_2,
                tooltip="Imprimir Rótulos de Bultos con QR",
                icon_color=ft.Colors.AMBER_700 if not interfaz.modo_oscuro else ft.Colors.AMBER_400,
                on_click=lambda _e, ped=p: interfaz.imprimir_rotulos_pedido(ped),
            )
            boton_imprimir = (
                ft.IconButton(
                    icon=ft.Icons.PRINT,
                    tooltip="Abrir / Imprimir informe PDF de este descuento",
                    icon_color=ROJO,
                    on_click=(lambda _e, r=pdf_archivo: interfaz.abrir_informe(ruta_especifica=r)) if pdf_archivo else None,
                )
                if pdf_archivo
                else ft.Container()
            )
            items_contenido.controls.append(
                ft.Container(
                    bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
                    border=ft.Border.all(1, interfaz.borde),
                    border_radius=8,
                    padding=10,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                                            ft.Text(f"Cliente: {p.cliente}", size=12, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                        ],
                                        spacing=12,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Text(f"Logística: {p.logistica}", size=11, color=interfaz.secundario),
                                            ft.Text(f"Bultos: {p.bultos}", size=11, color=interfaz.secundario),
                                            ft.Text(f"Descuento: {p.resumen_items}", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREEN_400),
                                            ft.Text(f"Fecha: {p.created_at[:16]}", size=11, color=interfaz.secundario),
                                        ],
                                        spacing=12,
                                    ),
                                ],
                                spacing=4,
                                expand=True,
                            ),
                            ft.Row([boton_rotulo, boton_imprimir], spacing=2),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )

    dialogo = ft.AlertDialog(
        title=ft.Row([ft.Icon(ft.Icons.PRINT, color=ROJO), ft.Text("Imprimir Descuentos de Pedidos", weight=ft.FontWeight.BOLD)], spacing=8),
        content=ft.Container(width=680, height=480, content=items_contenido),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
