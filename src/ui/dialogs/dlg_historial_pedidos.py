from datetime import datetime
"""Diálogos de historial de pedidos e impresión de comprobantes de descuento."""

from pathlib import Path
from typing import Any, Callable

import flet as ft

from ..theme import ROJO
from ...orders_store import Pedido
from ...paths import application_root


def buscar_archivo_comprobante(pedido: Pedido) -> Path | None:
    """Busca en el servidor la ruta física del comprobante original cargado para un pedido."""
    nombre = (pedido.nombre_archivo or "").strip()
    if not nombre or nombre.lower() in ("sin archivo", "ninguno", "-", "none"):
        return None

    root = application_root()
    candidatos = [
        root / "data" / "pedidos_archivos" / nombre,
        root / "data" / "descontados" / nombre,
        root / "data" / "descontados" / "mayoristas" / nombre,
        root / "data" / "descontados" / "canjes" / nombre,
        root / "data" / "descontados" / "mercado_libre" / nombre,
        root / "data" / "pendientes" / nombre,
        root / "data" / "pendientes" / "mayoristas" / nombre,
        root / "data" / "pendientes" / "canjes" / nombre,
        root / "data" / "pendientes" / "mercado_libre" / nombre,
        root / "Descuentos" / nombre,
        root / "data" / "informes" / nombre,
    ]
    for c in candidatos:
        if c.exists() and c.is_file():
            return c

    pedidos_dir = root / "data" / "pedidos_archivos"
    if pedidos_dir.exists():
        for f in pedidos_dir.glob("*"):
            if f.is_file() and f.name.lower() == nombre.lower():
                return f

    desc_dir = root / "data" / "descontados"
    if desc_dir.exists():
        for f in desc_dir.rglob("*"):
            if f.is_file() and f.name.lower() == nombre.lower():
                return f

    hist_dir = root / "data" / "historico"
    if hist_dir.exists():
        for f in hist_dir.rglob("*"):
            if f.is_file() and f.name.lower() == nombre.lower():
                return f

    return None


def buscar_archivo_descuento(pedido: Pedido) -> Path | None:
    """Busca la ruta del informe de descuento asociado a un pedido."""
    nombre = (getattr(pedido, "archivo_descuento", "") or "").strip()
    if not nombre or nombre.lower() in ("sin archivo", "ninguno", "-", "none"):
        return None

    root = application_root()
    candidatos = [
        root / "Descuentos" / nombre,
        root / "data" / "informes" / nombre,
        root / "data" / "pedidos_archivos" / nombre,
    ]
    for c in candidatos:
        if c.exists() and c.is_file():
            return c

    descuentos_dir = root / "Descuentos"
    if descuentos_dir.exists():
        for f in descuentos_dir.glob("*"):
            if f.is_file() and f.name.lower() == nombre.lower():
                return f

    hist_dir = root / "data" / "historico"
    if hist_dir.exists():
        for f in hist_dir.rglob("*"):
            if f.is_file() and f.name.lower() == nombre.lower():
                return f

    return None


def abrir_comprobante_pedido(interfaz: Any, ped: Pedido) -> None:
    """Abre el archivo original cargado para consulta o reimpresión."""
    ruta = buscar_archivo_comprobante(ped)
    if ruta is None or not ruta.exists():
        interfaz.notificar(
            f"El archivo cargado '{ped.nombre_archivo}' no se encuentra actualmente en el servidor.\n"
            "Es posible que haya sido archivado o movido a una copia de seguridad externa."
        )
        return
    interfaz.abrir_informe(ruta_especifica=ruta)


def abrir_descuento_pedido(interfaz: Any, ped: Pedido) -> None:
    """Abre el informe de descuento asociado al pedido."""
    ruta = buscar_archivo_descuento(ped)
    if ruta is None or not ruta.exists():
        interfaz.notificar(
            f"El informe de descuento '{ped.archivo_descuento}' no se encuentra en el servidor."
        )
        return
    interfaz.abrir_informe(ruta_especifica=ruta)


def mostrar_detalle_pedido_modal(interfaz: Any, ped: Pedido) -> None:
    """Muestra un modal detallado del pedido con opciones de consulta y reimpresión de comprobante y rótulos."""
    ruta_comprobante = buscar_archivo_comprobante(ped)
    ruta_descuento = buscar_archivo_descuento(ped)

    nombre_comprobante = ped.nombre_archivo or "Sin archivo adjunto"
    existe_comprobante = ruta_comprobante is not None and ruta_comprobante.exists()
    existe_descuento = ruta_descuento is not None and ruta_descuento.exists()

    ext = Path(nombre_comprobante).suffix.lower()
    if ext == ".pdf":
        icono_tipo = ft.Icons.PICTURE_AS_PDF
        color_tipo = ROJO
    elif ext in (".xlsx", ".xls"):
        icono_tipo = ft.Icons.TABLE_CHART
        color_tipo = ft.Colors.GREEN_600 if not interfaz.modo_oscuro else ft.Colors.GREEN_400
    elif ext in (".docx", ".doc"):
        icono_tipo = ft.Icons.DESCRIPTION
        color_tipo = ft.Colors.BLUE_600 if not interfaz.modo_oscuro else ft.Colors.BLUE_400
    else:
        icono_tipo = ft.Icons.ATTACH_FILE
        color_tipo = interfaz.secundario

    acciones_dialogo: list[ft.Control] = []
    if existe_comprobante:
        acciones_dialogo.append(
            interfaz.boton(
                "Reimprimir Comprobante",
                ft.Icons.PRINT,
                lambda _e: abrir_comprobante_pedido(interfaz, ped),
            )
        )
    acciones_dialogo.extend(
        [
            interfaz.boton(
                "Rótulos QR",
                ft.Icons.QR_CODE_2,
                lambda _e: interfaz.imprimir_rotulos_pedido(ped),
            ),
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

    fila_informe = ft.Container()
    if getattr(ped, "archivo_descuento", ""):
        fila_informe = ft.Container(
            padding=ft.Padding.symmetric(vertical=4),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.ASSESSMENT_OUTLINED, color=ft.Colors.GREEN_400, size=18),
                    ft.Text(f"Informe de Descuento: {ped.archivo_descuento}", size=12, color=interfaz.texto, expand=True),
                    *(
                        [
                            ft.TextButton(
                                "Ver informe",
                                icon=ft.Icons.VISIBILITY,
                                on_click=lambda _e: abrir_descuento_pedido(interfaz, ped),
                            )
                        ]
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
                            controls=[
                                ft.Text(ped.resumen_items or "Sin detalle de artículos registrado.", size=12, color=interfaz.texto)
                            ],
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


def mostrar_historial_pedidos(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana completa con buscador y lista histórica de pedidos del depósito."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador", "master"):
        interfaz.notificar("No tienes permisos suficientes para acceder al historial de pedidos.")
        return

    pedidos = interfaz.order_store.listar_pedidos(limit=400)
    items_lista = ft.ListView(expand=True, spacing=10)

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
    pedidos_visibles: list[Pedido] = []
    filtro_rapido_activo = "todos"  # "todos", "hoy", "pendientes", "despachados"

    def recargar_y_actualizar() -> None:
        nonlocal pedidos
        pedidos = interfaz.order_store.listar_pedidos(limit=400)
        actualizar_vista(campo_busqueda.value or "")

    def actualizar_vista(termino: str = "") -> None:
        nonlocal pedidos_visibles
        hoy_str = datetime.now().strftime("%Y-%m-%d")

        candidatos = []
        for p in pedidos:
            if filtro_rapido_activo == "hoy":
                if not (p.created_at and p.created_at.startswith(hoy_str)):
                    continue
            elif filtro_rapido_activo == "pendientes":
                if getattr(p, "cierre_id", None) is not None or getattr(p, "estado", "") == "anulado":
                    continue
            elif filtro_rapido_activo == "despachados":
                if getattr(p, "estado_despacho", "") != "despachado":
                    continue
            candidatos.append(p)

        filtrados = [p for p in candidatos if coincide(p, termino)]
        pedidos_visibles = filtrados
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

                col_borde_izq = (
                    ft.Colors.RED_600 if getattr(p, "estado", "") == "anulado"
                    else (
                        ft.Colors.GREEN_600 if est_desp == "entregado"
                        else (ft.Colors.AMBER_600 if est_desp == "despachado" else ft.Colors.BLUE_600)
                    )
                )

                boton_avanzar_desp = (
                    ft.OutlinedButton(
                        content=ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.LOCAL_SHIPPING if est_desp == "armado" else (ft.Icons.VERIFIED if est_desp == "despachado" else ft.Icons.REPLAY),
                                    size=14,
                                    color=col_desp_txt if interfaz.modo_oscuro else col_desp_bg,
                                ),
                                ft.Text(
                                    "Despachar pedido" if est_desp == "armado" else ("Marcar entregado" if est_desp == "despachado" else "Volver a armado"),
                                    size=11,
                                    weight=ft.FontWeight.W_500,
                                    color=interfaz.texto,
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        tooltip=tip_estado,
                        style=ft.ButtonStyle(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                            shape=ft.RoundedRectangleBorder(radius=6),
                            side=ft.BorderSide(1, col_desp_bg),
                        ),
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
                    if (interfaz.usuario_actual and interfaz.usuario_actual.role in ("operador", "administrador") and p.estado != "anulado")
                    else ft.Container()
                )
                boton_desarmar_hist = (
                    ft.IconButton(
                        icon=ft.Icons.REMOVE_SHOPPING_CART_OUTLINED,
                        tooltip="Desarmar pedido y devolver stock a inventario",
                        icon_color=ft.Colors.AMBER_400 if interfaz.modo_oscuro else ft.Colors.AMBER_800,
                        on_click=lambda _e, ped=p: interfaz.confirmar_desarmar_pedido(ped, al_final=recargar_y_actualizar),
                    )
                    if (interfaz.usuario_actual and interfaz.usuario_actual.role in ("operador", "administrador") and p.estado != "anulado")
                    else ft.Container()
                )
                boton_anular_hist = (
                    ft.IconButton(
                        icon=ft.Icons.CANCEL_OUTLINED,
                        tooltip="Anular este pedido",
                        icon_color=ft.Colors.RED_400,
                        on_click=lambda _e, ped=p: interfaz.confirmar_anulacion_pedido(ped, al_final=recargar_y_actualizar),
                    )
                    if (interfaz.usuario_actual and interfaz.usuario_actual.role in ("administrador",) and p.estado != "anulado")
                    else ft.Container()
                )

                nombre_arch = p.nombre_archivo or "Sin archivo"
                ext_arch = Path(nombre_arch).suffix.lower()
                if ext_arch == ".pdf":
                    icon_arch = ft.Icons.PICTURE_AS_PDF
                    col_arch = ROJO
                elif ext_arch in (".xlsx", ".xls"):
                    icon_arch = ft.Icons.TABLE_CHART
                    col_arch = ft.Colors.GREEN_600 if not interfaz.modo_oscuro else ft.Colors.GREEN_400
                elif ext_arch in (".docx", ".doc"):
                    icon_arch = ft.Icons.DESCRIPTION
                    col_arch = ft.Colors.BLUE_600 if not interfaz.modo_oscuro else ft.Colors.BLUE_400
                else:
                    icon_arch = ft.Icons.ATTACH_FILE
                    col_arch = interfaz.secundario

                chip_archivo = ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(icon_arch, size=13, color=col_arch),
                            ft.Text(nombre_arch, size=11, weight=ft.FontWeight.W_500, color=col_arch),
                            ft.Icon(ft.Icons.PRINT, size=12, color=col_arch),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                    border=ft.Border.all(1, col_arch if interfaz.modo_oscuro else ft.Colors.with_opacity(0.35, col_arch)),
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    bgcolor=ft.Colors.with_opacity(0.08, col_arch),
                    tooltip=f"Clic para consultar o reimprimir archivo cargado: {nombre_arch}",
                    on_click=lambda _e, ped=p: abrir_comprobante_pedido(interfaz, ped),
                )

                boton_imprimir_arch = ft.IconButton(
                    icon=ft.Icons.PRINT_OUTLINED,
                    tooltip=f"Consultar y reimprimir comprobante ({nombre_arch})",
                    icon_color=ft.Colors.CYAN_700 if not interfaz.modo_oscuro else ft.Colors.CYAN_400,
                    on_click=lambda _e, ped=p: abrir_comprobante_pedido(interfaz, ped),
                )
                boton_detalle_modal = ft.IconButton(
                    icon=ft.Icons.INFO_OUTLINE,
                    tooltip="Consultar detalle completo del pedido",
                    icon_color=interfaz.secundario,
                    on_click=lambda _e, ped=p: mostrar_detalle_pedido_modal(interfaz, ped),
                )

                items_lista.controls.append(
                    ft.Container(
                        bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.WHITE,
                        border=ft.Border(
                            left=ft.BorderSide(4, col_borde_izq),
                            top=ft.BorderSide(1, interfaz.borde),
                            right=ft.BorderSide(1, interfaz.borde),
                            bottom=ft.BorderSide(1, interfaz.borde),
                        ),
                        border_radius=ft.BorderRadius(top_left=4, bottom_left=4, top_right=10, bottom_right=10),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        content=ft.Column(
                            [
                                # Fila 1: Cabecera con número de pedido, badges y hora
                                ft.Row(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.RECEIPT_LONG, size=18, color=ROJO),
                                                ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=14, color=interfaz.texto),
                                                etiqueta_despacho,
                                                etiqueta_agregado,
                                                etiqueta_anulado,
                                            ],
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            spacing=8,
                                            wrap=True,
                                        ),
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.ACCESS_TIME, size=13, color=interfaz.secundario),
                                                ft.Text(f"{hora_txt} hs", size=11, color=interfaz.secundario, weight=ft.FontWeight.W_500),
                                            ],
                                            spacing=4,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),

                                # Fila 2: Datos comerciales y logísticos
                                ft.Row(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.PERSON, size=14, color=ROJO),
                                                ft.Text("Cliente:", size=12, color=interfaz.secundario),
                                                ft.Text(p.cliente, size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                                            ],
                                            spacing=4,
                                        ),
                                        ft.Container(
                                            content=ft.Row(
                                                [
                                                    ft.Icon(ft.Icons.LOCAL_SHIPPING_OUTLINED, size=13, color=ft.Colors.BLUE_400),
                                                    ft.Text(f"{p.logistica} · {p.bultos} bulto(s)", size=11, weight=ft.FontWeight.W_500, color=interfaz.texto),
                                                ],
                                                spacing=4,
                                            ),
                                            bgcolor=ft.Colors.WHITE_10 if interfaz.modo_oscuro else ft.Colors.GREY_100,
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                            border_radius=6,
                                        ),
                                        *(
                                            [
                                                ft.Container(
                                                    content=ft.Row(
                                                        [
                                                            ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=ft.Colors.AMBER_400),
                                                            ft.Text(
                                                                f"Retiro: {p.fecha_retiro}",
                                                                size=11,
                                                                weight=ft.FontWeight.BOLD,
                                                                color=ft.Colors.AMBER_300 if interfaz.modo_oscuro else ft.Colors.AMBER_800,
                                                            ),
                                                        ],
                                                        spacing=4,
                                                    ),
                                                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER_900) if interfaz.modo_oscuro else ft.Colors.AMBER_50,
                                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.AMBER_600)),
                                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                                    border_radius=6,
                                                )
                                            ]
                                            if getattr(p, "fecha_retiro", "")
                                            else []
                                        ),
                                        ft.Row(
                                            [
                                                ft.Icon(ft.Icons.ENGINEERING_OUTLINED, size=13, color=interfaz.secundario),
                                                ft.Text(f"Armador: {p.armador}", size=11, color=interfaz.secundario),
                                            ],
                                            spacing=4,
                                        ),
                                    ],
                                    spacing=12,
                                    wrap=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),

                                # Fila 3: Archivo Comprobante y Resumen de Descuento
                                ft.Row(
                                    [
                                        chip_archivo,
                                        ft.Container(
                                            content=ft.Row(
                                                [
                                                    ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=13, color=ft.Colors.GREEN_400),
                                                    ft.Text(
                                                        f"Descuento ({p.articulos_descontados} arts): {p.resumen_items}",
                                                        size=11,
                                                        weight=ft.FontWeight.W_500,
                                                        color=ft.Colors.GREEN_400 if interfaz.modo_oscuro else ft.Colors.GREEN_800,
                                                        no_wrap=False,
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                        max_lines=2,
                                                    ),
                                                ],
                                                spacing=6,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            ),
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_900) if interfaz.modo_oscuro else ft.Colors.GREEN_50,
                                            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.GREEN_700)),
                                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                            border_radius=6,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=10,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),

                                ft.Divider(height=6, thickness=0.6, color=interfaz.borde),

                                # Fila 4: Barra de Acciones y Herramientas
                                ft.Row(
                                    [
                                        boton_avanzar_desp,
                                        ft.Row(
                                            [
                                                boton_rotulo_hist,
                                                boton_imprimir_arch,
                                                boton_detalle_modal,
                                                boton_editar_hist,
                                                boton_desarmar_hist,
                                                boton_anular_hist,
                                            ],
                                            spacing=4,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            spacing=9,
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

    def imprimir_lote_rotulos_a4(_e: ft.Event) -> None:
        candidatos = [p for p in pedidos_visibles if getattr(p, "estado", "") != "anulado" and getattr(p, "bultos", 0) > 0]
        if not candidatos:
            interfaz.notificar("No hay pedidos con bultos para generar rótulos.")
            return
        interfaz.imprimir_rotulos_lote(candidatos)

    def cambiar_filtro_rapido(nuevo_filtro: str) -> None:
        nonlocal filtro_rapido_activo
        filtro_rapido_activo = nuevo_filtro
        actualizar_botones_filtro()
        actualizar_vista(campo_busqueda.value or "")

    btn_f_todos = ft.OutlinedButton("Todos", on_click=lambda _e: cambiar_filtro_rapido("todos"))
    btn_f_hoy = ft.OutlinedButton("Solo Hoy", icon=ft.Icons.TODAY, on_click=lambda _e: cambiar_filtro_rapido("hoy"))
    btn_f_pend = ft.OutlinedButton("Pendientes de Cierre", icon=ft.Icons.PENDING_ACTIONS, on_click=lambda _e: cambiar_filtro_rapido("pendientes"))
    btn_f_desp = ft.OutlinedButton("Despachados", icon=ft.Icons.LOCAL_SHIPPING, on_click=lambda _e: cambiar_filtro_rapido("despachados"))

    def actualizar_botones_filtro() -> None:
        for b, tag in [(btn_f_todos, "todos"), (btn_f_hoy, "hoy"), (btn_f_pend, "pendientes"), (btn_f_desp, "despachados")]:
            if filtro_rapido_activo == tag:
                b.style = ft.ButtonStyle(bgcolor=ROJO, color=ft.Colors.WHITE)
            else:
                b.style = ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT, color=interfaz.texto)

    actualizar_botones_filtro()

    fila_chips_filtro = ft.Row(
        [
            ft.Text("Filtros rápidos:", size=11, color=interfaz.secundario, weight=ft.FontWeight.BOLD),
            btn_f_todos,
            btn_f_hoy,
            btn_f_pend,
            btn_f_desp,
        ],
        spacing=6,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    barra_busqueda = ft.Column(
        [
            ft.Row(
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
                        "Rótulos A4 (Lote)",
                        icon=ft.Icons.PRINT,
                        tooltip="Generar rótulos optimizados llenando hojas A4 (10 por página)",
                        style=ft.ButtonStyle(
                            color=ft.Colors.WHITE,
                            bgcolor=ft.Colors.BLUE_GREY_700,
                        ),
                        on_click=imprimir_lote_rotulos_a4,
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
            ),
            fila_chips_filtro,
        ],
        spacing=6,
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
            width=960,
            height=620,
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
