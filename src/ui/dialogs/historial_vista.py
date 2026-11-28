"""Vista principal de historial de pedidos mayoristas con filtros, paginación y lote."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from typing import Any

import flet as ft

from ...orders import Pedido
from ..components.debounce import Debouncer
from ..design import colores_de, es_viewport_estrecho, fila_cabecera_responsiva
from .historial_cards import (
    _construir_encabezado_fecha,
    _construir_fila_pedido,
    construir_cabecera_columnas_historial,
)
from .historial_filtros import (
    agrupar_pedidos_por_fecha,
    filtrar_y_ordenar_pedidos,
    paginar_pedidos,
)


def _construir_placeholder_vacio(interfaz: Any, total_pedidos: int, termino: str) -> ft.Container:
    if not total_pedidos:
        contenido: ft.Control = ft.Text(
            "Aún no se han registrado pedidos en el sistema.",
            color=interfaz.secundario,
            size=13,
        )
    else:
        contenido = ft.Column(
            [
                ft.Icon(ft.Icons.SEARCH_OFF, size=34, color=interfaz.secundario),
                ft.Text(
                    f"No se encontraron pedidos para '{termino}'.",
                    color=interfaz.secundario,
                    size=13,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        )
    return ft.Container(padding=30, alignment=ft.Alignment.CENTER, content=contenido)


def _construir_fila_superior_busqueda(
    interfaz: Any,
    colores: Any,
    campo_busqueda: ft.TextField,
    on_limpiar: Callable[[ft.Event], None],
    on_rotulos_lote: Callable[[ft.Event], None],
    on_escaner_qr: Callable[[ft.Event], None],
) -> ft.Control:
    estrecho = es_viewport_estrecho(interfaz, umbral=820.0)
    estilo_btn_accion = ft.ButtonStyle(
        color=colores.texto,
        bgcolor=colores.superficie_suave,
        side=ft.BorderSide(1, colores.borde),
    )
    fila_campo = ft.Row(
        [
            campo_busqueda,
            ft.IconButton(
                icon=ft.Icons.CLEAR,
                icon_size=18,
                icon_color=colores.secundario,
                tooltip="Borrar búsqueda",
                on_click=on_limpiar,
            ),
        ],
        spacing=4,
        expand=not estrecho,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    botones = ft.Row(
        [
            ft.Button(
                "Rótulos A4 (Lote)",
                icon=ft.Icons.PRINT,
                tooltip="Generar rótulos optimizados llenando hojas A4 (10 por página)",
                style=estilo_btn_accion,
                on_click=on_rotulos_lote,
            ),
            ft.Button(
                "Escanear QR / Cambiar Estado",
                icon=ft.Icons.QR_CODE_SCANNER,
                style=estilo_btn_accion,
                on_click=on_escaner_qr,
            ),
        ],
        spacing=6,
        wrap=True,
        run_spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    if estrecho:
        return ft.Column([fila_campo, botones], spacing=6, tight=True)
    return ft.Row(
        [fila_campo, botones],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


class _HistorialPedidosController:
    """Controlador de estado y eventos para el diálogo de historial de pedidos."""

    def __init__(self, interfaz: Any) -> None:
        self.interfaz = interfaz
        self.colores = colores_de(interfaz)
        self.pedidos: list[Pedido] = interfaz.order_store.listar_pedidos(limit=400)
        self.pedidos_visibles: list[Pedido] = []
        self.pedidos_seleccionados: set[int] = set()
        self.filtro_rapido_activo = "todos"
        self.pagina_actual = 1
        self.tamano_pagina = 25
        self.total_paginas_global = 1

        self.items_lista = ft.ListView(expand=True, spacing=1)
        self.texto_contador = ft.Text(
            f"Total: {len(self.pedidos)} pedidos" if self.pedidos else "",
            size=11,
            color=interfaz.secundario,
        )
        self.texto_pagina_info = ft.Text(
            "Pág. 1 de 1",
            size=12,
            weight=ft.FontWeight.BOLD,
            color=interfaz.texto,
        )
        self.texto_rango_info = ft.Text("", size=11, color=interfaz.secundario)
        self.texto_lote_sel = ft.Text(
            "0 seleccionados",
            size=11,
            weight=ft.FontWeight.BOLD,
            color=interfaz.texto,
        )
        self.debouncer = Debouncer(0.25)

        self.barra_paginacion = self._construir_barra_paginacion()
        self.barra_lote = self._construir_barra_lote()
        self.campo_busqueda = self._construir_campo_busqueda()
        self.botones_filtro = self._construir_filtros_rapidos()
        self._actualizar_botones_filtro()
        self.barra_busqueda = self._construir_barra_busqueda()
        self.actualizar_vista("")

    def _construir_barra_paginacion(self) -> ft.Container:
        self.btn_pag_primera = ft.IconButton(
            icon=ft.Icons.FIRST_PAGE,
            icon_size=18,
            tooltip="Primera página",
            on_click=lambda _e: self._ir_a_pagina(1),
        )
        self.btn_pag_anterior = ft.IconButton(
            icon=ft.Icons.NAVIGATE_BEFORE,
            icon_size=18,
            tooltip="Página anterior",
            on_click=lambda _e: self._ir_a_pagina(self.pagina_actual - 1),
        )
        self.btn_pag_siguiente = ft.IconButton(
            icon=ft.Icons.NAVIGATE_NEXT,
            icon_size=18,
            tooltip="Página siguiente",
            on_click=lambda _e: self._ir_a_pagina(self.pagina_actual + 1),
        )
        self.btn_pag_ultima = ft.IconButton(
            icon=ft.Icons.LAST_PAGE,
            icon_size=18,
            tooltip="Última página",
            on_click=lambda _e: self._ir_a_pagina(self.total_paginas_global),
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
            on_select=self._cambiar_tamano_pagina,
        )
        return ft.Container(
            bgcolor=self.colores.superficie_suave,
            border=ft.Border.all(1, self.colores.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            content=fila_cabecera_responsiva(
                self.texto_rango_info,
                ft.Row(
                    [
                        self.btn_pag_primera,
                        self.btn_pag_anterior,
                        self.texto_pagina_info,
                        self.btn_pag_siguiente,
                        self.btn_pag_ultima,
                        dropdown_tamano,
                    ],
                    spacing=4,
                    wrap=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                spacing=8,
                run_spacing=4,
            ),
        )

    def _construir_barra_lote(self) -> ft.Container:
        return ft.Container(
            visible=False,
            bgcolor=self.colores.superficie_suave,
            border=ft.Border.all(1, self.colores.borde),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            content=ft.Row(
                [
                    self.texto_lote_sel,
                    ft.Button(
                        "Despachar Seleccionados",
                        icon=ft.Icons.LOCAL_SHIPPING,
                        bgcolor=ft.Colors.BLUE_600,
                        color=ft.Colors.WHITE,
                        on_click=lambda _e: self._despachar_lote("despachado"),
                    ),
                    ft.Button(
                        "Marcar Entregados",
                        icon=ft.Icons.TASK_ALT,
                        bgcolor=ft.Colors.GREEN_600,
                        color=ft.Colors.WHITE,
                        on_click=lambda _e: self._despachar_lote("entregado"),
                    ),
                    ft.TextButton("Desmarcar", on_click=self._desmarcar_todos),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
        )

    def _construir_campo_busqueda(self) -> ft.TextField:
        campo = ft.TextField(
            hint_text="Buscar por cliente, remito / nota, N° pedido, fecha (DD/MM/AAAA) o armador...",
            prefix_icon=ft.Icons.SEARCH,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=self.colores.superficie_suave,
            border_color=self.colores.borde,
            color=self.colores.texto,
            expand=True,
        )
        campo.on_change = lambda _e: self.debouncer.debounce(self._al_cambiar_busqueda)
        return campo

    def _construir_filtros_rapidos(self) -> tuple[tuple[ft.OutlinedButton, str], ...]:
        definiciones: tuple[tuple[str, Any, str], ...] = (
            ("Todos", None, "todos"),
            ("Solo Hoy", ft.Icons.TODAY, "hoy"),
            ("Pendientes de Cierre", ft.Icons.PENDING_ACTIONS, "pendientes"),
            ("Despachados", ft.Icons.LOCAL_SHIPPING, "despachados"),
        )
        botones: list[tuple[ft.OutlinedButton, str]] = []
        for etiqueta, icono, tag in definiciones:
            kwargs: dict[str, Any] = {
                "on_click": lambda _e, t=tag: self._cambiar_filtro_rapido(t),
            }
            if icono is not None:
                kwargs["icon"] = icono
            botones.append((ft.OutlinedButton(etiqueta, **kwargs), tag))
        return tuple(botones)

    def _construir_barra_busqueda(self) -> ft.Column:
        controles_filtros: list[ft.Control] = [
            ft.Text(
                "Filtros rápidos:",
                size=11,
                color=self.colores.secundario,
                weight=ft.FontWeight.BOLD,
            ),
            *(btn for btn, _tag in self.botones_filtro),
        ]
        return ft.Column(
            [
                _construir_fila_superior_busqueda(
                    self.interfaz,
                    self.colores,
                    self.campo_busqueda,
                    on_limpiar=self._limpiar_busqueda,
                    on_rotulos_lote=self._imprimir_lote_rotulos_a4,
                    on_escaner_qr=lambda _e: self.interfaz.mostrar_escaner_qr_despacho(
                        al_actualizar=self.recargar_y_actualizar
                    ),
                ),
                ft.Row(
                    [
                        ft.Row(
                            controles_filtros,
                            spacing=6,
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.TextButton(
                            "Seleccionar Visibles",
                            icon=ft.Icons.CHECK_BOX_OUTLINED,
                            icon_color=self.colores.secundario,
                            style=ft.ButtonStyle(color=self.colores.secundario),
                            on_click=self._sel_todos_visibles,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
                self.barra_lote,
            ],
            spacing=6,
        )

    def _al_cambiar_busqueda(self) -> None:
        if self.pagina_actual != 1:
            self._ir_a_pagina(1)
        else:
            self.actualizar_vista(self.campo_busqueda.value or "")

    def _ir_a_pagina(self, num: int) -> None:
        if 1 <= num <= self.total_paginas_global:
            self.pagina_actual = num
            self.actualizar_vista(self.campo_busqueda.value or "")

    def _cambiar_tamano_pagina(self, e: Any) -> None:
        try:
            self.tamano_pagina = int(e.control.value)
        except (TypeError, ValueError, AttributeError):
            self.tamano_pagina = 25
        self.pagina_actual = 1
        self.actualizar_vista(self.campo_busqueda.value or "")

    def _on_row_hover(self, e: ft.HoverEvent) -> None:
        with suppress(Exception):
            pal = colores_de(self.interfaz)
            e.control.bgcolor = (
                ft.Colors.with_opacity(0.08, pal.texto)
                if e.data == "true"
                else pal.superficie_suave
            )
            e.control.update()

    def _usuario_y_permiso_retroceso(self) -> tuple[str, bool]:
        usuario = self.interfaz.usuario_actual
        nombre = usuario.username if usuario else "Operador"
        puede_retroceder = bool(usuario and usuario.role in ("administrador", "master"))
        return nombre, puede_retroceder

    def _actualizar_barra_lote(self) -> None:
        c_sel = len(self.pedidos_seleccionados)
        self.barra_lote.visible = c_sel > 0
        self.texto_lote_sel.value = f"📦 {c_sel} pedido(s) seleccionado(s):"
        if self.interfaz.page:
            self.interfaz.page.update()

    def _toggle_sel(self, e: ft.Event, pid: int) -> None:
        if e.control.value:
            self.pedidos_seleccionados.add(pid)
        else:
            self.pedidos_seleccionados.discard(pid)
        self._actualizar_barra_lote()

    def _cambiar_estado_ped(self, ped_obj: Pedido, nuevo_est: str) -> None:
        if not self.interfaz.exigir_roles("operador", "administrador"):
            return
        usr, puede_retroceder = self._usuario_y_permiso_retroceso()
        try:
            self.interfaz.order_store.actualizar_estado_despacho(
                ped_obj.id,
                nuevo_est,
                usuario=usr,
                permitir_retroceso=puede_retroceder,
            )
            self.recargar_y_actualizar()
            self.interfaz.sincronizar_sesiones()
        except Exception as err:
            self.interfaz.notificar(str(err))

    def _despachar_lote(self, st_nuevo: str) -> None:
        if not self.interfaz.exigir_roles("operador", "administrador") or not self.pedidos_seleccionados:
            return
        usr, puede_retroceder = self._usuario_y_permiso_retroceso()
        try:
            n_upd = self.interfaz.order_store.avanzar_estado_lote(
                list(self.pedidos_seleccionados),
                st_nuevo,
                usuario=usr,
                permitir_retroceso=puede_retroceder,
            )
            self.pedidos_seleccionados.clear()
            self._actualizar_barra_lote()
            self.interfaz.reproducir_sonido("exito")
            self.interfaz.notificar(f"Se actualizaron {n_upd} pedido(s) a '{st_nuevo.upper()}'.")
            self.recargar_y_actualizar()
        except Exception as ex_l:
            self.interfaz.reproducir_sonido("error")
            self.interfaz.notificar(f"Error en despacho en lote: {ex_l}")

    def _sel_todos_visibles(self, _e: ft.Event) -> None:
        for p in self.pedidos_visibles:
            if getattr(p, "estado", "") != "anulado":
                self.pedidos_seleccionados.add(p.id)
        self._actualizar_barra_lote()
        self.actualizar_vista(self.campo_busqueda.value or "")

    def _desmarcar_todos(self, _e: ft.Event) -> None:
        self.pedidos_seleccionados.clear()
        self._actualizar_barra_lote()
        self.actualizar_vista(self.campo_busqueda.value or "")

    def _limpiar_busqueda(self, _e: ft.Event) -> None:
        self.pagina_actual = 1
        self.campo_busqueda.value = ""
        self.actualizar_vista("")

    def _imprimir_lote_rotulos_a4(self, _e: ft.Event) -> None:
        candidatos = [
            p
            for p in self.pedidos_visibles
            if getattr(p, "estado", "") != "anulado" and getattr(p, "bultos", 0) > 0
        ]
        if not candidatos:
            self.interfaz.notificar("No hay pedidos con bultos para generar rótulos.")
            return
        self.interfaz.imprimir_rotulos_lote(candidatos)

    def _actualizar_botones_filtro(self) -> None:
        pal = colores_de(self.interfaz)
        bg_activo = ft.Colors.with_opacity(0.14, ft.Colors.BLUE_500)
        for btn, tag in self.botones_filtro:
            btn.style = (
                ft.ButtonStyle(
                    bgcolor=bg_activo,
                    color=pal.texto,
                    side=ft.BorderSide(1, ft.Colors.BLUE_500),
                )
                if self.filtro_rapido_activo == tag
                else ft.ButtonStyle(
                    bgcolor=ft.Colors.TRANSPARENT,
                    color=pal.secundario,
                    side=ft.BorderSide(1, pal.borde),
                )
            )

    def _cambiar_filtro_rapido(self, nuevo_filtro: str) -> None:
        self.pagina_actual = 1
        self.filtro_rapido_activo = nuevo_filtro
        self._actualizar_botones_filtro()
        self.actualizar_vista(self.campo_busqueda.value or "")

    def recargar_y_actualizar(self) -> None:
        self.pagina_actual = 1
        self.pedidos = self.interfaz.order_store.listar_pedidos(limit=400)
        ids_activos = {p.id for p in self.pedidos if getattr(p, "estado", "") != "anulado"}
        if self.pedidos_seleccionados - ids_activos:
            self.pedidos_seleccionados.intersection_update(ids_activos)
            self._actualizar_barra_lote()
        self.actualizar_vista(self.campo_busqueda.value or "")

    def actualizar_vista(self, termino: str = "") -> None:
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        filtrados = filtrar_y_ordenar_pedidos(
            self.pedidos,
            filtro_rapido=self.filtro_rapido_activo,
            termino=termino,
            hoy_str=hoy_str,
        )
        pedidos_pagina, self.pagina_actual, self.total_paginas_global, inicio_idx, fin_idx = (
            paginar_pedidos(filtrados, self.pagina_actual, self.tamano_pagina)
        )

        self.btn_pag_primera.disabled = self.pagina_actual <= 1
        self.btn_pag_anterior.disabled = self.pagina_actual <= 1
        self.btn_pag_siguiente.disabled = self.pagina_actual >= self.total_paginas_global
        self.btn_pag_ultima.disabled = self.pagina_actual >= self.total_paginas_global
        self.texto_pagina_info.value = f"Pág. {self.pagina_actual} de {self.total_paginas_global}"
        self.items_lista.controls.clear()

        if not filtrados:
            self.pedidos_visibles = []
            self.barra_paginacion.visible = False
            self.items_lista.controls.append(
                _construir_placeholder_vacio(self.interfaz, len(self.pedidos), termino)
            )
            self.texto_contador.value = f"0 de {len(self.pedidos)} pedidos"
            if self.interfaz.page:
                self.interfaz.page.update()
            return

        self.barra_paginacion.visible = True
        self.pedidos_visibles = pedidos_pagina
        total_items = len(filtrados)
        self.texto_rango_info.value = f"Mostrando {inicio_idx + 1}–{fin_idx} de {total_items} pedidos"
        self.texto_contador.value = (
            f"Pág. {self.pagina_actual}/{self.total_paginas_global} ({inicio_idx + 1}–{fin_idx} de {total_items})"
            if termino.strip()
            else f"Total: {total_items} pedidos · Pág. {self.pagina_actual}/{self.total_paginas_global}"
        )

        for f_clave, pedidos_grupo in agrupar_pedidos_por_fecha(pedidos_pagina):
            self.items_lista.controls.append(
                _construir_encabezado_fecha(f_clave, hoy_str, len(pedidos_grupo), self.interfaz)
            )
            for p in pedidos_grupo:
                self.items_lista.controls.append(
                    _construir_fila_pedido(
                        self.interfaz,
                        p,
                        self.pedidos_seleccionados,
                        self._toggle_sel,
                        self._on_row_hover,
                        self._cambiar_estado_ped,
                        on_recargar=self.recargar_y_actualizar,
                    )
                )

        if self.interfaz.page:
            self.interfaz.page.update()

    def construir_dialogo(self) -> ft.AlertDialog:
        w_calc = (
            self.interfaz.ancho_adaptable(1140)
            if hasattr(self.interfaz, "ancho_adaptable")
            else 1140
        )
        h_calc = (
            self.interfaz.alto_adaptable(660)
            if hasattr(self.interfaz, "alto_adaptable")
            else 660
        )
        ancho_dlg = int(w_calc) if isinstance(w_calc, (int, float)) else 1140
        alto_dlg = int(h_calc) if isinstance(h_calc, (int, float)) else 660
        bg_dlg = (
            "#121214"
            if bool(getattr(self.interfaz, "modo_oscuro", True))
            else self.colores.superficie
        )

        return ft.AlertDialog(
            modal=True,
            bgcolor=bg_dlg,
            title=fila_cabecera_responsiva(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.RECEIPT_LONG, color=self.colores.secundario, size=22),
                        ft.Text(
                            "Ver pedidos mayoristas",
                            weight=ft.FontWeight.BOLD,
                            color=self.colores.texto,
                            size=18,
                        ),
                    ],
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        self.texto_contador,
                        ft.IconButton(
                            icon=ft.Icons.CHECK_BOX_OUTLINED,
                            icon_size=20,
                            icon_color=self.colores.secundario,
                            tooltip="Seleccionar todos los pedidos visibles",
                            on_click=self._sel_todos_visibles,
                        ),
                    ],
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                spacing=8,
                run_spacing=4,
            ),
            content=ft.Container(
                width=ancho_dlg,
                height=alto_dlg,
                bgcolor=bg_dlg,
                content=ft.Column(
                    [
                        self.barra_busqueda,
                        construir_cabecera_columnas_historial(self.interfaz),
                        self.items_lista,
                        self.barra_paginacion,
                    ],
                    expand=True,
                    spacing=4,
                ),
            ),
            actions=[
                self.interfaz.boton_dialogo("Cerrar", lambda _e: self.interfaz.page.pop_dialog())
            ],
        )


def mostrar_historial_pedidos(interfaz: Any, _evento: ft.Event | None = None) -> None:
    """Ventana completa con buscador y lista histórica de pedidos del depósito."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role not in (
        "operador",
        "administrador",
    ):
        interfaz.notificar("No tienes permisos suficientes para acceder al historial de pedidos.")
        return

    controlador = _HistorialPedidosController(interfaz)
    interfaz.page.show_dialog(controlador.construir_dialogo())
