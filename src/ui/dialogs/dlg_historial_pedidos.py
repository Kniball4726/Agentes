"""Diálogos de historial de pedidos e impresión de comprobantes de descuento."""

from pathlib import Path
from typing import Any, Callable

import flet as ft

from ..theme import ROJO
from ...orders_store import Pedido


def mostrar_historial_pedidos(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana completa con buscador y lista histórica de pedidos del depósito."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador", "master"):
        interfaz.notificar("No tienes permisos suficientes para acceder al historial de pedidos.")
        return

    pedidos = interfaz.order_store.listar_pedidos(limit=400)
    items_lista = ft.ListView(expand=True, spacing=8)

    def formatear_fecha_corta(f_str: str) -> str:
        try:
            partes = f_str.split("-")
            if len(partes) == 3:
                return f"{partes[2]}/{partes[1]}/{partes[0]}"
        except Exception:
            pass
        return f_str

    def coincide(p: Pedido, q: str) -> bool:
        if not q:
            return True
        q = q.lower().strip()
        if q in (p.cliente or "").lower():
            return True
        if q in (p.nota_pedido or "").lower():
            return True
        num_ped = str(getattr(p, "numero_pedido", "") or "").lower()
        if q in num_ped:
            return True
        if q in (p.armador or "").lower():
            return True
        if q in (p.logistica or "").lower():
            return True
        c_at = p.created_at or ""
        if q in c_at.lower():
            return True
        f_corta = formatear_fecha_corta(c_at[:10])
        if q in f_corta.lower():
            return True
        f_ret = str(getattr(p, "fecha_retiro", "") or "").lower()
        if q in f_ret:
            return True
        if q in (p.nombre_archivo or "").lower():
            return True
        return False

    texto_contador = ft.Text(f"Total: {len(pedidos)} pedidos" if pedidos else "", size=11, color=interfaz.secundario)

    def recargar_y_actualizar() -> None:
        nonlocal pedidos
        pedidos = interfaz.order_store.listar_pedidos(limit=400)
        actualizar_vista(campo_busqueda.value or "")

    def actualizar_vista(termino: str = "") -> None:
        filtrados = [p for p in pedidos if coincide(p, termino)]
        items_lista.controls.clear()

        if not filtrados:
            if not pedidos:
                items_lista.controls.append(
                    ft.Container(
                        padding=30,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text("Aún no se han registrado pedidos en el sistema.", color=interfaz.secundario, size=13),
                    )
                )
            else:
                items_lista.controls.append(
                    ft.Container(
                        padding=30,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.SEARCH_OFF, size=34, color=interfaz.secundario),
                                ft.Text(f"No se encontraron pedidos para '{termino}'.", color=interfaz.secundario, size=13),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                        ),
                    )
                )
            texto_contador.value = f"0 de {len(pedidos)} pedidos"
            if interfaz.page:
                interfaz.page.update()
            return

        texto_contador.value = (
            f"Mostrando {len(filtrados)} de {len(pedidos)} pedidos"
            if termino.strip()
            else f"Total: {len(pedidos)} pedidos"
        )

        pedidos_por_fecha: dict[str, list[Pedido]] = {}
        for p in filtrados:
            f_clave = p.created_at[:10] if p.created_at else "Sin fecha"
            pedidos_por_fecha.setdefault(f_clave, []).append(p)

        for f_clave, pedidos_grupo in pedidos_por_fecha.items():
            cant = len(pedidos_grupo)
            texto_cant = "1 pedido armado" if cant == 1 else f"{cant} pedidos armados"
            fecha_legible = formatear_fecha_corta(f_clave)

            encabezado_fecha = ft.Container(
                bgcolor=ft.Colors.BLUE_GREY_900 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_50,
                border=ft.Border.all(1, ft.Colors.BLUE_GREY_700 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_200),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                margin=ft.Margin.only(top=8, bottom=2),
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=ROJO),
                                ft.Text(f"Fecha: {fecha_legible}", weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                            ],
                            spacing=8,
                        ),
                        ft.Container(
                            content=ft.Text(texto_cant, size=11, weight=ft.FontWeight.W_500, color=ft.Colors.WHITE),
                            bgcolor=ROJO,
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=12,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            )
            items_lista.controls.append(encabezado_fecha)

            for p in pedidos_grupo:
                if getattr(p, "numero_pedido", ""):
                    num_ped_txt = f"Pedido #{p.numero_pedido} · Remito: {p.nota_pedido}"
                else:
                    num_ped_txt = f"Remito / Factura: {p.nota_pedido}"
                etiqueta_agregado = (
                    ft.Container(
                        content=ft.Text(
                            "AGREGADO",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.AMBER_800 if not interfaz.modo_oscuro else ft.Colors.AMBER_300,
                        ),
                        bgcolor=ft.Colors.AMBER_100 if not interfaz.modo_oscuro else ft.Colors.AMBER_900,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    )
                    if getattr(p, "agregado", False)
                    else ft.Container()
                )
                etiqueta_anulado = (
                    ft.Container(
                        content=ft.Text(
                            "ANULADO",
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE,
                        ),
                        bgcolor=ft.Colors.RED_600,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    )
                    if getattr(p, "estado", "") == "anulado"
                    else ft.Container()
                )
                est_desp = (getattr(p, "estado_despacho", "armado") or "armado").lower()
                if est_desp == "entregado":
                    col_desp_bg, col_desp_txt, lbl_desp = ft.Colors.GREEN_700, ft.Colors.WHITE, "✔ ENTREGADO"
                    sig_estado = "armado"
                    tip_estado = "Estado actual: Entregado (clic para volver a Armado)"
                elif est_desp == "despachado":
                    col_desp_bg, col_desp_txt, lbl_desp = ft.Colors.AMBER_700, ft.Colors.WHITE, "🚚 DESPACHADO"
                    sig_estado = "entregado"
                    tip_estado = "Marcar como ENTREGADO"
                else:
                    col_desp_bg, col_desp_txt, lbl_desp = ft.Colors.BLUE_700, ft.Colors.WHITE, "📦 ARMADO"
                    sig_estado = "despachado"
                    tip_estado = "Marcar como DESPACHADO"

                etiqueta_despacho = (
                    ft.Container(
                        content=ft.Text(lbl_desp, size=10, weight=ft.FontWeight.BOLD, color=col_desp_txt),
                        bgcolor=col_desp_bg,
                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        border_radius=4,
                    )
                    if getattr(p, "estado", "") != "anulado"
                    else ft.Container()
                )
                hora_txt = p.created_at[11:16] if len(p.created_at) >= 16 else p.created_at

                def cambiar_estado_ped(ped_obj: Pedido, nuevo_est: str) -> None:
                    usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
                    try:
                        interfaz.order_store.actualizar_estado_despacho(
                            ped_obj.id,
                            nuevo_est,
                            usuario=usr,
                            permitir_retroceso=True,
                        )
                        recargar_y_actualizar()
                        interfaz.sincronizar_sesiones()
                    except Exception as err:
                        interfaz.notificar(str(err))

                boton_avanzar_desp = (
                    ft.IconButton(
                        icon=ft.Icons.LOCAL_SHIPPING if est_desp == "armado" else (ft.Icons.VERIFIED if est_desp == "despachado" else ft.Icons.REPLAY),
                        tooltip=tip_estado,
                        icon_color=ft.Colors.GREEN_400 if est_desp == "despachado" else ft.Colors.BLUE_400,
                        on_click=lambda _e, ped=p, st=sig_estado: cambiar_estado_ped(ped, st),
                    )
                    if getattr(p, "estado", "") != "anulado"
                    else ft.Container()
                )
                boton_rotulo_hist = ft.IconButton(
                    icon=ft.Icons.QR_CODE_2,
                    tooltip="Imprimir Rótulos de Bultos con QR",
                    icon_color=ft.Colors.AMBER_700 if not interfaz.modo_oscuro else ft.Colors.AMBER_400,
                    on_click=lambda _e, ped=p: interfaz.imprimir_rotulos_pedido(ped),
                )
                boton_editar_hist = (
                    ft.IconButton(
                        icon=ft.Icons.EDIT_OUTLINED,
                        tooltip="Modificar datos del pedido",
                        icon_color=ft.Colors.BLUE_400 if interfaz.modo_oscuro else ft.Colors.BLUE_700,
                        on_click=lambda _e, ped=p: interfaz.mostrar_dialogo_editar_pedido(ped, al_final=recargar_y_actualizar),
                    )
                    if (interfaz.usuario_actual and interfaz.usuario_actual.role in ("operador", "administrador", "master") and p.estado != "anulado")
                    else ft.Container()
                )
                boton_desarmar_hist = (
                    ft.IconButton(
                        icon=ft.Icons.REMOVE_SHOPPING_CART_OUTLINED,
                        tooltip="Desarmar pedido y devolver stock a inventario",
                        icon_color=ft.Colors.AMBER_400 if interfaz.modo_oscuro else ft.Colors.AMBER_800,
                        on_click=lambda _e, ped=p: interfaz.confirmar_desarmar_pedido(ped, al_final=recargar_y_actualizar),
                    )
                    if (interfaz.usuario_actual and interfaz.usuario_actual.role in ("operador", "administrador", "master") and p.estado != "anulado")
                    else ft.Container()
                )
                boton_anular_hist = (
                    ft.IconButton(
                        icon=ft.Icons.CANCEL_OUTLINED,
                        tooltip="Anular este pedido",
                        icon_color=ft.Colors.RED_400,
                        on_click=lambda _e, ped=p: interfaz.confirmar_anulacion_pedido(ped, al_final=recargar_y_actualizar),
                    )
                    if (interfaz.usuario_actual and interfaz.usuario_actual.role in ("administrador", "master") and p.estado != "anulado")
                    else ft.Container()
                )

                items_lista.controls.append(
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
                                                ft.Row(
                                                    [
                                                        ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto),
                                                        etiqueta_despacho,
                                                        etiqueta_agregado,
                                                        etiqueta_anulado,
                                                    ],
                                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                    spacing=8,
                                                ),
                                                ft.Text(f"Hora: {hora_txt}", size=11, color=interfaz.secundario),
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        ),
                                        ft.Row(
                                            [
                                                ft.Text(f"Cliente: {p.cliente}", size=12, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                                ft.Text(f"Logística: {p.logistica}", size=12, color=interfaz.secundario),
                                                ft.Text(f"Bultos: {p.bultos}", size=12, color=interfaz.secundario),
                                                *(
                                                    [ft.Text(f"Retiro: {p.fecha_retiro}", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.AMBER_400 if interfaz.modo_oscuro else ft.Colors.AMBER_800)]
                                                    if getattr(p, "fecha_retiro", "")
                                                    else []
                                                ),
                                            ],
                                            spacing=16,
                                        ),
                                        ft.Row(
                                            [
                                                ft.Text(f"Armador: {p.armador}", size=11, color=interfaz.secundario),
                                                ft.Text(f"Archivo: {p.nombre_archivo}", size=11, color=interfaz.secundario),
                                                ft.Text(f"Descuento: {p.resumen_items}", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREEN_400),
                                            ],
                                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        ),
                                    ],
                                    spacing=4,
                                    expand=True,
                                ),
                                ft.Row([boton_avanzar_desp, boton_rotulo_hist, boton_editar_hist, boton_desarmar_hist, boton_anular_hist], spacing=2),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )
        if interfaz.page:
            interfaz.page.update()

    campo_busqueda = ft.TextField(
        hint_text="Buscar por cliente, remito / nota, N° pedido, fecha (DD/MM/AAAA) o armador...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=interfaz.fondo,
        border_color=interfaz.borde,
        color=interfaz.texto,
        expand=True,
        on_change=lambda e: actualizar_vista(campo_busqueda.value or ""),
    )

    def limpiar_busqueda(_e: ft.Event) -> None:
        campo_busqueda.value = ""
        actualizar_vista("")

    barra_busqueda = ft.Row(
        [
            campo_busqueda,
            ft.IconButton(
                icon=ft.Icons.CLEAR,
                icon_size=18,
                icon_color=interfaz.secundario,
                tooltip="Borrar búsqueda",
                on_click=limpiar_busqueda,
            ),
            ft.Button(
                "Escanear QR / Cambiar Estado",
                icon=ft.Icons.QR_CODE_SCANNER,
                bgcolor=ROJO,
                color=ft.Colors.WHITE,
                on_click=lambda _e: interfaz.mostrar_escaner_qr_despacho(al_actualizar=recargar_y_actualizar),
            ),
        ],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    actualizar_vista("")

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.RECEIPT_LONG, color=ROJO, size=22),
                        ft.Text("Historial de Pedidos", weight=ft.FontWeight.BOLD),
                    ],
                    spacing=8,
                ),
                texto_contador,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        content=ft.Container(
            width=780,
            height=540,
            content=ft.Column(
                [
                    barra_busqueda,
                    ft.Divider(height=10, color=interfaz.borde),
                    items_lista,
                ],
                expand=True,
                spacing=6,
            ),
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())
        ],
    )
    interfaz.page.show_dialog(dialogo)


def mostrar_imprimir_descuentos(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana para consultar y reimprimir comprobantes PDF de descuentos procesados."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("La impresión de descuentos es una función exclusiva del rol operador.")
        return

    pedidos = interfaz.order_store.listar_pedidos(limit=200)

    todos_informes = interfaz.menu._obtener_generados()
    informes_descuento_pdf = [
        r for r in sorted(todos_informes, key=lambda x: x.stat().st_mtime_ns, reverse=True)
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
            if getattr(p, "numero_pedido", ""):
                num_ped_txt = f"Pedido #{p.numero_pedido} · Remito: {p.nota_pedido}"
            else:
                num_ped_txt = f"Remito / Factura: {p.nota_pedido}"

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
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.PRINT, color=ROJO),
                    ft.Text("Imprimir Descuentos de Pedidos", weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=680,
                height=480,
                content=items_contenido,
            ),
            actions=[
                interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())
            ],
        )
        interfaz.page.show_dialog(dialogo)
