"""Vista principal de historial de pedidos mayoristas con filtros, paginación y lote."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import flet as ft

from ...orders import Pedido
from ..components.debounce import Debouncer
from ..design import colores_de
from .historial_cards import (
    _coincide_pedido,
    _construir_encabezado_fecha,
    _construir_fila_pedido,
    _estado_visual_despacho,
    _formatear_fecha_corta,
    construir_cabecera_columnas_historial,
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
    colores = colores_de(interfaz)
    barra_paginacion = ft.Container(
        bgcolor=colores.superficie_suave,
        border=ft.Border.all(1, colores.borde),
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
            pal = colores_de(interfaz)
            bg_hover = ft.Colors.with_opacity(0.08, pal.texto) if e.data == "true" else pal.superficie_suave
            e.control.bgcolor = bg_hover
            e.control.update()
        except Exception:
            pass

    def recargar_y_actualizar() -> None:
        nonlocal pedidos, pagina_actual
        pagina_actual = 1
        pedidos = interfaz.order_store.listar_pedidos(limit=400)
        actualizar_vista(campo_busqueda.value or "")

    def _cambiar_estado_ped(ped_obj: Pedido, nuevo_est: str) -> None:
        if not interfaz.exigir_roles("operador", "administrador"):
            return
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
        puede_retroceder = bool(
            interfaz.usuario_actual and interfaz.usuario_actual.role in ("administrador", "master")
        )
        try:
            interfaz.order_store.actualizar_estado_despacho(
                ped_obj.id, nuevo_est, usuario=usr, permitir_retroceso=puede_retroceder
            )
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
            items_lista.controls.append(_construir_encabezado_fecha(f_clave, hoy_str, len(pedidos_grupo), interfaz))
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
        if not interfaz.exigir_roles("operador", "administrador"):
            return
        if not pedidos_seleccionados:
            return
        usr = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operador"
        puede_retroceder = bool(
            interfaz.usuario_actual and interfaz.usuario_actual.role in ("administrador", "master")
        )
        try:
            n_upd = interfaz.order_store.avanzar_estado_lote(
                list(pedidos_seleccionados),
                st_nuevo,
                usuario=usr,
                permitir_retroceso=puede_retroceder,
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
        bgcolor=colores.superficie_suave,
        border=ft.Border.all(1, colores.borde),
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
        bgcolor=colores.superficie_suave,
        border_color=colores.borde,
        color=colores.texto,
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
        pal = colores_de(interfaz)
        bg_activo = ft.Colors.with_opacity(0.14, ft.Colors.BLUE_500)
        for b, tag in [(btn_f_todos, "todos"), (btn_f_hoy, "hoy"), (btn_f_pend, "pendientes"), (btn_f_desp, "despachados")]:
            b.style = (
                ft.ButtonStyle(bgcolor=bg_activo, color=pal.texto, side=ft.BorderSide(1, ft.Colors.BLUE_500))
                if filtro_rapido_activo == tag
                else ft.ButtonStyle(bgcolor=ft.Colors.TRANSPARENT, color=pal.secundario, side=ft.BorderSide(1, pal.borde))
            )

    def cambiar_filtro_rapido(nuevo_filtro: str) -> None:
        nonlocal filtro_rapido_activo, pagina_actual
        pagina_actual = 1
        filtro_rapido_activo = nuevo_filtro
        actualizar_botones_filtro()
        actualizar_vista(campo_busqueda.value or "")

    actualizar_botones_filtro()

    estilo_btn_accion = ft.ButtonStyle(
        color=colores.texto,
        bgcolor=colores.superficie_suave,
        side=ft.BorderSide(1, colores.borde),
    )

    barra_busqueda = ft.Column(
        [
            ft.Row(
                [
                    campo_busqueda,
                    ft.IconButton(icon=ft.Icons.CLEAR, icon_size=18, icon_color=colores.secundario, tooltip="Borrar búsqueda", on_click=limpiar_busqueda),
                    ft.Button(
                        "Rótulos A4 (Lote)",
                        icon=ft.Icons.PRINT,
                        tooltip="Generar rótulos optimizados llenando hojas A4 (10 por página)",
                        style=estilo_btn_accion,
                        on_click=imprimir_lote_rotulos_a4,
                    ),
                    ft.Button(
                        "Escanear QR / Cambiar Estado",
                        icon=ft.Icons.QR_CODE_SCANNER,
                        style=estilo_btn_accion,
                        on_click=lambda _e: interfaz.mostrar_escaner_qr_despacho(al_actualizar=recargar_y_actualizar),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    ft.Row(
                        [ft.Text("Filtros rápidos:", size=11, color=colores.secundario, weight=ft.FontWeight.BOLD), btn_f_todos, btn_f_hoy, btn_f_pend, btn_f_desp],
                        spacing=6,
                        wrap=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.TextButton("Seleccionar Visibles", icon=ft.Icons.CHECK_BOX_OUTLINED, icon_color=colores.secundario, style=ft.ButtonStyle(color=colores.secundario), on_click=_sel_todos_visibles),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
            barra_lote,
        ],
        spacing=6,
    )

    cabecera_columnas = construir_cabecera_columnas_historial(interfaz)

    actualizar_vista("")

    w_calc = interfaz.ancho_adaptable(1140) if hasattr(interfaz, "ancho_adaptable") else 1140
    ancho_dlg = int(w_calc) if isinstance(w_calc, (int, float)) else 1140
    bg_dlg = "#121214" if bool(getattr(interfaz, "modo_oscuro", True)) else colores.superficie

    dialogo = ft.AlertDialog(
        modal=True,
        bgcolor=bg_dlg,
        title=ft.Row(
            [
                ft.Row([ft.Icon(ft.Icons.RECEIPT_LONG, color=colores.secundario, size=22), ft.Text("Ver pedidos mayoristas", weight=ft.FontWeight.BOLD, color=colores.texto, size=18)], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([texto_contador, ft.IconButton(icon=ft.Icons.CHECK_BOX_OUTLINED, icon_size=20, icon_color=colores.secundario, tooltip="Seleccionar todos los pedidos visibles", on_click=_sel_todos_visibles)], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        content=ft.Container(
            width=ancho_dlg,
            height=660,
            bgcolor=bg_dlg,
            content=ft.Column([barra_busqueda, cabecera_columnas, items_lista, barra_paginacion], expand=True, spacing=4),
        ),
        actions=[interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())],
    )
    interfaz.page.show_dialog(dialogo)
