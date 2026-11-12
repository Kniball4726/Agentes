from datetime import datetime
"""Diálogos de historial de pedidos e impresión de comprobantes de descuento."""

from pathlib import Path
from typing import Any, Callable

import flet as ft

from ..theme import ROJO
from ..components.debounce import Debouncer
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
    if interfaz.usuario_actual and interfaz.usuario_actual.role == "master":
        interfaz.notificar("El usuario Master no tiene acceso a la visualización de pedidos operativos.")
        return
    if interfaz.usuario_actual and interfaz.usuario_actual.role == "picker":
        interfaz.notificar("El usuario Picker no tiene acceso a la visualización de pedidos operativos.")
        return

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
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador"):
        interfaz.notificar("No tienes permisos suficientes para acceder al historial de pedidos.")
        return

    pedidos = interfaz.order_store.listar_pedidos(limit=400)
    items_lista = ft.ListView(expand=True, spacing=1)

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
    pedidos_seleccionados: set[int] = set()
    filtro_rapido_activo = "todos"  # "todos", "hoy", "pendientes", "despachados"
    pagina_actual = 1
    tamano_pagina = 25
    total_paginas_global = 1

    texto_pagina_info = ft.Text("Pág. 1 de 1", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto)
    texto_rango_info = ft.Text("", size=11, color=interfaz.secundario)

    def _ir_a_pagina(num: int) -> None:
        nonlocal pagina_actual
        if 1 <= num <= total_paginas_global:
            pagina_actual = num
            actualizar_vista(campo_busqueda.value or "")

    def _cambiar_tamano_pagina(e: Any) -> None:
        nonlocal tamano_pagina, pagina_actual
        try:
            tamano_pagina = int(e.control.value)
        except Exception:
            tamano_pagina = 25
        pagina_actual = 1
        actualizar_vista(campo_busqueda.value or "")

    btn_pag_primera = ft.IconButton(
        icon=ft.Icons.FIRST_PAGE,
        icon_size=18,
        tooltip="Primera página",
        on_click=lambda _e: _ir_a_pagina(1),
    )
    btn_pag_anterior = ft.IconButton(
        icon=ft.Icons.NAVIGATE_BEFORE,
        icon_size=18,
        tooltip="Página anterior",
        on_click=lambda _e: _ir_a_pagina(pagina_actual - 1),
    )
    btn_pag_siguiente = ft.IconButton(
        icon=ft.Icons.NAVIGATE_NEXT,
        icon_size=18,
        tooltip="Página siguiente",
        on_click=lambda _e: _ir_a_pagina(pagina_actual + 1),
    )
    btn_pag_ultima = ft.IconButton(
        icon=ft.Icons.LAST_PAGE,
        icon_size=18,
        tooltip="Última página",
        on_click=lambda _e: _ir_a_pagina(total_paginas_global),
    )
    dropdown_tamano = ft.Dropdown(
        dense=True,
        options=[
            ft.dropdown.Option("15", "15 por pág."),
            ft.dropdown.Option("25", "25 por pág."),
            ft.dropdown.Option("50", "50 por pág."),
            ft.dropdown.Option("100", "100 por pág."),
        ],
        value="25",
        width=135,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        on_select=_cambiar_tamano_pagina,
    )

    barra_paginacion = ft.Container(
        bgcolor="#18181b",
        border=ft.Border.all(1, "#27272a"),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=12, vertical=4),
        content=ft.Row(
            [
                texto_rango_info,
                ft.Row(
                    [
                        btn_pag_primera,
                        btn_pag_anterior,
                        texto_pagina_info,
                        btn_pag_siguiente,
                        btn_pag_ultima,
                        dropdown_tamano,
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    def _on_row_hover(e: ft.HoverEvent) -> None:
        try:
            e.control.bgcolor = "#26262b" if e.data == "true" else "#141416"
            e.control.update()
        except Exception:
            pass

    def recargar_y_actualizar() -> None:
        nonlocal pedidos, pagina_actual
        pagina_actual = 1
        pedidos = interfaz.order_store.listar_pedidos(limit=400)
        actualizar_vista(campo_busqueda.value or "")

    def actualizar_vista(termino: str = "") -> None:
        nonlocal pedidos_visibles, total_paginas_global, pagina_actual
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
        filtrados.sort(key=lambda x: (x.created_at or "", x.id), reverse=True)
        total_items = len(filtrados)
        total_paginas_global = max(1, (total_items + tamano_pagina - 1) // tamano_pagina)
        if pagina_actual > total_paginas_global:
            pagina_actual = total_paginas_global
        if pagina_actual < 1:
            pagina_actual = 1

        btn_pag_primera.disabled = (pagina_actual <= 1)
        btn_pag_anterior.disabled = (pagina_actual <= 1)
        btn_pag_siguiente.disabled = (pagina_actual >= total_paginas_global)
        btn_pag_ultima.disabled = (pagina_actual >= total_paginas_global)
        texto_pagina_info.value = f"Pág. {pagina_actual} de {total_paginas_global}"
        pedidos_visibles = filtrados
        items_lista.controls.clear()

        if not filtrados:
            barra_paginacion.visible = False
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

        barra_paginacion.visible = True
        inicio_idx = (pagina_actual - 1) * tamano_pagina
        fin_idx = min(inicio_idx + tamano_pagina, total_items)
        pedidos_pagina = filtrados[inicio_idx:fin_idx]
        pedidos_visibles = pedidos_pagina
        texto_rango_info.value = f"Mostrando {inicio_idx + 1}–{fin_idx} de {total_items} pedidos"
        texto_contador.value = (
            f"Pág. {pagina_actual}/{total_paginas_global} ({inicio_idx + 1}–{fin_idx} de {total_items})"
            if termino.strip()
            else f"Total: {total_items} pedidos · Pág. {pagina_actual}/{total_paginas_global}"
        )

        pedidos_por_fecha: dict[str, list[Pedido]] = {}
        for p in pedidos_pagina:
            f_clave = p.created_at[:10] if p.created_at else "Sin fecha"
            pedidos_por_fecha.setdefault(f_clave, []).append(p)

        fechas_ordenadas = sorted(
            pedidos_por_fecha.keys(),
            key=lambda d: ("0000-00-00" if d == "Sin fecha" else d),
            reverse=True,
        )

        for f_clave in fechas_ordenadas:
            pedidos_grupo = pedidos_por_fecha[f_clave]
            pedidos_grupo.sort(key=lambda x: (x.created_at or "", x.id), reverse=True)
            cant = len(pedidos_grupo)

            fecha_display = f_clave
            try:
                partes = f_clave.split("-")
                if len(partes) == 3:
                    dia = int(partes[2])
                    mes = int(partes[1])
                    anio = partes[0]
                    fecha_display = f"{dia}/{mes}/{anio}"
            except Exception:
                pass

            es_hoy = (f_clave == hoy_str)
            encabezado_fecha = ft.Container(
                bgcolor="#18181c",
                border=ft.Border(
                    left=ft.BorderSide(4, ROJO),
                    top=ft.BorderSide(1, "#27272a"),
                    right=ft.BorderSide(1, "#27272a"),
                    bottom=ft.BorderSide(1, "#27272a"),
                ),
                border_radius=ft.BorderRadius(top_left=4, bottom_left=4, top_right=8, bottom_right=8),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                margin=ft.Margin.only(top=10, bottom=4),
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=ROJO),
                                ft.Text(fecha_display, weight=ft.FontWeight.BOLD, size=13, color="#f4f4f5"),
                                *(
                                    [
                                        ft.Container(
                                            content=ft.Text("HOY", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                            bgcolor=ROJO,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                        )
                                    ]
                                    if es_hoy
                                    else []
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Container(
                            content=ft.Text(
                                f"{cant} pedido{'s' if cant != 1 else ''}",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            bgcolor=ROJO,
                            border_radius=6,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            items_lista.controls.append(encabezado_fecha)

            for p in pedidos_grupo:
                est_desp = (getattr(p, "estado_despacho", "armado") or "armado").lower()
                es_anulado = getattr(p, "estado", "") == "anulado"
                if est_desp == "entregado":
                    col_desp_bg, lbl_desp = "#16a34a", "ENTREGADO"
                    sig_estado = "armado"
                    tip_estado = "Estado actual: Entregado (clic para volver a Armado)"
                elif est_desp == "despachado":
                    col_desp_bg, lbl_desp = "#d97706", "DESPACHADO"
                    sig_estado = "entregado"
                    tip_estado = "Marcar como DESPACHADO"
                else:
                    col_desp_bg, lbl_desp = "#2563eb", "ARMADO"
                    sig_estado = "despachado"
                    tip_estado = "Marcar como DESPACHADO"

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

                nota_obs = ""
                col_obs = "#a1a1aa"
                if getattr(p, "agregado", False):
                    nota_obs = "agregado"
                    col_obs = "#eab308"
                elif p.resumen_items:
                    res_c = p.resumen_items.strip()
                    if len(res_c) > 20:
                        res_c = res_c[:18] + "..."
                    nota_obs = res_c

                badge_firma = ft.Container(
                    content=ft.Text(
                        "ANULADO" if es_anulado else lbl_desp,
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color="#ffffff",
                    ),
                    bgcolor="#dc2626" if es_anulado else col_desp_bg,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                    tooltip=tip_estado if not es_anulado else "Pedido anulado",
                    on_click=(lambda _e, ped=p, st=sig_estado: cambiar_estado_ped(ped, st)) if not es_anulado else None,
                )

                fila_pedido = ft.Container(
                    bgcolor="#141416",
                    border=ft.Border(bottom=ft.BorderSide(0.5, "#222226")),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    ink=True,
                    on_hover=_on_row_hover,
                    on_click=lambda _e, ped=p: mostrar_detalle_pedido_modal(interfaz, ped),
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Checkbox(
                                    value=p.id in pedidos_seleccionados,
                                    tooltip="Seleccionar para despacho en lote",
                                    on_change=lambda e, pid=p.id: _toggle_sel(e, pid),
                                    scale=0.8,
                                ),
                                width=30,
                                alignment=ft.Alignment(-1, 0),
                            ),
                            ft.Container(
                                content=ft.Text(p.nota_pedido or "-", size=12, color="#f4f4f5"),
                                width=75,
                            ),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.IconButton(
                                            icon=ft.Icons.DESCRIPTION_OUTLINED,
                                            icon_size=15,
                                            icon_color="#9ca3af",
                                            tooltip=f"Ver/reimprimir comprobante ({p.nombre_archivo or 'Sin archivo'})",
                                            on_click=lambda _e, ped=p: abrir_comprobante_pedido(interfaz, ped),
                                            style=ft.ButtonStyle(padding=0),
                                            width=18,
                                            height=18,
                                        ),
                                        ft.Text(
                                            p.cliente or "Sin Cliente",
                                            size=12,
                                            weight=ft.FontWeight.BOLD,
                                            color="#f4f4f5",
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            max_lines=1,
                                            expand=True,
                                        ),
                                    ],
                                    spacing=4,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                width=240,
                            ),
                            ft.Container(
                                content=ft.Text(p.numero_pedido or "-", size=12, color="#d4d4d8"),
                                width=65,
                            ),
                            ft.Container(
                                content=ft.Text(str(p.bultos), size=12, weight=ft.FontWeight.BOLD, color="#d4d4d8"),
                                width=55,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    p.logistica or "-",
                                    size=12,
                                    color="#d4d4d8",
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                ),
                                width=170,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    p.armador or "-",
                                    size=12,
                                    color="#a1a1aa",
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                ),
                                width=140,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    nota_obs,
                                    size=11,
                                    weight=ft.FontWeight.BOLD if nota_obs == "agregado" else ft.FontWeight.NORMAL,
                                    color=col_obs,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                ),
                                width=90,
                            ),
                            ft.Container(
                                content=ft.Text(
                                    getattr(p, "fecha_retiro", "") or "-",
                                    size=11,
                                    color="#a1a1aa",
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                ),
                                width=115,
                            ),
                            ft.Container(
                                content=badge_firma,
                                width=90,
                            ),
                            ft.Container(
                                content=ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color="#71717a"),
                                width=30,
                                alignment=ft.Alignment(1, 0),
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
                items_lista.controls.append(fila_pedido)
        if interfaz.page:
            interfaz.page.update()

    def _toggle_sel(e: ft.Event, pid: int) -> None:
        if e.control.value:
            pedidos_seleccionados.add(pid)
        else:
            pedidos_seleccionados.discard(pid)
        _actualizar_barra_lote()

    texto_lote_sel = ft.Text("0 seleccionados", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto)

    def _actualizar_barra_lote() -> None:
        c_sel = len(pedidos_seleccionados)
        barra_lote.visible = c_sel > 0
        texto_lote_sel.value = f"📦 {c_sel} pedido(s) seleccionado(s):"
        if interfaz.page:
            interfaz.page.update()

    def _despachar_lote(st_nuevo: str) -> None:
        if not pedidos_seleccionados:
            return
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
        try:
            n_upd = interfaz.order_store.avanzar_estado_lote(
                list(pedidos_seleccionados),
                st_nuevo,
                usuario=usr
            )
            pedidos_seleccionados.clear()
            _actualizar_barra_lote()
            interfaz.reproducir_sonido("exito")
            interfaz.notificar(f"Se actualizaron {n_upd} pedido(s) a '{st_nuevo.upper()}'.")
            recargar_y_actualizar()
        except Exception as ex_l:
            interfaz.reproducir_sonido("error")
            interfaz.notificar(f"Error en despacho en lote: {ex_l}")

    def _sel_todos_visibles(_e: ft.Event) -> None:
        for p in pedidos_visibles:
            if getattr(p, "estado", "") != "anulado":
                pedidos_seleccionados.add(p.id)
        _actualizar_barra_lote()
        actualizar_vista(campo_busqueda.value or "")

    def _desmarcar_todos(_e: ft.Event) -> None:
        pedidos_seleccionados.clear()
        _actualizar_barra_lote()
        actualizar_vista(campo_busqueda.value or "")

    barra_lote = ft.Container(
        visible=False,
        bgcolor="#18181b",
        border=ft.Border.all(1, "#27272a"),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        content=ft.Row(
            [
                texto_lote_sel,
                ft.Button(
                    "Despachar Seleccionados",
                    icon=ft.Icons.LOCAL_SHIPPING,
                    bgcolor=ft.Colors.BLUE_600,
                    color=ft.Colors.WHITE,
                    on_click=lambda _e: _despachar_lote("despachado"),
                ),
                ft.Button(
                    "Marcar Entregados",
                    icon=ft.Icons.TASK_ALT,
                    bgcolor=ft.Colors.GREEN_600,
                    color=ft.Colors.WHITE,
                    on_click=lambda _e: _despachar_lote("entregado"),
                ),
                ft.TextButton("Desmarcar", on_click=_desmarcar_todos),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        ),
    )

    campo_busqueda = ft.TextField(
        hint_text="Buscar por cliente, remito / nota, N° pedido, fecha (DD/MM/AAAA) o armador...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor="#18181b",
        border_color="#27272a",
        color="#f4f4f5",
        expand=True,
    )

    debouncer_pedidos = Debouncer(0.25)

    def _al_escribir_filtro(_e: Any) -> None:
        debouncer_pedidos.debounce(
            lambda: _ir_a_pagina(1) if pagina_actual != 1 else actualizar_vista(campo_busqueda.value or "")
        )

    campo_busqueda.on_change = _al_escribir_filtro

    def limpiar_busqueda(_e: ft.Event) -> None:
        nonlocal pagina_actual
        pagina_actual = 1
        campo_busqueda.value = ""
        actualizar_vista("")

    def imprimir_lote_rotulos_a4(_e: ft.Event) -> None:
        candidatos = [p for p in pedidos_visibles if getattr(p, "estado", "") != "anulado" and getattr(p, "bultos", 0) > 0]
        if not candidatos:
            interfaz.notificar("No hay pedidos con bultos para generar rótulos.")
            return
        interfaz.imprimir_rotulos_lote(candidatos)

    def cambiar_filtro_rapido(nuevo_filtro: str) -> None:
        nonlocal filtro_rapido_activo, pagina_actual
        pagina_actual = 1
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
                b.style = ft.ButtonStyle(bgcolor="#27272a", color=ft.Colors.WHITE, side=ft.BorderSide(1, "#3b82f6"))
            else:
                b.style = ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT, color="#a1a1aa", side=ft.BorderSide(1, "#27272a"))

    actualizar_botones_filtro()

    fila_chips_filtro = ft.Row(
        [
            ft.Text("Filtros rápidos:", size=11, color="#a1a1aa", weight=ft.FontWeight.BOLD),
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
                        icon_color="#a1a1aa",
                        tooltip="Borrar búsqueda",
                        on_click=limpiar_busqueda,
                    ),
                    ft.Button(
                        "Rótulos A4 (Lote)",
                        icon=ft.Icons.PRINT,
                        tooltip="Generar rótulos optimizados llenando hojas A4 (10 por página)",
                        style=ft.ButtonStyle(
                            color=ft.Colors.WHITE,
                            bgcolor="#27272a",
                            side=ft.BorderSide(1, "#3f3f46"),
                        ),
                        on_click=imprimir_lote_rotulos_a4,
                    ),
                    ft.Button(
                        "Escanear QR / Cambiar Estado",
                        icon=ft.Icons.QR_CODE_SCANNER,
                        style=ft.ButtonStyle(
                            color=ft.Colors.WHITE,
                            bgcolor="#27272a",
                            side=ft.BorderSide(1, "#3f3f46"),
                        ),
                        on_click=lambda _e: interfaz.mostrar_escaner_qr_despacho(al_actualizar=recargar_y_actualizar),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    fila_chips_filtro,
                    ft.TextButton(
                        "Seleccionar Visibles",
                        icon=ft.Icons.CHECK_BOX_OUTLINED,
                        icon_color="#a1a1aa",
                        style=ft.ButtonStyle(color="#a1a1aa"),
                        on_click=_sel_todos_visibles,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            barra_lote,
        ],
        spacing=6,
    )

    cabecera_columnas = ft.Container(
        bgcolor="#18181b",
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border=ft.Border(bottom=ft.BorderSide(1, "#27272a")),
        content=ft.Row(
            [
                ft.Container(width=30),
                ft.Container(content=ft.Text("Nota", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=75),
                ft.Container(content=ft.Text("Cliente", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=240),
                ft.Container(content=ft.Text("Numero", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=65),
                ft.Container(content=ft.Text("Bultos", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=55),
                ft.Container(content=ft.Text("Logistica", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=170),
                ft.Container(content=ft.Text("Preparador", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=140),
                ft.Container(content=ft.Text("Nota", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=90),
                ft.Container(content=ft.Text("Fecha de retiro o entrega", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=115),
                ft.Container(content=ft.Text("Firma", size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=90),
                ft.Container(width=30),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    actualizar_vista("")

    dialogo = ft.AlertDialog(
        bgcolor="#121214",
        title=ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.RECEIPT_LONG, color="#a1a1aa", size=22),
                        ft.Text("Ver pedidos mayoristas", weight=ft.FontWeight.BOLD, color="#f4f4f5", size=18),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        texto_contador,
                        ft.IconButton(
                            icon=ft.Icons.CHECK_BOX_OUTLINED,
                            icon_size=20,
                            icon_color="#a1a1aa",
                            tooltip="Seleccionar todos los pedidos visibles",
                            on_click=_sel_todos_visibles,
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        content=ft.Container(
            width=1140,
            height=660,
            bgcolor="#121214",
            content=ft.Column(
                [
                    barra_busqueda,
                    cabecera_columnas,
                    items_lista,
                    barra_paginacion,
                ],
                expand=True,
                spacing=4,
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
