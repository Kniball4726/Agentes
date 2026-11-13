"""Vista principal de historial de pedidos mayoristas con filtros, paginación y lote."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import flet as ft

from ...orders_store import Pedido
from ..components.debounce import Debouncer
from ..theme import ROJO
from .historial_archivos import abrir_comprobante_pedido
from .historial_detalle import mostrar_detalle_pedido_modal


def _formatear_fecha_corta(f_str: str) -> str:
    try:
        partes = f_str.split("-")
        if len(partes) == 3:
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
    except Exception:
        pass
    return f_str


def _coincide_pedido(p: Pedido, q: str) -> bool:
    if not q:
        return True
    q = q.lower().strip()
    c_at = p.created_at or ""
    campos = (
        p.cliente or "",
        p.nota_pedido or "",
        str(getattr(p, "numero_pedido", "") or ""),
        p.armador or "",
        p.logistica or "",
        c_at,
        _formatear_fecha_corta(c_at[:10]),
        str(getattr(p, "fecha_retiro", "") or ""),
        p.nombre_archivo or "",
    )
    return any(q in campo.lower() for campo in campos)


def _estado_visual_despacho(p: Pedido) -> tuple[str, str, str, str]:
    est_desp = (getattr(p, "estado_despacho", "armado") or "armado").lower()
    if est_desp == "entregado":
        return "#16a34a", "ENTREGADO", "armado", "Estado actual: Entregado (clic para volver a Armado)"
    if est_desp == "despachado":
        return "#d97706", "DESPACHADO", "entregado", "Marcar como DESPACHADO"
    return "#2563eb", "ARMADO", "despachado", "Marcar como DESPACHADO"


def _construir_encabezado_fecha(f_clave: str, hoy_str: str, cant: int) -> ft.Container:
    fecha_display = f_clave
    try:
        partes = f_clave.split("-")
        if len(partes) == 3:
            fecha_display = f"{int(partes[2])}/{int(partes[1])}/{partes[0]}"
    except Exception:
        pass
    es_hoy = f_clave == hoy_str
    return ft.Container(
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
                    content=ft.Text(f"{cant} pedido{'s' if cant != 1 else ''}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    bgcolor=ROJO,
                    border_radius=6,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _construir_fila_pedido(
    interfaz: Any,
    p: Pedido,
    pedidos_seleccionados: set[int],
    on_toggle_sel: Callable[[ft.Event, int], None],
    on_row_hover: Callable[[ft.HoverEvent], None],
    on_cambiar_estado: Callable[[Pedido, str], None],
) -> ft.Container:
    es_anulado = getattr(p, "estado", "") == "anulado"
    col_desp_bg, lbl_desp, sig_estado, tip_estado = _estado_visual_despacho(p)

    nota_obs = ""
    col_obs = "#a1a1aa"
    if getattr(p, "agregado", False):
        nota_obs = "agregado"
        col_obs = "#eab308"
    elif p.resumen_items:
        res_c = p.resumen_items.strip()
        nota_obs = (res_c[:18] + "...") if len(res_c) > 20 else res_c

    badge_firma = ft.Container(
        content=ft.Text("ANULADO" if es_anulado else lbl_desp, size=10, weight=ft.FontWeight.BOLD, color="#ffffff"),
        bgcolor="#dc2626" if es_anulado else col_desp_bg,
        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
        border_radius=4,
        tooltip=tip_estado if not es_anulado else "Pedido anulado",
        on_click=(lambda _e, ped=p, st=sig_estado: on_cambiar_estado(ped, st)) if not es_anulado else None,
    )

    return ft.Container(
        bgcolor="#141416",
        border=ft.Border(bottom=ft.BorderSide(0.5, "#222226")),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        ink=True,
        on_hover=on_row_hover,
        on_click=lambda _e, ped=p: mostrar_detalle_pedido_modal(interfaz, ped),
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Checkbox(
                        value=p.id in pedidos_seleccionados,
                        tooltip="Seleccionar para despacho en lote",
                        on_change=lambda e, pid=p.id: on_toggle_sel(e, pid),
                        scale=0.8,
                    ),
                    width=30,
                    alignment=ft.Alignment(-1, 0),
                ),
                ft.Container(content=ft.Text(p.nota_pedido or "-", size=12, color="#f4f4f5"), width=75),
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
                ft.Container(content=ft.Text(p.numero_pedido or "-", size=12, color="#d4d4d8"), width=65),
                ft.Container(content=ft.Text(str(p.bultos), size=12, weight=ft.FontWeight.BOLD, color="#d4d4d8"), width=55),
                ft.Container(content=ft.Text(p.logistica or "-", size=12, color="#d4d4d8", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), width=170),
                ft.Container(content=ft.Text(p.armador or "-", size=12, color="#a1a1aa", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1), width=140),
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
                    content=ft.Text(getattr(p, "fecha_retiro", "") or "-", size=11, color="#a1a1aa", overflow=ft.TextOverflow.ELLIPSIS, max_lines=1),
                    width=115,
                ),
                ft.Container(content=badge_firma, width=90),
                ft.Container(content=ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color="#71717a"), width=30, alignment=ft.Alignment(1, 0)),
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def mostrar_historial_pedidos(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana completa con buscador y lista histórica de pedidos del depósito."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in ("operador", "administrador"):
        interfaz.notificar("No tienes permisos suficientes para acceder al historial de pedidos.")
        return

    pedidos = interfaz.order_store.listar_pedidos(limit=400)
    items_lista = ft.ListView(expand=True, spacing=1)

    texto_contador = ft.Text(f"Total: {len(pedidos)} pedidos" if pedidos else "", size=11, color=interfaz.secundario)
    pedidos_visibles: list[Pedido] = []
    pedidos_seleccionados: set[int] = set()
    filtro_rapido_activo = "todos"
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

    btn_pag_primera = ft.IconButton(icon=ft.Icons.FIRST_PAGE, icon_size=18, tooltip="Primera página", on_click=lambda _e: _ir_a_pagina(1))
    btn_pag_anterior = ft.IconButton(icon=ft.Icons.NAVIGATE_BEFORE, icon_size=18, tooltip="Página anterior", on_click=lambda _e: _ir_a_pagina(pagina_actual - 1))
    btn_pag_siguiente = ft.IconButton(icon=ft.Icons.NAVIGATE_NEXT, icon_size=18, tooltip="Página siguiente", on_click=lambda _e: _ir_a_pagina(pagina_actual + 1))
    btn_pag_ultima = ft.IconButton(icon=ft.Icons.LAST_PAGE, icon_size=18, tooltip="Última página", on_click=lambda _e: _ir_a_pagina(total_paginas_global))
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
                    [btn_pag_primera, btn_pag_anterior, texto_pagina_info, btn_pag_siguiente, btn_pag_ultima, dropdown_tamano],
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

    def _cambiar_estado_ped(ped_obj: Pedido, nuevo_est: str) -> None:
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
        try:
            interfaz.order_store.actualizar_estado_despacho(ped_obj.id, nuevo_est, usuario=usr, permitir_retroceso=True)
            recargar_y_actualizar()
            interfaz.sincronizar_sesiones()
        except Exception as err:
            interfaz.notificar(str(err))

    def actualizar_vista(termino: str = "") -> None:
        nonlocal pedidos_visibles, total_paginas_global, pagina_actual
        hoy_str = datetime.now().strftime("%Y-%m-%d")

        candidatos = []
        for p in pedidos:
            if filtro_rapido_activo == "hoy" and not (p.created_at and p.created_at.startswith(hoy_str)):
                continue
            if filtro_rapido_activo == "pendientes" and (getattr(p, "cierre_id", None) is not None or getattr(p, "estado", "") == "anulado"):
                continue
            if filtro_rapido_activo == "despachados" and getattr(p, "estado_despacho", "") != "despachado":
                continue
            candidatos.append(p)

        filtrados = [p for p in candidatos if _coincide_pedido(p, termino)]
        filtrados.sort(key=lambda x: (x.created_at or "", x.id), reverse=True)
        total_items = len(filtrados)
        total_paginas_global = max(1, (total_items + tamano_pagina - 1) // tamano_pagina)
        pagina_actual = max(1, min(pagina_actual, total_paginas_global))

        btn_pag_primera.disabled = pagina_actual <= 1
        btn_pag_anterior.disabled = pagina_actual <= 1
        btn_pag_siguiente.disabled = pagina_actual >= total_paginas_global
        btn_pag_ultima.disabled = pagina_actual >= total_paginas_global
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
            pedidos_por_fecha.setdefault(p.created_at[:10] if p.created_at else "Sin fecha", []).append(p)

        for f_clave in sorted(pedidos_por_fecha.keys(), key=lambda d: ("0000-00-00" if d == "Sin fecha" else d), reverse=True):
            pedidos_grupo = sorted(pedidos_por_fecha[f_clave], key=lambda x: (x.created_at or "", x.id), reverse=True)
            items_lista.controls.append(_construir_encabezado_fecha(f_clave, hoy_str, len(pedidos_grupo)))
            for p in pedidos_grupo:
                items_lista.controls.append(
                    _construir_fila_pedido(interfaz, p, pedidos_seleccionados, _toggle_sel, _on_row_hover, _cambiar_estado_ped)
                )

        if interfaz.page:
            interfaz.page.update()

    texto_lote_sel = ft.Text("0 seleccionados", size=11, weight=ft.FontWeight.BOLD, color=interfaz.texto)

    def _actualizar_barra_lote() -> None:
        c_sel = len(pedidos_seleccionados)
        barra_lote.visible = c_sel > 0
        texto_lote_sel.value = f"📦 {c_sel} pedido(s) seleccionado(s):"
        if interfaz.page:
            interfaz.page.update()

    def _toggle_sel(e: ft.Event, pid: int) -> None:
        if e.control.value:
            pedidos_seleccionados.add(pid)
        else:
            pedidos_seleccionados.discard(pid)
        _actualizar_barra_lote()

    def _despachar_lote(st_nuevo: str) -> None:
        if not pedidos_seleccionados:
            return
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
        try:
            n_upd = interfaz.order_store.avanzar_estado_lote(list(pedidos_seleccionados), st_nuevo, usuario=usr)
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
                ft.Button("Despachar Seleccionados", icon=ft.Icons.LOCAL_SHIPPING, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE, on_click=lambda _e: _despachar_lote("despachado")),
                ft.Button("Marcar Entregados", icon=ft.Icons.TASK_ALT, bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE, on_click=lambda _e: _despachar_lote("entregado")),
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
    campo_busqueda.on_change = lambda _e: debouncer_pedidos.debounce(
        lambda: _ir_a_pagina(1) if pagina_actual != 1 else actualizar_vista(campo_busqueda.value or "")
    )

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

    btn_f_todos = ft.OutlinedButton("Todos", on_click=lambda _e: cambiar_filtro_rapido("todos"))
    btn_f_hoy = ft.OutlinedButton("Solo Hoy", icon=ft.Icons.TODAY, on_click=lambda _e: cambiar_filtro_rapido("hoy"))
    btn_f_pend = ft.OutlinedButton("Pendientes de Cierre", icon=ft.Icons.PENDING_ACTIONS, on_click=lambda _e: cambiar_filtro_rapido("pendientes"))
    btn_f_desp = ft.OutlinedButton("Despachados", icon=ft.Icons.LOCAL_SHIPPING, on_click=lambda _e: cambiar_filtro_rapido("despachados"))

    def actualizar_botones_filtro() -> None:
        for b, tag in [(btn_f_todos, "todos"), (btn_f_hoy, "hoy"), (btn_f_pend, "pendientes"), (btn_f_desp, "despachados")]:
            b.style = (
                ft.ButtonStyle(bgcolor="#27272a", color=ft.Colors.WHITE, side=ft.BorderSide(1, "#3b82f6"))
                if filtro_rapido_activo == tag
                else ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT, color="#a1a1aa", side=ft.BorderSide(1, "#27272a"))
            )

    def cambiar_filtro_rapido(nuevo_filtro: str) -> None:
        nonlocal filtro_rapido_activo, pagina_actual
        pagina_actual = 1
        filtro_rapido_activo = nuevo_filtro
        actualizar_botones_filtro()
        actualizar_vista(campo_busqueda.value or "")

    actualizar_botones_filtro()

    barra_busqueda = ft.Column(
        [
            ft.Row(
                [
                    campo_busqueda,
                    ft.IconButton(icon=ft.Icons.CLEAR, icon_size=18, icon_color="#a1a1aa", tooltip="Borrar búsqueda", on_click=limpiar_busqueda),
                    ft.Button(
                        "Rótulos A4 (Lote)",
                        icon=ft.Icons.PRINT,
                        tooltip="Generar rótulos optimizados llenando hojas A4 (10 por página)",
                        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor="#27272a", side=ft.BorderSide(1, "#3f3f46")),
                        on_click=imprimir_lote_rotulos_a4,
                    ),
                    ft.Button(
                        "Escanear QR / Cambiar Estado",
                        icon=ft.Icons.QR_CODE_SCANNER,
                        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor="#27272a", side=ft.BorderSide(1, "#3f3f46")),
                        on_click=lambda _e: interfaz.mostrar_escaner_qr_despacho(al_actualizar=recargar_y_actualizar),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    ft.Row(
                        [ft.Text("Filtros rápidos:", size=11, color="#a1a1aa", weight=ft.FontWeight.BOLD), btn_f_todos, btn_f_hoy, btn_f_pend, btn_f_desp],
                        spacing=6,
                        wrap=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.TextButton("Seleccionar Visibles", icon=ft.Icons.CHECK_BOX_OUTLINED, icon_color="#a1a1aa", style=ft.ButtonStyle(color="#a1a1aa"), on_click=_sel_todos_visibles),
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
                *[
                    ft.Container(content=ft.Text(lbl, size=12, weight=ft.FontWeight.W_500, color="#9ca3af"), width=w)
                    for lbl, w in (
                        ("Nota", 75), ("Cliente", 240), ("Numero", 65), ("Bultos", 55),
                        ("Logistica", 170), ("Preparador", 140), ("Nota", 90),
                        ("Fecha de retiro o entrega", 115), ("Firma", 90),
                    )
                ],
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
                ft.Row([ft.Icon(ft.Icons.RECEIPT_LONG, color="#a1a1aa", size=22), ft.Text("Ver pedidos mayoristas", weight=ft.FontWeight.BOLD, color="#f4f4f5", size=18)], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([texto_contador, ft.IconButton(icon=ft.Icons.CHECK_BOX_OUTLINED, icon_size=20, icon_color="#a1a1aa", tooltip="Seleccionar todos los pedidos visibles", on_click=_sel_todos_visibles)], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        content=ft.Container(
            width=1140,
            height=660,
            bgcolor="#121214",
            content=ft.Column([barra_busqueda, cabecera_columnas, items_lista, barra_paginacion], expand=True, spacing=4),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
